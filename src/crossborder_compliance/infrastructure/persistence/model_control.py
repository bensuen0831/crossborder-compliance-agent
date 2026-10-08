"""Independent control commands over the existing Phase1C provider/model tables."""

from uuid import uuid4

from sqlalchemy import func, select

from crossborder_compliance.application.metadata_services import (
    AdminActionPolicy,
    MetadataLifecycleError,
    lifecycle_transition_allowed,
)
from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.infrastructure.llm_gateway_configuration import ProviderConnection
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataOptimisticConcurrencyError,
)


class PostgresModelControlRepository:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant = str(context.tenant_id)
        self.policy = AdminActionPolicy()

    def _row(self, session, cls, identity, lock=False):
        query = select(cls).where(
            cls.tenant_id == self.tenant,
            list(cls.__table__.primary_key)[0] == str(identity),
        )
        row = session.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        return row

    @staticmethod
    def _expected(row, expected):
        if expected is None or row.record_version != expected:
            raise MetadataOptimisticConcurrencyError("MODEL_CONFIGURATION_CONFLICT")

    def require_provider(self, identity, expected=None):
        with self.sessions() as s:
            row = self._row(s, m.ModelProviderEntity, identity)
            if expected is not None:
                self._expected(row, expected)
            return row

    def probe_connection(self, provider_version_id):
        self.policy.require(self.context, "metadata:admin")
        with self.sessions() as s:
            version = self._row(s, m.ModelProviderVersionEntity, provider_version_id)
            provider = self._row(s, m.ModelProviderEntity, version.provider_id)
            if not provider.enabled or not version.enabled or version.status != "ACTIVE":
                raise GatewayDenied("PROVIDER_DISABLED")
            return provider.provider_type, ProviderConnection(
                model_name="",
                endpoint=dict(version.endpoint_config_json),
                secret_ref=version.secret_ref,
                auth_type=version.auth_type,
                timeout_policy=dict(version.timeout_policy_json),
                retry_policy=dict(version.retry_policy_json),
                external=version.deployment_type not in {"PRIVATE_CLOUD", "ON_PREMISE"},
            )

    def record_health(self, deployment_id, status):
        self.policy.require(self.context, "metadata:admin")
        with self.sessions() as s, s.begin():
            self._row(s, m.ModelDeploymentEntity, deployment_id)
            s.add(
                m.ModelHealthMetadataEntity(
                    model_health_metadata_id=str(uuid4()),
                    tenant_id=self.tenant,
                    model_deployment_id=str(deployment_id),
                    health_status="HEALTHY" if status == "HEALTHY" else "UNHEALTHY",
                    detail_json={
                        "actor_id": self.context.permission.actor_id,
                        "status_code": status,
                    },
                )
            )

    def list_providers(self):
        self.policy.require(self.context, "metadata:admin")
        with self.sessions() as s:
            rows = s.scalars(
                select(m.ModelProviderEntity).where(m.ModelProviderEntity.tenant_id == self.tenant)
            ).all()
            result = []
            for row in rows:
                versions = s.scalars(
                    select(m.ModelProviderVersionEntity)
                    .where(
                        m.ModelProviderVersionEntity.tenant_id == self.tenant,
                        m.ModelProviderVersionEntity.provider_id == row.provider_id,
                    )
                    .order_by(m.ModelProviderVersionEntity.version_no.desc())
                ).all()
                result.append(
                    dict(
                        provider_id=row.provider_id,
                        code=row.code,
                        display_name=row.display_name,
                        enabled=row.enabled,
                        record_version=row.record_version,
                        active_version_id=row.active_version_id,
                        versions=[self._provider_view(row, v) for v in versions],
                    )
                )
            return result

    @staticmethod
    def _provider_view(provider, version):
        config = version.endpoint_config_json or {}
        return dict(
            provider_id=provider.provider_id,
            provider_version_id=version.provider_version_id,
            provider_version=version.version_no,
            display_name=provider.display_name,
            vendor_preset=config.get("vendor_preset", "OTHER_OPENAI_COMPATIBLE"),
            protocol=provider.provider_type,
            base_url=config.get("url"),
            deployment_class=version.deployment_type,
            trust_level=version.trust_level,
            data_boundary=version.data_boundary,
            secret_configured=bool(version.secret_ref),
            enabled=provider.enabled and version.enabled,
            lifecycle_status=version.lifecycle_status,
            record_version=version.record_version,
            effective_from=version.effective_from,
            effective_to=version.effective_to,
        )

    def save_provider(self, request, secret_ref):
        self.policy.require(self.context, "metadata:admin")
        if request.effective_to and request.effective_to < request.effective_from:
            raise ValueError("PROVIDER_EFFECTIVE_RANGE_INVALID")
        with self.sessions() as s, s.begin():
            if request.provider_id:
                row = self._row(s, m.ModelProviderEntity, request.provider_id, True)
                self._expected(row, request.expected_record_version)
                if row.provider_type != request.protocol:
                    raise ValueError("PROVIDER_PROTOCOL_IDENTITY_IMMUTABLE")
                row.display_name = request.display_name
                row.record_version += 1
                prior = (
                    s.get(m.ModelProviderVersionEntity, row.active_version_id)
                    if row.active_version_id
                    else None
                )
                if secret_ref is None and prior:
                    secret_ref = prior.secret_ref
            else:
                row = m.ModelProviderEntity(
                    provider_id=str(uuid4()),
                    tenant_id=self.tenant,
                    code=request.code,
                    display_name=request.display_name,
                    provider_type=request.protocol,
                )
                s.add(row)
                s.flush()
            number = (
                s.scalar(
                    select(func.max(m.ModelProviderVersionEntity.version_no)).where(
                        m.ModelProviderVersionEntity.tenant_id == self.tenant,
                        m.ModelProviderVersionEntity.provider_id == row.provider_id,
                    )
                )
                or 0
            ) + 1
            version = m.ModelProviderVersionEntity(
                provider_version_id=str(uuid4()),
                provider_id=row.provider_id,
                tenant_id=self.tenant,
                version_no=number,
                lifecycle_status="DRAFT",
                effective_from=request.effective_from,
                effective_to=request.effective_to,
                endpoint_config_json={
                    "url": request.base_url,
                    "vendor_preset": request.vendor_preset,
                    "health_ttl_seconds": request.health_ttl_seconds,
                    "governance": {"created_by": self.context.permission.actor_id},
                },
                auth_type="BEARER_SECRET_REF" if secret_ref else "NONE",
                secret_ref=secret_ref,
                deployment_type=request.deployment_class,
                trust_level=request.trust_level,
                data_boundary=request.data_boundary,
                timeout_policy_json={"seconds": request.timeout_seconds},
                retry_policy_json={"max_attempts": 1},
            )
            s.add(version)
            s.flush()
            return self._provider_view(row, version)

    def list_models(self, provider_id):
        self.policy.require(self.context, "metadata:admin")
        with self.sessions() as s:
            self._row(s, m.ModelProviderEntity, provider_id)
            pairs = s.execute(
                select(m.ModelDefinitionEntity, m.ModelDeploymentEntity)
                .join(
                    m.ModelDeploymentEntity,
                    m.ModelDeploymentEntity.model_definition_id
                    == m.ModelDefinitionEntity.model_definition_id,
                )
                .where(
                    m.ModelDefinitionEntity.tenant_id == self.tenant,
                    m.ModelDeploymentEntity.tenant_id == self.tenant,
                    m.ModelDefinitionEntity.provider_id == str(provider_id),
                )
            ).all()
            return [self._model_view(s, model, deployment) for model, deployment in pairs]

    def _model_view(self, s, model, deployment):
        health = s.scalar(
            select(m.ModelHealthMetadataEntity)
            .where(
                m.ModelHealthMetadataEntity.tenant_id == self.tenant,
                m.ModelHealthMetadataEntity.model_deployment_id == deployment.model_deployment_id,
            )
            .order_by(m.ModelHealthMetadataEntity.observed_at.desc())
            .limit(1)
        )
        return dict(
            model_id=model.model_definition_id,
            provider_id=model.provider_id,
            deployment_id=deployment.model_deployment_id,
            provider_version_id=deployment.provider_version_id,
            display_name=deployment.configuration_json.get("display_name", model.display_name),
            **{k: v for k, v in deployment.configuration_json.items() if k != "display_name"},
            enabled=model.enabled and deployment.enabled,
            lifecycle_status=deployment.lifecycle_status,
            record_version=deployment.record_version,
            model_record_version=model.record_version,
            health_status=health.health_status if health else "UNKNOWN",
        )

    def save_model(self, provider_id, request):
        self.policy.require(self.context, "metadata:admin")
        if request.effective_to and request.effective_to < request.effective_from:
            raise ValueError("MODEL_EFFECTIVE_RANGE_INVALID")
        with self.sessions() as s, s.begin():
            self._row(s, m.ModelProviderEntity, provider_id)
            provider_version = self._row(
                s, m.ModelProviderVersionEntity, request.provider_version_id
            )
            if (
                provider_version.provider_id != str(provider_id)
                or provider_version.lifecycle_status != "ACTIVE"
            ):
                raise GatewayDenied("PUBLISHED_PROVIDER_REQUIRED")
            if request.model_id:
                model = self._row(s, m.ModelDefinitionEntity, request.model_id, True)
                self._expected(model, request.expected_record_version)
                if (
                    model.provider_id != str(provider_id)
                    or model.model_id != request.remote_model_name
                ):
                    raise GatewayDenied("MODEL_IDENTITY_IMMUTABLE")
                model.record_version += 1
            else:
                model = m.ModelDefinitionEntity(
                    model_definition_id=str(uuid4()),
                    tenant_id=self.tenant,
                    provider_id=str(provider_id),
                    model_id=request.remote_model_name,
                    display_name=request.display_name,
                    max_output_tokens=request.max_output_tokens,
                )
                s.add(model)
                s.flush()
            config = request.model_dump(
                mode="json",
                exclude={
                    "model_id",
                    "expected_record_version",
                    "provider_version_id",
                    "effective_from",
                    "effective_to",
                },
            )
            config["governance"] = {"created_by": self.context.permission.actor_id}
            deployment = m.ModelDeploymentEntity(
                model_deployment_id=str(uuid4()),
                tenant_id=self.tenant,
                model_definition_id=model.model_definition_id,
                provider_version_id=str(request.provider_version_id),
                deployment_ref=str(uuid4()),
                lifecycle_status="DRAFT",
                configuration_json=config,
                effective_from=request.effective_from,
                effective_to=request.effective_to,
            )
            s.add(deployment)
            # Existing registry projection; deployment owns runtime semantics.
            for capability in request.capabilities:
                if not s.scalar(
                    select(m.ModelCapabilityEntity).where(
                        m.ModelCapabilityEntity.tenant_id == self.tenant,
                        m.ModelCapabilityEntity.model_definition_id == model.model_definition_id,
                        m.ModelCapabilityEntity.capability == capability.value,
                    )
                ):
                    s.add(
                        m.ModelCapabilityEntity(
                            model_capability_id=str(uuid4()),
                            tenant_id=self.tenant,
                            model_definition_id=model.model_definition_id,
                            capability=capability.value,
                            metadata_json={"embedding_dimension": request.embedding_dimension}
                            if capability.value == "EMBEDDING"
                            else {},
                        )
                    )
            s.flush()
            return self._model_view(s, model, deployment)

    def transition(self, kind, version_id, request):
        if kind not in {"PROVIDER", "MODEL"}:
            raise ValueError("MODEL_CONTROL_KIND_INVALID")
        target = request.target_status.value
        required = (
            "metadata:review"
            if target in {"APPROVED", "DRAFT"}
            else "metadata:admin"
            if target == "PENDING_REVIEW"
            else "metadata:publish"
        )
        self.policy.require(self.context, required)
        cls = m.ModelProviderVersionEntity if kind == "PROVIDER" else m.ModelDeploymentEntity
        with self.sessions() as s, s.begin():
            row = self._row(s, cls, version_id, True)
            self._expected(row, request.expected_record_version)
            if not lifecycle_transition_allowed(row.lifecycle_status, target):
                raise MetadataLifecycleError("INVALID_MODEL_GOVERNANCE_TRANSITION")
            config = dict(
                row.endpoint_config_json if kind == "PROVIDER" else row.configuration_json
            )
            governance = dict(config.get("governance", {}))
            if target == "APPROVED":
                if governance.get("created_by") == self.context.permission.actor_id:
                    raise GatewayDenied("INDEPENDENT_REVIEW_REQUIRED")
                governance["approved_by"] = self.context.permission.actor_id
                config["governance"] = governance
                if kind == "PROVIDER":
                    row.endpoint_config_json = config
                else:
                    row.configuration_json = config
            if target == "ACTIVE" and not governance.get("approved_by"):
                raise GatewayDenied("REVIEW_APPROVAL_REQUIRED")
            row.lifecycle_status = target
            row.record_version += 1
            if kind == "PROVIDER":
                identity = self._row(s, m.ModelProviderEntity, row.provider_id, True)
            else:
                identity = self._row(s, m.ModelDefinitionEntity, row.model_definition_id, True)
            if target == "ACTIVE":
                prior_id = (
                    identity.active_version_id
                    if kind == "PROVIDER"
                    else identity.active_deployment_id
                )
                if prior_id:
                    prior = self._row(s, cls, prior_id)
                    if prior.lifecycle_status == "ACTIVE":
                        prior.lifecycle_status = "SUPERSEDED"
                if kind == "PROVIDER":
                    identity.active_version_id = str(version_id)
                else:
                    identity.active_deployment_id = str(version_id)
                identity.record_version += 1
                s.add(
                    m.AdminPublishRecordEntity(
                        publish_record_id=str(uuid4()),
                        tenant_id=self.tenant,
                        object_kind=kind,
                        version_id=str(version_id),
                        published_by=self.context.permission.actor_id,
                    )
                )
                s.add(
                    m.RegistrySyncEventEntity(
                        registry_sync_event_id=str(uuid4()),
                        tenant_id=self.tenant,
                        object_kind=kind,
                        object_id=identity.provider_id
                        if kind == "PROVIDER"
                        else identity.model_definition_id,
                        version_id=str(version_id),
                        event_version=row.record_version,
                        attempts=0,
                        status="PENDING",
                    )
                )
            s.flush()
            return (
                self._provider_view(identity, row)
                if kind == "PROVIDER"
                else self._model_view(s, identity, row)
            )

    def set_enabled(self, kind, identity, enabled, expected_version):
        self.policy.require(self.context, "metadata:admin")
        cls = (
            m.ModelProviderEntity
            if kind == "PROVIDER"
            else m.ModelDefinitionEntity
            if kind == "MODEL"
            else None
        )
        if cls is None:
            raise ValueError("MODEL_CONTROL_KIND_INVALID")
        with self.sessions() as s, s.begin():
            row = self._row(s, cls, identity, True)
            self._expected(row, expected_version)
            row.enabled = enabled
            row.record_version += 1
            return {"enabled": row.enabled, "record_version": row.record_version}
