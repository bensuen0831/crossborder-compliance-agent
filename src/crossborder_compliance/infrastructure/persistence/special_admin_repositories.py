from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from crossborder_compliance.application.metadata_services import (
    AdminActionPolicy,
    MetadataLifecycleError,
    lifecycle_transition_allowed,
)
from crossborder_compliance.domain.metadata import GovernanceStatus, validate_endpoint_config
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    AdminPublishRecordEntity,
    ClassificationSchemeVersionEntity,
    MetadataDefinitionEntity,
    MetadataVersionEntity,
    ModelCapabilityEntity,
    ModelDefinitionEntity,
    ModelDeploymentEntity,
    ModelProviderEntity,
    ModelProviderVersionEntity,
    RegistrySyncEventEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataOptimisticConcurrencyError,
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.models import ClassificationSchemeEntity, JurisdictionEntity
from crossborder_compliance.infrastructure.persistence.classification_governance import materialize_scheme, scheme_dates, validate_scheme


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostgresClassificationAdminRepository:
    def __init__(self, session_factory: sessionmaker, context: RepositoryContext):
        self._sessions = session_factory
        self._context = context
        self._policy = AdminActionPolicy()

    @property
    def tenant_id(self) -> str:
        return str(self._context.tenant_id)

    def create_draft(self, *, code: str, display_name: str, payload: dict[str, object]) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        scheme_id = str(uuid4())
        version_id = str(uuid4())
        with self._sessions() as session, session.begin():
            session.add(
                ClassificationSchemeEntity(
                    scheme_id=scheme_id,
                    tenant_id=self.tenant_id,
                    code=code,
                    name=display_name,
                    record_version=1,
                    status="ACTIVE",
                )
            )
            session.flush()
            version = ClassificationSchemeVersionEntity(
                    scheme_version_id=version_id,
                    tenant_id=self.tenant_id,
                    scheme_id=scheme_id,
                    version_no=1,
                    lifecycle_status=GovernanceStatus.DRAFT.value,
                    applicability_json=dict(payload.get("applicability", {})),
                    status="ACTIVE",
                )
            session.add(version)
            scheme_dates(version, payload)
            session.flush()
            materialize_scheme(session, version)
        return {
            "definition_id": scheme_id,
            "version_id": version_id,
            "version_no": 1,
            "lifecycle_status": GovernanceStatus.DRAFT.value,
            "record_version": 1,
        }

    def update_draft(self, version_id: UUID, *, payload: dict[str, object], expected_record_version: int) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        with self._sessions() as session, session.begin():
            row = session.scalar(
                select(ClassificationSchemeVersionEntity).where(
                    ClassificationSchemeVersionEntity.scheme_version_id == str(version_id),
                    ClassificationSchemeVersionEntity.tenant_id == self.tenant_id,
                )
            )
            if row is None:
                raise LookupError("classification scheme version not found")
            if row.lifecycle_status != GovernanceStatus.DRAFT.value:
                raise MetadataLifecycleError("only DRAFT classification scheme can be updated")
            if row.record_version != expected_record_version:
                raise MetadataOptimisticConcurrencyError("classification scheme version changed")
            row.applicability_json = dict(payload.get("applicability", {}))
            scheme_dates(row, payload)
            materialize_scheme(session, row)
            row.record_version += 1
            row.updated_at = utcnow()
        return self.get_version(version_id)

    def transition(self, version_id: UUID, *, target_status: str, expected_record_version: int) -> dict[str, object]:
        required = (
            self._policy.review_scope
            if target_status in {GovernanceStatus.APPROVED.value, GovernanceStatus.DRAFT.value}
            else self._policy.publish_scope
            if target_status in {
                GovernanceStatus.ACTIVE.value,
                GovernanceStatus.SUPERSEDED.value,
                GovernanceStatus.EXPIRED.value,
                GovernanceStatus.ARCHIVED.value,
            }
            else self._policy.draft_scope
        )
        self._policy.require(self._context, required)
        with self._sessions() as session, session.begin():
            row = session.scalar(
                select(ClassificationSchemeVersionEntity).where(
                    ClassificationSchemeVersionEntity.scheme_version_id == str(version_id),
                    ClassificationSchemeVersionEntity.tenant_id == self.tenant_id,
                )
                .with_for_update()
            )
            if row is None:
                raise LookupError("classification scheme version not found")
            if row.record_version != expected_record_version:
                raise MetadataOptimisticConcurrencyError("classification scheme version changed")
            if not lifecycle_transition_allowed(row.lifecycle_status, target_status):
                raise MetadataLifecycleError(
                    f"invalid lifecycle transition: {row.lifecycle_status} -> {target_status}"
                )
            validate_scheme(row)
            row.lifecycle_status = target_status
            row.record_version += 1
            row.updated_at = utcnow()
            if target_status == GovernanceStatus.ACTIVE.value:
                if row.applicability_json.get("phase1h"):
                    # A canonical scheme has one current V1 generation; historic pins remain valid.
                    scheme = session.scalar(select(ClassificationSchemeEntity).where(
                        ClassificationSchemeEntity.tenant_id == self.tenant_id,
                        ClassificationSchemeEntity.scheme_id == row.scheme_id).with_for_update())
                    if scheme is None:
                        raise LookupError("classification scheme not found")
                    old_versions = session.scalars(select(ClassificationSchemeVersionEntity).where(
                        ClassificationSchemeVersionEntity.tenant_id == self.tenant_id,
                        ClassificationSchemeVersionEntity.scheme_id == row.scheme_id,
                        ClassificationSchemeVersionEntity.scheme_version_id != row.scheme_version_id,
                        ClassificationSchemeVersionEntity.lifecycle_status == "ACTIVE")).all()
                    for old in old_versions:
                        old.lifecycle_status = "SUPERSEDED"
                        old.record_version += 1
                session.add(
                    AdminPublishRecordEntity(
                        publish_record_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind="CLASSIFICATION",
                        version_id=row.scheme_version_id,
                        published_by=self._context.permission.actor_id,
                        published_at=utcnow(),
                        status="ACTIVE",
                    )
                )
                session.add(
                    RegistrySyncEventEntity(
                        registry_sync_event_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind="CLASSIFICATION",
                        object_id=row.scheme_id,
                        version_id=row.scheme_version_id,
                        event_version=row.version_no,
                        attempts=0,
                        status="PENDING",
                    )
                )
        return self.get_version(version_id)

    def create_version(self, scheme_id: UUID, *, payload: dict[str, object]) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        if not payload.get("applicability", {}).get("phase1h"):
            raise ValueError("new classification version requires Phase 1H membership")
        with self._sessions() as session, session.begin():
            scheme = session.scalar(select(ClassificationSchemeEntity).where(
                ClassificationSchemeEntity.scheme_id == str(scheme_id),
                ClassificationSchemeEntity.tenant_id == self.tenant_id).with_for_update())
            if scheme is None:
                raise LookupError("classification scheme not found")
            number = (session.scalar(select(func.max(ClassificationSchemeVersionEntity.version_no)).where(
                ClassificationSchemeVersionEntity.tenant_id == self.tenant_id,
                ClassificationSchemeVersionEntity.scheme_id == str(scheme_id))) or 0) + 1
            version = ClassificationSchemeVersionEntity(scheme_version_id=str(uuid4()),
                tenant_id=self.tenant_id, scheme_id=str(scheme_id), version_no=number,
                lifecycle_status="DRAFT", applicability_json=dict(payload["applicability"]))
            scheme_dates(version, payload)
            session.add(version)
            session.flush()
            materialize_scheme(session, version)
            ident = UUID(version.scheme_version_id)
        return self.get_version(ident)

    def get_version(self, version_id: UUID) -> dict[str, object]:
        with self._sessions() as session:
            row = session.scalar(
                select(ClassificationSchemeVersionEntity).where(
                    ClassificationSchemeVersionEntity.scheme_version_id == str(version_id),
                    ClassificationSchemeVersionEntity.tenant_id == self.tenant_id,
                )
            )
            if row is None:
                raise LookupError("classification scheme version not found")
            return {
                "definition_id": row.scheme_id,
                "version_id": row.scheme_version_id,
                "version_no": row.version_no,
                "lifecycle_status": row.lifecycle_status,
                "record_version": row.record_version,
            }

    def get_detail(self, version_id: UUID) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        result = self.get_version(version_id)
        with self._sessions() as session:
            row = session.scalar(select(ClassificationSchemeVersionEntity).where(
                ClassificationSchemeVersionEntity.scheme_version_id == str(version_id),
                ClassificationSchemeVersionEntity.tenant_id == self.tenant_id))
            return {**result, "applicability": row.applicability_json}

    def history(self, definition_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ClassificationSchemeVersionEntity)
                .where(
                    ClassificationSchemeVersionEntity.tenant_id == self.tenant_id,
                    ClassificationSchemeVersionEntity.scheme_id == str(definition_id),
                )
                .order_by(ClassificationSchemeVersionEntity.version_no.desc())
            ).all()
            return [
                {
                    "definition_id": row.scheme_id,
                    "version_id": row.scheme_version_id,
                    "version_no": row.version_no,
                    "lifecycle_status": row.lifecycle_status,
                    "record_version": row.record_version,
                }
                for row in rows
            ]

    def impact_preview(self, definition_id: UUID) -> dict[str, object]:
        return {
            "definition_id": str(definition_id),
            "object_kind": "CLASSIFICATION",
            "registry_refresh_required": True,
            "requires_root_graph_change": False,
        }


