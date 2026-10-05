from __future__ import annotations

import re
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from crossborder_compliance.application.metadata_services import (
    MetadataLifecycleError,
    lifecycle_transition_allowed,
)
from crossborder_compliance.domain.metadata import (
    GovernanceStatus,
    ModelCapability,
    ModelDefinition,
    ModelDeployment,
    ModelProvider,
    ModelProviderVersion,
    validate_endpoint_config,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.domain.compliance_profiles import PHASE1I_CONFIG_KINDS
from crossborder_compliance.infrastructure.persistence.compliance_profile_governance import (
    lock_definition,
    transition_validation,
    validate_payload,
)
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    AdminPublishRecordEntity,
    AnalysisSnapshotRegistryPinEntity,
    MetadataDefinitionEntity,
    MetadataVersionEntity,
    ModelCapabilityEntity,
    ModelDefinitionEntity,
    ModelDeploymentEntity,
    ModelProviderEntity,
    ModelProviderVersionEntity,
    RegistrySyncEventEntity,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MetadataOptimisticConcurrencyError(RuntimeError):
    pass


class _TenantScopedMetadataRepository:
    def __init__(self, session_factory: sessionmaker, context: RepositoryContext):
        self._sessions = session_factory
        self._context = context

    @property
    def tenant_id(self) -> str:
        return str(self._context.tenant_id)

    def _scoped(self, session, model, pk, object_id: UUID):
        return session.scalar(
            select(model).where(pk == str(object_id), model.tenant_id == self.tenant_id)
        )


class PostgresAdminMetadataRepository(_TenantScopedMetadataRepository):
    """Source-of-truth repository for generic metadata definitions and versions.

    Publication writes the active pointer and transactional outbox event in the same transaction.
    Registry refresh happens only after commit via RegistrySyncService.
    """

    def create_definition(
        self,
        *,
        kind: str,
        code: str,
        display_name: str,
        parent_definition_id: UUID | None = None,
    ) -> dict[str, object]:
        if kind in PHASE1I_CONFIG_KINDS:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", code):
                raise ValueError("Phase1I metadata code must be locale-neutral ASCII")
        if parent_definition_id is not None:
            with self._sessions() as session:
                parent = self._scoped(
                    session,
                    MetadataDefinitionEntity,
                    MetadataDefinitionEntity.definition_id,
                    parent_definition_id,
                )
                if parent is None:
                    raise LookupError("parent metadata definition not found in tenant scope")
        row = MetadataDefinitionEntity(
            definition_id=str(uuid4()),
            tenant_id=self.tenant_id,
            kind=kind,
            code=code,
            display_name=display_name,
            parent_definition_id=str(parent_definition_id) if parent_definition_id else None,
            active_version_id=None,
            status="ACTIVE",
        )
        with self._sessions() as session, session.begin():
            session.add(row)
        return self._definition_dict(row)

    def create_version(
        self,
        *,
        definition_id: UUID,
        payload: dict[str, object],
        effective_from=None,
        effective_to=None,
    ) -> dict[str, object]:
        with self._sessions() as session, session.begin():
            definition = self._scoped(
                session, MetadataDefinitionEntity, MetadataDefinitionEntity.definition_id, definition_id
            )
            if definition is None:
                raise LookupError("metadata definition not found in tenant scope")
            definition = lock_definition(session, definition)
            phase1i_values = validate_payload(session, definition, payload)
            max_version = session.scalar(
                select(func.max(MetadataVersionEntity.version_no)).where(
                    MetadataVersionEntity.tenant_id == self.tenant_id,
                    MetadataVersionEntity.definition_id == str(definition_id),
                )
            )
            row = MetadataVersionEntity(
                version_id=str(uuid4()),
                tenant_id=self.tenant_id,
                definition_id=str(definition_id),
                version_no=int(max_version or 0) + 1,
                lifecycle_status=GovernanceStatus.DRAFT.value,
                payload_json=dict(payload),
                created_by=self._context.permission.actor_id,
                effective_from=effective_from,
                effective_to=effective_to,
                status="ACTIVE",
            )
            for key, value in phase1i_values.items():
                setattr(row, key, value)
            session.add(row)
            session.flush()
            return self._version_dict(row)

    def update_draft(
        self,
        version_id: UUID,
        *,
        payload: dict[str, object],
        expected_record_version: int,
    ) -> dict[str, object]:
        with self._sessions() as session, session.begin():
            candidate = self._scoped(
                session, MetadataVersionEntity, MetadataVersionEntity.version_id, version_id
            )
            phase1i_values = {}
            if candidate is not None:
                definition = self._scoped(
                    session, MetadataDefinitionEntity, MetadataDefinitionEntity.definition_id,
                    UUID(candidate.definition_id),
                )
                if definition is not None:
                    lock_definition(session, definition)
                    phase1i_values = validate_payload(session, definition, payload)
            phase1i_values.pop("payload_json", None)
            result = session.execute(
                update(MetadataVersionEntity)
                .where(
                    MetadataVersionEntity.version_id == str(version_id),
                    MetadataVersionEntity.tenant_id == self.tenant_id,
                    MetadataVersionEntity.lifecycle_status == GovernanceStatus.DRAFT.value,
                    MetadataVersionEntity.record_version == expected_record_version,
                )
                .values(
                    payload_json=dict(payload),
                    record_version=MetadataVersionEntity.record_version + 1,
                    updated_at=utcnow(),
                    **phase1i_values,
                )
            )
            if result.rowcount != 1:
                existing = self._scoped(
                    session, MetadataVersionEntity, MetadataVersionEntity.version_id, version_id
                )
                if existing is None:
                    raise LookupError("metadata version not found in tenant scope")
                if existing.lifecycle_status != GovernanceStatus.DRAFT.value:
                    raise MetadataLifecycleError("only DRAFT metadata can be updated")
                raise MetadataOptimisticConcurrencyError("metadata version changed")
        return self.get_version(version_id)

    def transition(
        self,
        version_id: UUID,
        *,
        target_status: str,
        actor_id: str,
        expected_record_version: int,
    ) -> dict[str, object]:
        with self._sessions() as session, session.begin():
            row = self._scoped(
                session, MetadataVersionEntity, MetadataVersionEntity.version_id, version_id
            )
            if row is None:
                raise LookupError("metadata version not found in tenant scope")
            row = transition_validation(session, row, actor_id, target_status)
            if row.record_version != expected_record_version:
                raise MetadataOptimisticConcurrencyError("metadata version changed")
            current = row.lifecycle_status
            if not lifecycle_transition_allowed(current, target_status):
                raise MetadataLifecycleError(f"invalid lifecycle transition: {current} -> {target_status}")
            if (
                target_status == GovernanceStatus.APPROVED.value
                and actor_id == row.created_by
                and "metadata:self-review" not in self._context.permission.scopes
                and not self._context.permission.system
            ):
                raise MetadataLifecycleError("reviewer separation requires a different actor")

            row.lifecycle_status = target_status
            row.record_version += 1
            row.updated_at = utcnow()

            if target_status == GovernanceStatus.APPROVED.value:
                row.approved_by = actor_id
                row.approved_at = utcnow()

            if target_status == GovernanceStatus.ACTIVE.value:
                definition = self._scoped(
                    session,
                    MetadataDefinitionEntity,
                    MetadataDefinitionEntity.definition_id,
                    UUID(row.definition_id),
                )
                if definition is None:
                    raise LookupError("metadata definition not found")
                if definition.active_version_id and definition.active_version_id != row.version_id:
                    prior = session.scalar(
                        select(MetadataVersionEntity).where(
                            MetadataVersionEntity.version_id == definition.active_version_id,
                            MetadataVersionEntity.tenant_id == self.tenant_id,
                        )
                    )
                    if prior and prior.lifecycle_status == GovernanceStatus.ACTIVE.value:
                        prior.lifecycle_status = GovernanceStatus.SUPERSEDED.value
                        prior.record_version += 1
                        prior.updated_at = utcnow()
                definition.active_version_id = row.version_id
                definition.record_version += 1
                definition.updated_at = utcnow()
                row.published_at = utcnow()
                publish = AdminPublishRecordEntity(
                    publish_record_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    object_kind=definition.kind,
                    version_id=row.version_id,
                    published_by=actor_id,
                    published_at=utcnow(),
                    status="ACTIVE",
                )
                session.add(publish)
                session.add(
                    RegistrySyncEventEntity(
                        registry_sync_event_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind=definition.kind,
                        object_id=definition.definition_id,
                        version_id=row.version_id,
                        event_version=row.version_no,
                        attempts=0,
                        status="PENDING",
                    )
                )

            if target_status in {
                GovernanceStatus.SUPERSEDED.value,
                GovernanceStatus.EXPIRED.value,
                GovernanceStatus.ARCHIVED.value,
            }:
                definition = session.scalar(
                    select(MetadataDefinitionEntity).where(
                        MetadataDefinitionEntity.definition_id == row.definition_id,
                        MetadataDefinitionEntity.tenant_id == self.tenant_id,
                    )
                )
                if definition and definition.active_version_id == row.version_id:
                    definition.active_version_id = None
                    definition.record_version += 1
                    definition.updated_at = utcnow()

            session.flush()
            return self._version_dict(row)

    def get_version(self, version_id: UUID) -> dict[str, object]:
        with self._sessions() as session:
            row = self._scoped(
                session, MetadataVersionEntity, MetadataVersionEntity.version_id, version_id
            )
            if row is None:
                raise LookupError("metadata version not found in tenant scope")
            return self._version_dict(row)

    def history(self, definition_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as session:
            definition = self._scoped(
                session, MetadataDefinitionEntity, MetadataDefinitionEntity.definition_id, definition_id
            )
            if definition is None:
                return []
            rows = session.scalars(
                select(MetadataVersionEntity)
                .where(
                    MetadataVersionEntity.tenant_id == self.tenant_id,
                    MetadataVersionEntity.definition_id == str(definition_id),
                )
                .order_by(MetadataVersionEntity.version_no.desc())
            ).all()
            return [self._version_dict(row) for row in rows]

    def impact_preview(self, definition_id: UUID) -> dict[str, object]:
        with self._sessions() as session:
            definition = self._scoped(
                session, MetadataDefinitionEntity, MetadataDefinitionEntity.definition_id, definition_id
            )
            if definition is None:
                raise LookupError("metadata definition not found in tenant scope")
            return {
                "definition_id": definition.definition_id,
                "kind": definition.kind,
                "active_version_id": definition.active_version_id,
                "impact_mode": "REFERENCE_SCAN_ONLY",
                "requires_runtime_restart": False,
            }

    @staticmethod
    def _definition_dict(row: MetadataDefinitionEntity) -> dict[str, object]:
        return {
            "definition_id": row.definition_id,
            "kind": row.kind,
            "code": row.code,
            "display_name": row.display_name,
            "parent_definition_id": row.parent_definition_id,
            "active_version_id": row.active_version_id,
            "record_version": row.record_version,
            "status": row.status,
        }

    @staticmethod
    def _version_dict(row: MetadataVersionEntity) -> dict[str, object]:
        return {
            "version_id": row.version_id,
            "definition_id": row.definition_id,
            "version_no": row.version_no,
            "lifecycle_status": row.lifecycle_status,
            "payload": dict(row.payload_json or {}),
            "effective_from": row.effective_from,
            "effective_to": row.effective_to,
            "record_version": row.record_version,
            "approved_by": row.approved_by,
            "approved_at": row.approved_at,
            "published_at": row.published_at,
        }


class PostgresRegistrySourceRepository(_TenantScopedMetadataRepository):
    def load_jurisdictions(self) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.models import JurisdictionEntity
        today = date.today()
        with self._sessions() as session:
            jurisdictions = session.scalars(
                select(JurisdictionEntity).where(
                    JurisdictionEntity.tenant_id == self.tenant_id,
                    JurisdictionEntity.status == "ACTIVE",
                    or_(JurisdictionEntity.effective_from.is_(None), JurisdictionEntity.effective_from <= today),
                    or_(JurisdictionEntity.effective_to.is_(None), JurisdictionEntity.effective_to >= today),
                ).order_by(JurisdictionEntity.code)
            ).all()
            result: list[dict[str, object]] = []
            for row in jurisdictions:
                config = session.execute(
                    select(MetadataDefinitionEntity, MetadataVersionEntity)
                    .join(
                        MetadataVersionEntity,
                        MetadataVersionEntity.version_id == MetadataDefinitionEntity.active_version_id,
                    )
                    .where(
                        MetadataDefinitionEntity.tenant_id == self.tenant_id,
                        MetadataDefinitionEntity.kind == "JURISDICTION_CONFIG",
                        MetadataDefinitionEntity.canonical_object_id == row.jurisdiction_id,
                        MetadataVersionEntity.tenant_id == self.tenant_id,
                        MetadataVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                        or_(MetadataVersionEntity.effective_from.is_(None), MetadataVersionEntity.effective_from <= today),
                        or_(MetadataVersionEntity.effective_to.is_(None), MetadataVersionEntity.effective_to >= today),
                    )
                ).first()
                if config:
                    definition, version = config
                    version_id = version.version_id
                    version_no = version.version_no
                    payload = dict(version.payload_json or {})
                    config_definition_id = definition.definition_id
                else:
                    version_id = row.jurisdiction_id
                    version_no = row.record_version
                    payload = dict(row.metadata_json or {})
                    config_definition_id = None
                result.append(
                    {
                        "definition_id": row.jurisdiction_id,
                        "config_definition_id": config_definition_id,
                        "version_id": version_id,
                        "version_no": version_no,
                        "kind": "JURISDICTION",
                        "code": row.code,
                        "display_name": row.name,
                        "payload": payload,
                        "effective_from": row.effective_from,
                        "effective_to": row.effective_to,
                    }
                )
            return result

    def load_active(self, kind: str) -> list[dict[str, object]]:
        today = date.today()
        with self._sessions() as session:
            rows = session.execute(
                select(MetadataDefinitionEntity, MetadataVersionEntity)
                .join(
                    MetadataVersionEntity,
                    MetadataVersionEntity.version_id == MetadataDefinitionEntity.active_version_id,
                )
                .where(
                    MetadataDefinitionEntity.tenant_id == self.tenant_id,
                    MetadataVersionEntity.tenant_id == self.tenant_id,
                    MetadataDefinitionEntity.kind == kind,
                    MetadataDefinitionEntity.status == "ACTIVE",
                    MetadataVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    or_(MetadataVersionEntity.effective_from.is_(None), MetadataVersionEntity.effective_from <= today),
                    or_(MetadataVersionEntity.effective_to.is_(None), MetadataVersionEntity.effective_to >= today),
                )
                .order_by(MetadataDefinitionEntity.code)
            ).all()
            return [self._project(definition, version) for definition, version in rows]

    def load_active_version(self, kind: str, definition_id: UUID) -> dict[str, object] | None:
        rows = self.load_active(kind)
        return next(
            (row for row in rows if row["definition_id"] == str(definition_id)),
            None,
        )

    @staticmethod
    def _project(definition: MetadataDefinitionEntity, version: MetadataVersionEntity) -> dict[str, object]:
        return {
            "definition_id": definition.canonical_object_id or definition.definition_id,
            "config_definition_id": definition.definition_id,
            "canonical_object_type": definition.canonical_object_type,
            "version_id": version.version_id,
            "version_no": version.version_no,
            "kind": definition.kind,
            "code": definition.code,
            "display_name": definition.display_name,
            "parent_definition_id": definition.parent_definition_id,
            "payload": dict(version.payload_json or {}),
            "effective_from": version.effective_from,
            "effective_to": version.effective_to,
        }


class PostgresRegistrySyncEventRepository(_TenantScopedMetadataRepository):
    def pending(self, limit: int = 100, *, object_kinds=None) -> list[dict[str, object]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(RegistrySyncEventEntity)
                .where(
                    RegistrySyncEventEntity.tenant_id == self.tenant_id,
                    RegistrySyncEventEntity.status.in_(["PENDING", "RETRY"]),
                    RegistrySyncEventEntity.object_kind.in_(object_kinds) if object_kinds else
                    RegistrySyncEventEntity.object_kind.notin_(("KNOWLEDGE_INGESTION", "KNOWLEDGE_VERSION_PUBLISHED")),
                )
                .order_by(RegistrySyncEventEntity.created_at)
                .limit(limit)
            ).all()
            return [
                {
                    "registry_sync_event_id": row.registry_sync_event_id,
                    "object_kind": row.object_kind,
                    "object_id": row.object_id,
                    "version_id": row.version_id,
                    "event_version": row.event_version,
                    "attempts": row.attempts,
                }
                for row in rows
            ]

    def mark_applied(self, event_id: UUID) -> None:
        with self._sessions() as session, session.begin():
            row = self._scoped(
                session, RegistrySyncEventEntity, RegistrySyncEventEntity.registry_sync_event_id, event_id
            )
            if row is None:
                return
            if row.status == "APPLIED":
                return
            row.status = "APPLIED"
            row.applied_at = utcnow()
            row.last_error = None
            row.updated_at = utcnow()

    def mark_retry(self, event_id: UUID, error: str) -> None:
        with self._sessions() as session, session.begin():
            row = self._scoped(
                session, RegistrySyncEventEntity, RegistrySyncEventEntity.registry_sync_event_id, event_id
            )
            if row is None or row.status == "APPLIED":
                return
            row.status = "RETRY"
            row.attempts += 1
            row.last_error = error[:2000]
            row.updated_at = utcnow()


class PostgresSnapshotRegistryPinRepository(_TenantScopedMetadataRepository):
    def add_pin(
        self,
        *,
        analysis_snapshot_id: UUID,
        pin_type: str,
        logical_key: str,
        object_id: UUID,
        version_id: UUID,
        version_no: int,
    ) -> None:
        with self._sessions() as session, session.begin():
            existing = session.scalar(
                select(AnalysisSnapshotRegistryPinEntity).where(
                    AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant_id,
                    AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(analysis_snapshot_id),
                    AnalysisSnapshotRegistryPinEntity.pin_type == pin_type,
                    AnalysisSnapshotRegistryPinEntity.logical_key == logical_key,
                )
            )
            if existing:
                same = (
                    existing.object_id == str(object_id)
                    and existing.version_id == str(version_id)
                    and existing.version_no == version_no
                )
                if same:
                    return
                raise MetadataLifecycleError("analysis snapshot pin is immutable")
            session.add(
                AnalysisSnapshotRegistryPinEntity(
                    pin_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    analysis_snapshot_id=str(analysis_snapshot_id),
                    pin_type=pin_type,
                    logical_key=logical_key,
                    object_id=str(object_id),
                    version_id=str(version_id),
                    version_no=version_no,
                    status="ACTIVE",
                )
            )

    def list_pins(self, analysis_snapshot_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(AnalysisSnapshotRegistryPinEntity)
                .where(
                    AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant_id,
                    AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == str(analysis_snapshot_id),
                )
                .order_by(
                    AnalysisSnapshotRegistryPinEntity.pin_type,
                    AnalysisSnapshotRegistryPinEntity.logical_key,
                )
            ).all()
            return [
                {
                    "pin_id": row.pin_id,
                    "pin_type": row.pin_type,
                    "logical_key": row.logical_key,
                    "object_id": row.object_id,
                    "version_id": row.version_id,
                    "version_no": row.version_no,
                }
                for row in rows
            ]


class PostgresModelRegistryRepository(_TenantScopedMetadataRepository):
    """Model metadata source. Runtime projections intentionally omit secret_ref."""

    def add_provider(
        self,
        provider: ModelProvider,
        version: ModelProviderVersion,
    ) -> None:
        self._context.assert_tenant(provider.tenant_id)
        self._context.assert_tenant(version.tenant_id)
        validate_endpoint_config(version.endpoint_config)
        with self._sessions() as session, session.begin():
            provider_row = ModelProviderEntity(
                provider_id=str(provider.provider_id),
                tenant_id=self.tenant_id,
                provider_type=provider.provider_type.value,
                code=provider.code,
                display_name=provider.display_name,
                active_version_id=None,
                enabled=provider.enabled,
                status="ACTIVE",
            )
            session.add(provider_row)
            session.flush()
            version_row = ModelProviderVersionEntity(
                    provider_version_id=str(version.provider_version_id),
                    tenant_id=self.tenant_id,
                    provider_id=str(provider.provider_id),
                    version_no=version.version_no,
                    lifecycle_status=version.lifecycle_status.value,
                    base_url_ref=version.base_url_ref,
                    endpoint_config_json=dict(version.endpoint_config),
                    auth_type=version.auth_type,
                    secret_ref=version.secret_ref,
                    deployment_type=version.deployment_type,
                    trust_level=version.trust_level,
                    data_boundary=version.data_boundary,
                    timeout_policy_json=dict(version.timeout_policy),
                    retry_policy_json=dict(version.retry_policy),
                    cost_metadata_json=dict(version.cost_metadata),
                    enabled=version.enabled,
                    effective_from=version.effective_from,
                    effective_to=version.effective_to,
                    status="ACTIVE",
                )
            session.add(version_row)
            session.flush()
            if version.lifecycle_status == GovernanceStatus.ACTIVE:
                provider_row.active_version_id = str(version.provider_version_id)

    def add_model(
        self,
        model: ModelDefinition,
        deployment: ModelDeployment,
        capabilities: list[ModelCapability],
    ) -> None:
        self._context.assert_tenant(model.tenant_id)
        self._context.assert_tenant(deployment.tenant_id)
        with self._sessions() as session, session.begin():
            provider = self._scoped(
                session, ModelProviderEntity, ModelProviderEntity.provider_id, model.provider_id
            )
            provider_version = self._scoped(
                session,
                ModelProviderVersionEntity,
                ModelProviderVersionEntity.provider_version_id,
                deployment.provider_version_id,
            )
            if provider is None or provider_version is None:
                raise LookupError("model provider/version not found in tenant scope")
            model_row = ModelDefinitionEntity(
                model_definition_id=str(model.model_definition_id),
                tenant_id=self.tenant_id,
                provider_id=str(model.provider_id),
                model_id=model.model_id,
                display_name=model.display_name,
                context_window=model.context_window,
                max_output_tokens=model.max_output_tokens,
                active_deployment_id=None,
                enabled=model.enabled,
                status="ACTIVE",
            )
            session.add(model_row)
            session.flush()
            deployment_row = ModelDeploymentEntity(
                    model_deployment_id=str(deployment.model_deployment_id),
                    tenant_id=self.tenant_id,
                    model_definition_id=str(model.model_definition_id),
                    provider_version_id=str(deployment.provider_version_id),
                    deployment_ref=deployment.deployment_ref,
                    lifecycle_status=deployment.lifecycle_status.value,
                    enabled=deployment.enabled,
                    effective_from=deployment.effective_from,
                    effective_to=deployment.effective_to,
                    status="ACTIVE",
                )
            session.add(deployment_row)
            session.flush()
            if deployment.lifecycle_status == GovernanceStatus.ACTIVE:
                model_row.active_deployment_id = str(deployment.model_deployment_id)
            for capability in capabilities:
                self._context.assert_tenant(capability.tenant_id)
                session.add(
                    ModelCapabilityEntity(
                        model_capability_id=str(capability.model_capability_id),
                        tenant_id=self.tenant_id,
                        model_definition_id=str(model.model_definition_id),
                        capability=capability.capability.value,
                        metadata_json=dict(capability.metadata),
                        status="ACTIVE",
                    )
                )

    def set_model_enabled(self, model_definition_id: UUID, enabled: bool) -> None:
        with self._sessions() as session, session.begin():
            row = self._scoped(
                session,
                ModelDefinitionEntity,
                ModelDefinitionEntity.model_definition_id,
                model_definition_id,
            )
            if row is None:
                raise LookupError("model not found in tenant scope")
            row.enabled = enabled
            row.record_version += 1
            row.updated_at = utcnow()

    def set_provider_enabled(self, provider_id: UUID, enabled: bool) -> None:
        with self._sessions() as session, session.begin():
            row = self._scoped(
                session,
                ModelProviderEntity,
                ModelProviderEntity.provider_id,
                provider_id,
            )
            if row is None:
                raise LookupError("model provider not found in tenant scope")
            row.enabled = enabled
            row.record_version += 1
            row.updated_at = utcnow()

    def set_deployment_enabled(self, model_deployment_id: UUID, enabled: bool) -> None:
        with self._sessions() as session, session.begin():
            row = self._scoped(
                session,
                ModelDeploymentEntity,
                ModelDeploymentEntity.model_deployment_id,
                model_deployment_id,
            )
            if row is None:
                raise LookupError("model deployment not found in tenant scope")
            row.enabled = enabled
            row.record_version += 1
            row.updated_at = utcnow()

    def load_runtime_models(self) -> list[dict[str, object]]:
        today = date.today()
        with self._sessions() as session:
            rows = session.execute(
                select(
                    ModelDefinitionEntity,
                    ModelDeploymentEntity,
                    ModelProviderEntity,
                    ModelProviderVersionEntity,
                )
                .join(
                    ModelDeploymentEntity,
                    ModelDeploymentEntity.model_deployment_id
                    == ModelDefinitionEntity.active_deployment_id,
                )
                .join(
                    ModelProviderEntity,
                    ModelProviderEntity.provider_id == ModelDefinitionEntity.provider_id,
                )
                .join(
                    ModelProviderVersionEntity,
                    ModelProviderVersionEntity.provider_version_id
                    == ModelDeploymentEntity.provider_version_id,
                )
                .where(
                    ModelDefinitionEntity.tenant_id == self.tenant_id,
                    ModelDeploymentEntity.tenant_id == self.tenant_id,
                    ModelProviderEntity.tenant_id == self.tenant_id,
                    ModelProviderVersionEntity.tenant_id == self.tenant_id,
                    ModelDefinitionEntity.enabled.is_(True),
                    ModelDeploymentEntity.enabled.is_(True),
                    ModelProviderEntity.enabled.is_(True),
                    ModelProviderVersionEntity.enabled.is_(True),
                    ModelProviderEntity.active_version_id == ModelProviderVersionEntity.provider_version_id,
                    ModelDeploymentEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    ModelProviderVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    or_(ModelDeploymentEntity.effective_from.is_(None), ModelDeploymentEntity.effective_from <= today),
                    or_(ModelDeploymentEntity.effective_to.is_(None), ModelDeploymentEntity.effective_to >= today),
                )
            ).all()
            result: list[dict[str, object]] = []
            for model, deployment, provider, provider_version in rows:
                caps = session.scalars(
                    select(ModelCapabilityEntity.capability).where(
                        ModelCapabilityEntity.tenant_id == self.tenant_id,
                        ModelCapabilityEntity.model_definition_id == model.model_definition_id,
                        ModelCapabilityEntity.status == "ACTIVE",
                    )
                ).all()
                result.append(
                    {
                        "model_definition_id": model.model_definition_id,
                        "provider_id": provider.provider_id,
                        "provider_type": provider.provider_type,
                        "model_id": model.model_id,
                        "display_name": model.display_name,
                        "deployment_ref": deployment.deployment_ref,
                        "base_url_ref": provider_version.base_url_ref,
                        "endpoint_config": dict(provider_version.endpoint_config_json or {}),
                        "auth_type": provider_version.auth_type,
                        "deployment_type": provider_version.deployment_type,
                        "trust_level": provider_version.trust_level,
                        "data_boundary": provider_version.data_boundary,
                        "capabilities": list(caps),
                        "context_window": model.context_window,
                        "max_output_tokens": model.max_output_tokens,
                        "timeout_policy": dict(provider_version.timeout_policy_json or {}),
                        "retry_policy": dict(provider_version.retry_policy_json or {}),
                        "cost_metadata": dict(provider_version.cost_metadata_json or {}),
                        "enabled": True,
                    }
                )
            return result



class PostgresConfigRegistrySourceRepository(_TenantScopedMetadataRepository):
    def load_jurisdictions(self) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.models import JurisdictionEntity
        today = date.today()
        with self._sessions() as session:
            jurisdictions = session.scalars(
                select(JurisdictionEntity).where(
                    JurisdictionEntity.tenant_id == self.tenant_id,
                    JurisdictionEntity.status == "ACTIVE",
                    or_(JurisdictionEntity.effective_from.is_(None), JurisdictionEntity.effective_from <= today),
                    or_(JurisdictionEntity.effective_to.is_(None), JurisdictionEntity.effective_to >= today),
                ).order_by(JurisdictionEntity.code)
            ).all()
            result: list[dict[str, object]] = []
            for row in jurisdictions:
                config = session.execute(
                    select(MetadataDefinitionEntity, MetadataVersionEntity)
                    .join(
                        MetadataVersionEntity,
                        MetadataVersionEntity.version_id == MetadataDefinitionEntity.active_version_id,
                    )
                    .where(
                        MetadataDefinitionEntity.tenant_id == self.tenant_id,
                        MetadataDefinitionEntity.kind == "JURISDICTION_CONFIG",
                        MetadataDefinitionEntity.canonical_object_id == row.jurisdiction_id,
                        MetadataVersionEntity.tenant_id == self.tenant_id,
                        MetadataVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                        or_(MetadataVersionEntity.effective_from.is_(None), MetadataVersionEntity.effective_from <= today),
                        or_(MetadataVersionEntity.effective_to.is_(None), MetadataVersionEntity.effective_to >= today),
                    )
                ).first()
                if config:
                    definition, version = config
                    version_id = version.version_id
                    version_no = version.version_no
                    payload = dict(version.payload_json or {})
                else:
                    version_id = row.jurisdiction_id
                    version_no = row.record_version
                    payload = dict(row.metadata_json or {})
                result.append(
                    {
                        "definition_id": row.jurisdiction_id,
                        "version_id": version_id,
                        "version_no": version_no,
                        "code": row.code,
                        "display_name": row.name,
                        "payload": payload,
                        "effective_from": row.effective_from,
                        "effective_to": row.effective_to,
                    }
                )
            return result

    def _effective(self, model, lifecycle_column):
        today = date.today()
        return (
            model.tenant_id == self.tenant_id,
            lifecycle_column == GovernanceStatus.ACTIVE.value,
            or_(model.effective_from.is_(None), model.effective_from <= today),
            or_(model.effective_to.is_(None), model.effective_to >= today),
        )

    def load_classification_schemes(self) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.metadata_models import (
            ClassificationBindingEntity,
            ClassificationSchemeVersionEntity,
        )
        from crossborder_compliance.infrastructure.persistence.models import ClassificationSchemeEntity
        today = date.today()
        with self._sessions() as session:
            rows = session.execute(
                select(ClassificationSchemeVersionEntity, ClassificationSchemeEntity)
                .join(
                    ClassificationSchemeEntity,
                    ClassificationSchemeEntity.scheme_id == ClassificationSchemeVersionEntity.scheme_id,
                )
                .where(
                    ClassificationSchemeVersionEntity.tenant_id == self.tenant_id,
                    ClassificationSchemeEntity.tenant_id == self.tenant_id,
                    ClassificationSchemeVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    or_(ClassificationSchemeVersionEntity.effective_from.is_(None), ClassificationSchemeVersionEntity.effective_from <= today),
                    or_(ClassificationSchemeVersionEntity.effective_to.is_(None), ClassificationSchemeVersionEntity.effective_to >= today),
                )
                .order_by(ClassificationSchemeEntity.code, ClassificationSchemeVersionEntity.version_no.desc())
            ).all()
            result = []
            for version, scheme in rows:
                bindings = session.scalars(
                    select(ClassificationBindingEntity).where(
                        ClassificationBindingEntity.tenant_id == self.tenant_id,
                        ClassificationBindingEntity.scheme_version_id == version.scheme_version_id,
                        ClassificationBindingEntity.status == "ACTIVE",
                    )
                ).all()
                result.append(
                    {
                        "definition_id": scheme.scheme_id,
                        "version_id": version.scheme_version_id,
                        "version_no": version.version_no,
                        "code": scheme.code,
                        "display_name": scheme.name,
                        "applicability": dict(version.applicability_json or {}),
                        "bindings": [
                            {
                                "jurisdiction_id": row.jurisdiction_id,
                                "industry_ref": row.industry_ref,
                                "scenario_definition_id": row.scenario_definition_id,
                                "priority": row.priority,
                            }
                            for row in bindings
                        ],
                    }
                )
            return result

    def load_prompts(self) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.metadata_models import (
            PromptDefinitionEntity,
            PromptVersionEntity,
        )
        today = date.today()
        with self._sessions() as session:
            rows = session.execute(
                select(PromptDefinitionEntity, PromptVersionEntity)
                .join(PromptVersionEntity, PromptVersionEntity.prompt_version_id == PromptDefinitionEntity.active_version_id)
                .where(
                    PromptDefinitionEntity.tenant_id == self.tenant_id,
                    PromptVersionEntity.tenant_id == self.tenant_id,
                    PromptDefinitionEntity.status == "ACTIVE",
                    PromptVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    or_(PromptVersionEntity.effective_from.is_(None), PromptVersionEntity.effective_from <= today),
                    or_(PromptVersionEntity.effective_to.is_(None), PromptVersionEntity.effective_to >= today),
                )
            ).all()
            return [
                {
                    "definition_id": definition.prompt_definition_id,
                    "version_id": version.prompt_version_id,
                    "version_no": version.version_no,
                    "code": definition.code,
                    "display_name": definition.display_name,
                    "template_text": version.template_text,
                    "capability_requirement": list(version.capability_requirement_json or []),
                }
                for definition, version in rows
            ]

    def load_rules(self) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.metadata_models import (
            RuleDefinitionEntity,
            RuleVersionEntity,
        )
        today = date.today()
        with self._sessions() as session:
            rows = session.execute(
                select(RuleDefinitionEntity, RuleVersionEntity)
                .join(RuleVersionEntity, RuleVersionEntity.rule_version_id == RuleDefinitionEntity.active_version_id)
                .where(
                    RuleDefinitionEntity.tenant_id == self.tenant_id,
                    RuleVersionEntity.tenant_id == self.tenant_id,
                    RuleDefinitionEntity.status == "ACTIVE",
                    RuleVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    or_(RuleVersionEntity.effective_from.is_(None), RuleVersionEntity.effective_from <= today),
                    or_(RuleVersionEntity.effective_to.is_(None), RuleVersionEntity.effective_to >= today),
                )
            ).all()
            return [
                {
                    "definition_id": definition.rule_definition_id,
                    "version_id": version.rule_version_id,
                    "version_no": version.version_no,
                    "code": definition.code,
                    "display_name": definition.display_name,
                    "safe_dsl": dict(version.safe_dsl_json or {}),
                    "scope": dict(version.scope_json or {}),
                    "priority": version.priority,
                    "runtime_contract": version.runtime_contract_json,
                    "governance": version.governance_json,
                    "executable_v1": version.runtime_contract_json is not None,
                }
                for definition, version in rows
            ]

    def load_templates(self) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.metadata_models import (
            TemplateDefinitionEntity,
            TemplateVersionEntity,
        )
        today = date.today()
        with self._sessions() as session:
            rows = session.execute(
                select(TemplateDefinitionEntity, TemplateVersionEntity)
                .join(
                    TemplateVersionEntity,
                    TemplateVersionEntity.template_version_id == TemplateDefinitionEntity.active_version_id,
                )
                .where(
                    TemplateDefinitionEntity.tenant_id == self.tenant_id,
                    TemplateVersionEntity.tenant_id == self.tenant_id,
                    TemplateDefinitionEntity.status == "ACTIVE",
                    TemplateVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    or_(TemplateVersionEntity.effective_from.is_(None), TemplateVersionEntity.effective_from <= today),
                    or_(TemplateVersionEntity.effective_to.is_(None), TemplateVersionEntity.effective_to >= today),
                )
            ).all()
            return [
                {
                    "definition_id": definition.template_definition_id,
                    "version_id": version.template_version_id,
                    "version_no": version.version_no,
                    "code": definition.code,
                    "display_name": definition.display_name,
                    "template_type": definition.template_type,
                    "field_schema": dict(version.field_schema_json or {}),
                    "content_ref": version.content_ref,
                }
                for definition, version in rows
            ]

    def load_knowledge(self) -> list[dict[str, object]]:
        from crossborder_compliance.infrastructure.persistence.metadata_models import (
            KnowledgeCollectionEntity,
            KnowledgeCollectionVersionEntity,
        )
        today = date.today()
        with self._sessions() as session:
            rows = session.execute(
                select(KnowledgeCollectionEntity, KnowledgeCollectionVersionEntity)
                .join(
                    KnowledgeCollectionVersionEntity,
                    KnowledgeCollectionVersionEntity.knowledge_collection_version_id
                    == KnowledgeCollectionEntity.active_version_id,
                )
                .where(
                    KnowledgeCollectionEntity.tenant_id == self.tenant_id,
                    KnowledgeCollectionVersionEntity.tenant_id == self.tenant_id,
                    KnowledgeCollectionEntity.status == "ACTIVE",
                    KnowledgeCollectionVersionEntity.lifecycle_status == GovernanceStatus.ACTIVE.value,
                    or_(KnowledgeCollectionVersionEntity.effective_from.is_(None), KnowledgeCollectionVersionEntity.effective_from <= today),
                    or_(KnowledgeCollectionVersionEntity.effective_to.is_(None), KnowledgeCollectionVersionEntity.effective_to >= today),
                )
            ).all()
            return [
                {
                    "definition_id": definition.knowledge_collection_id,
                    "version_id": version.knowledge_collection_version_id,
                    "version_no": version.version_no,
                    "code": definition.code,
                    "display_name": definition.display_name,
                    "payload": dict(version.payload_json or {}),
                }
                for definition, version in rows
            ]