class PostgresModelAdminRepository:
    """Model config governance. Responses never expose secret_ref."""

    def __init__(self, session_factory: sessionmaker, context: RepositoryContext):
        self._sessions = session_factory
        self._context = context
        self._policy = AdminActionPolicy()

    @property
    def tenant_id(self) -> str:
        return str(self._context.tenant_id)

    def create_draft(self, *, code: str, display_name: str, payload: dict[str, object]) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        endpoint_config = dict(payload.get("endpoint_config", {}))
        validate_endpoint_config(endpoint_config)
        provider_id = str(uuid4())
        provider_version_id = str(uuid4())
        model_definition_id = str(uuid4())
        deployment_id = str(uuid4())
        with self._sessions() as session, session.begin():
            session.add(
                ModelProviderEntity(
                    provider_id=provider_id,
                    tenant_id=self.tenant_id,
                    provider_type=str(payload.get("provider_type", "GENERIC_REST")),
                    code=f"{code}-provider",
                    display_name=f"{display_name} Provider",
                    active_version_id=None,
                    enabled=bool(payload.get("enabled", True)),
                    status="ACTIVE",
                )
            )
            session.flush()
            session.add(
                ModelProviderVersionEntity(
                    provider_version_id=provider_version_id,
                    tenant_id=self.tenant_id,
                    provider_id=provider_id,
                    version_no=1,
                    lifecycle_status=GovernanceStatus.DRAFT.value,
                    base_url_ref=payload.get("base_url_ref"),
                    endpoint_config_json=endpoint_config,
                    auth_type=str(payload.get("auth_type", "NONE")),
                    secret_ref=payload.get("secret_ref"),
                    deployment_type=str(payload.get("deployment_type", "API")),
                    trust_level=str(payload.get("trust_level", "UNSPECIFIED")),
                    data_boundary=str(payload.get("data_boundary", "UNSPECIFIED")),
                    timeout_policy_json=dict(payload.get("timeout_policy", {})),
                    retry_policy_json=dict(payload.get("retry_policy", {})),
                    cost_metadata_json=dict(payload.get("cost_metadata", {})),
                    enabled=bool(payload.get("enabled", True)),
                    status="ACTIVE",
                )
            )
            session.add(
                ModelDefinitionEntity(
                    model_definition_id=model_definition_id,
                    tenant_id=self.tenant_id,
                    provider_id=provider_id,
                    model_id=str(payload.get("model_id", code)),
                    display_name=display_name,
                    context_window=payload.get("context_window"),
                    max_output_tokens=payload.get("max_output_tokens"),
                    active_deployment_id=None,
                    enabled=bool(payload.get("enabled", True)),
                    status="ACTIVE",
                )
            )
            session.flush()
            session.add(
                ModelDeploymentEntity(
                    model_deployment_id=deployment_id,
                    tenant_id=self.tenant_id,
                    model_definition_id=model_definition_id,
                    provider_version_id=provider_version_id,
                    deployment_ref=str(payload.get("deployment_ref", "default")),
                    lifecycle_status=GovernanceStatus.DRAFT.value,
                    enabled=bool(payload.get("enabled", True)),
                    status="ACTIVE",
                )
            )
            for cap in payload.get("capabilities", []):
                session.add(
                    ModelCapabilityEntity(
                        model_capability_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        model_definition_id=model_definition_id,
                        capability=str(cap),
                        metadata_json={},
                        status="ACTIVE",
                    )
                )
        return {
            "definition_id": model_definition_id,
            "version_id": deployment_id,
            "provider_id": provider_id,
            "provider_version_id": provider_version_id,
            "version_no": 1,
            "lifecycle_status": GovernanceStatus.DRAFT.value,
            "record_version": 1,
        }

    def update_draft(self, version_id: UUID, *, payload: dict[str, object], expected_record_version: int) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        validate_endpoint_config(dict(payload.get("endpoint_config", {})))
        with self._sessions() as session, session.begin():
            deployment = session.scalar(
                select(ModelDeploymentEntity).where(
                    ModelDeploymentEntity.model_deployment_id == str(version_id),
                    ModelDeploymentEntity.tenant_id == self.tenant_id,
                )
            )
            if deployment is None:
                raise LookupError("model deployment not found")
            if deployment.lifecycle_status != GovernanceStatus.DRAFT.value:
                raise MetadataLifecycleError("only DRAFT model deployment can be updated")
            if deployment.record_version != expected_record_version:
                raise MetadataOptimisticConcurrencyError("model deployment changed")
            provider_version = session.scalar(
                select(ModelProviderVersionEntity).where(
                    ModelProviderVersionEntity.provider_version_id == deployment.provider_version_id,
                    ModelProviderVersionEntity.tenant_id == self.tenant_id,
                )
            )
            if provider_version is None:
                raise LookupError("model provider version not found")
            if "endpoint_config" in payload:
                provider_version.endpoint_config_json = dict(payload["endpoint_config"])
            if "base_url_ref" in payload:
                provider_version.base_url_ref = payload["base_url_ref"]
            if "secret_ref" in payload:
                provider_version.secret_ref = payload["secret_ref"]
            deployment.record_version += 1
            deployment.updated_at = utcnow()
        return self.get_version(version_id)

    def transition(self, version_id: UUID, *, target_status: str, expected_record_version: int) -> dict[str, object]:
        required = (
            self._policy.review_scope
            if target_status in {GovernanceStatus.APPROVED.value, GovernanceStatus.DRAFT.value}
            else self._policy.publish_scope
            if target_status in {
                GovernanceStatus.ACTIVE.value,
                GovernanceStatus.SUPERSEDED.value,
                GovernanceStatus.EXPIRED.value,
                GovernanceStatus.ARCHIVED.value,
            }
            else self._policy.draft_scope
        )
        self._policy.require(self._context, required)
        with self._sessions() as session, session.begin():
            deployment = session.scalar(
                select(ModelDeploymentEntity).where(
                    ModelDeploymentEntity.model_deployment_id == str(version_id),
                    ModelDeploymentEntity.tenant_id == self.tenant_id,
                )
            )
            if deployment is None:
                raise LookupError("model deployment not found")
            if deployment.record_version != expected_record_version:
                raise MetadataOptimisticConcurrencyError("model deployment changed")
            if not lifecycle_transition_allowed(deployment.lifecycle_status, target_status):
                raise MetadataLifecycleError(
                    f"invalid lifecycle transition: {deployment.lifecycle_status} -> {target_status}"
                )
            provider_version = session.scalar(
                select(ModelProviderVersionEntity).where(
                    ModelProviderVersionEntity.provider_version_id == deployment.provider_version_id,
                    ModelProviderVersionEntity.tenant_id == self.tenant_id,
                )
            )
            model = session.scalar(
                select(ModelDefinitionEntity).where(
                    ModelDefinitionEntity.model_definition_id == deployment.model_definition_id,
                    ModelDefinitionEntity.tenant_id == self.tenant_id,
                )
            )
            provider = session.scalar(
                select(ModelProviderEntity).where(
                    ModelProviderEntity.provider_id == model.provider_id,
                    ModelProviderEntity.tenant_id == self.tenant_id,
                )
            ) if model else None
            if provider_version is None or model is None or provider is None:
                raise LookupError("model config graph incomplete")
            deployment.lifecycle_status = target_status
            provider_version.lifecycle_status = target_status
            deployment.record_version += 1
            provider_version.record_version += 1
            deployment.updated_at = utcnow()
            provider_version.updated_at = utcnow()
            if target_status == GovernanceStatus.ACTIVE.value:
                provider.active_version_id = provider_version.provider_version_id
                model.active_deployment_id = deployment.model_deployment_id
                provider.record_version += 1
                model.record_version += 1
                session.add(
                    AdminPublishRecordEntity(
                        publish_record_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind="MODEL",
                        version_id=deployment.model_deployment_id,
                        published_by=self._context.permission.actor_id,
                        published_at=utcnow(),
                        status="ACTIVE",
                    )
                )
                session.add(
                    RegistrySyncEventEntity(
                        registry_sync_event_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind="MODEL",
                        object_id=model.model_definition_id,
                        version_id=deployment.model_deployment_id,
                        event_version=deployment.record_version,
                        attempts=0,
                        status="PENDING",
                    )
                )
        return self.get_version(version_id)

    def get_version(self, version_id: UUID) -> dict[str, object]:
        with self._sessions() as session:
            deployment = session.scalar(
                select(ModelDeploymentEntity).where(
                    ModelDeploymentEntity.model_deployment_id == str(version_id),
                    ModelDeploymentEntity.tenant_id == self.tenant_id,
                )
            )
            if deployment is None:
                raise LookupError("model deployment not found")
            model = session.scalar(
                select(ModelDefinitionEntity).where(
                    ModelDefinitionEntity.model_definition_id == deployment.model_definition_id,
                    ModelDefinitionEntity.tenant_id == self.tenant_id,
                )
            )
            return {
                "definition_id": deployment.model_definition_id,
                "version_id": deployment.model_deployment_id,
                "provider_version_id": deployment.provider_version_id,
                "version_no": 1,
                "lifecycle_status": deployment.lifecycle_status,
                "record_version": deployment.record_version,
                "model_id": model.model_id if model else None,
                "display_name": model.display_name if model else None,
            }

    def history(self, definition_id: UUID) -> list[dict[str, object]]:
        with self._sessions() as session:
            rows = session.scalars(
                select(ModelDeploymentEntity).where(
                    ModelDeploymentEntity.tenant_id == self.tenant_id,
                    ModelDeploymentEntity.model_definition_id == str(definition_id),
                )
            ).all()
            return [
                {
                    "definition_id": row.model_definition_id,
                    "version_id": row.model_deployment_id,
                    "lifecycle_status": row.lifecycle_status,
                    "record_version": row.record_version,
                }
                for row in rows
            ]

    def impact_preview(self, definition_id: UUID) -> dict[str, object]:
        return {
            "definition_id": str(definition_id),
            "object_kind": "MODEL",
            "model_replacement_requires_agent_change": False,
            "requires_root_graph_change": False,
            "registry_refresh_required": True,
        }



class PostgresJurisdictionAdminRepository:
    """Canonical Jurisdiction identity + immutable versioned config overlay."""

    def __init__(self, session_factory: sessionmaker, context: RepositoryContext):
        self._sessions = session_factory
        self._context = context
        self._policy = AdminActionPolicy()
        self._config_repo = PostgresAdminMetadataRepository(session_factory, context)

    @property
    def tenant_id(self) -> str:
        return str(self._context.tenant_id)

    def create_draft(self, *, code: str, display_name: str, payload: dict[str, object]) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        from crossborder_compliance.domain.localized_metadata import (
            validate_localized_payload, validate_stable_metadata_code,
        )
        validate_stable_metadata_code(code)
        validate_localized_payload(payload)
        jurisdiction_id = str(uuid4())
        definition_id = str(uuid4())
        version_id = str(uuid4())
        with self._sessions() as session, session.begin():
            session.add(
                JurisdictionEntity(
                    jurisdiction_id=jurisdiction_id,
                    tenant_id=self.tenant_id,
                    code=code,
                    name=display_name,
                    metadata_json={},
                    status=GovernanceStatus.DRAFT.value,
                    record_version=1,
                )
            )
            session.add(
                MetadataDefinitionEntity(
                    definition_id=definition_id,
                    tenant_id=self.tenant_id,
                    kind="JURISDICTION_CONFIG",
                    code=code,
                    display_name=display_name,
                    canonical_object_type="JURISDICTION_CONFIG",
                    canonical_object_id=jurisdiction_id,
                    active_version_id=None,
                    status="ACTIVE",
                    record_version=1,
                )
            )
            session.flush()
            session.add(
                MetadataVersionEntity(
                    version_id=version_id,
                    tenant_id=self.tenant_id,
                    definition_id=definition_id,
                    version_no=1,
                    lifecycle_status=GovernanceStatus.DRAFT.value,
                    payload_json=dict(payload),
                    created_by=self._context.permission.actor_id,
                    status="ACTIVE",
                    record_version=1,
                )
            )
        return {
            "definition_id": jurisdiction_id,
            "config_definition_id": definition_id,
            "version_id": version_id,
            "version_no": 1,
            "lifecycle_status": GovernanceStatus.DRAFT.value,
            "record_version": 1,
        }

    def _config_definition(self, jurisdiction_id: UUID):
        with self._sessions() as session:
            return session.scalar(
                select(MetadataDefinitionEntity).where(
                    MetadataDefinitionEntity.tenant_id == self.tenant_id,
                    MetadataDefinitionEntity.kind == "JURISDICTION_CONFIG",
                    MetadataDefinitionEntity.canonical_object_id == str(jurisdiction_id),
                )
            )

    def update_draft(self, version_id: UUID, *, payload: dict[str, object], expected_record_version: int) -> dict[str, object]:
        self._policy.require(self._context, self._policy.draft_scope)
        return self._config_repo.update_draft(
            version_id, payload=payload, expected_record_version=expected_record_version
        )

    def transition(self, version_id: UUID, *, target_status: str, expected_record_version: int) -> dict[str, object]:
        result = self._config_repo.transition(
            version_id,
            target_status=target_status,
            actor_id=self._context.permission.actor_id,
            expected_record_version=expected_record_version,
        )
        with self._sessions() as session, session.begin():
            definition = session.scalar(
                select(MetadataDefinitionEntity).where(
                    MetadataDefinitionEntity.definition_id == str(result["definition_id"]),
                    MetadataDefinitionEntity.tenant_id == self.tenant_id,
                )
            )
            if definition is None or not definition.canonical_object_id:
                raise LookupError("jurisdiction config definition missing")
            jurisdiction = session.scalar(
                select(JurisdictionEntity).where(
                    JurisdictionEntity.jurisdiction_id == definition.canonical_object_id,
                    JurisdictionEntity.tenant_id == self.tenant_id,
                )
            )
            if jurisdiction is None:
                raise LookupError("canonical jurisdiction missing")
            if target_status == GovernanceStatus.ACTIVE.value:
                jurisdiction.status = "ACTIVE"
            elif target_status in {
                GovernanceStatus.ARCHIVED.value,
                GovernanceStatus.EXPIRED.value,
            }:
                jurisdiction.status = target_status
            jurisdiction.record_version += 1
            jurisdiction.updated_at = utcnow()
        result["definition_id"] = definition.canonical_object_id
        result["config_definition_id"] = definition.definition_id
        return result

    def history(self, jurisdiction_id: UUID) -> list[dict[str, object]]:
        definition = self._config_definition(jurisdiction_id)
        if definition is None:
            return []
        return self._config_repo.history(UUID(definition.definition_id))

    def impact_preview(self, jurisdiction_id: UUID) -> dict[str, object]:
        return {
            "definition_id": str(jurisdiction_id),
            "object_kind": "JURISDICTION_CONFIG",
            "registry_refresh_required": True,
            "existing_snapshot_switch": False,
        }
