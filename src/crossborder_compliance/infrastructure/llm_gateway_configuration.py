"""Extend Phase 1C readers/pins; no registry, lifecycle or schema is duplicated."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from crossborder_compliance.application.llm_gateway_policy import required_capabilities
from crossborder_compliance.domain.llm_gateway import (
    GatewayDenied,
    ModelCandidate,
    ModelUsagePolicy,
)
from crossborder_compliance.domain.metadata import ModelCapabilityCode
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresConfigRegistrySourceRepository,
    PostgresModelRegistryRepository,
    PostgresRegistrySourceRepository,
    PostgresSnapshotRegistryPinRepository,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresProjectRepository,
)
from crossborder_compliance.infrastructure.registry import (
    GenericMetadataRegistry,
    ModelRegistry,
    PromptRegistry,
)


@dataclass(frozen=True)
class ProviderConnection:
    """Infrastructure-only config. Credentials remain a reference until HTTP invocation."""

    model_name: str = field(repr=False)
    endpoint: dict = field(repr=False)
    secret_ref: str | None = field(repr=False)
    auth_type: str
    timeout_policy: dict
    retry_policy: dict
    external: bool


class PostgresLLMConfiguration:
    def __init__(self, sessions, context, *, draft_catalog=False):
        self.sessions, self.context = sessions, context
        self.draft_catalog = draft_catalog
        self.pins = PostgresSnapshotRegistryPinRepository(sessions, context)
        self.model_registry = ModelRegistry(PostgresModelRegistryRepository(sessions, context))
        self.policy_registry = GenericMetadataRegistry(
            PostgresRegistrySourceRepository(sessions, context), "MODEL_USAGE_POLICY"
        )
        self.prompt_registry = PromptRegistry(
            PostgresConfigRegistrySourceRepository(sessions, context)
        )

    @property
    def tenant(self):
        return str(self.context.tenant_id)

    def authorize(self, request):
        project = PostgresProjectRepository(self.sessions, self.context).get_project(
            request.project_id
        )
        if project is None or project.status != "ACTIVE":
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        if not self.context.permission.system:
            if not {
                "llm:invoke",
                f"project:{request.project_id}:read",
            } <= self.context.permission.scopes or (
                project.organization_id is not None
                and project.organization_id != self.context.user_context.organization_id
            ):
                raise GatewayDenied("RESOURCE_NOT_FOUND")
        if self.draft_catalog:
            return
        with self.sessions() as s:
            snapshot = s.scalar(
                select(b.AnalysisSnapshotEntity)
                .join(
                    b.ProjectVersionEntity,
                    b.ProjectVersionEntity.project_version_id
                    == b.AnalysisSnapshotEntity.project_version_id,
                )
                .where(
                    b.AnalysisSnapshotEntity.analysis_snapshot_id
                    == str(request.analysis_snapshot_id),
                    b.AnalysisSnapshotEntity.tenant_id == self.tenant,
                    b.AnalysisSnapshotEntity.status == "ACTIVE",
                    b.ProjectVersionEntity.tenant_id == self.tenant,
                    b.ProjectVersionEntity.project_id == str(request.project_id),
                )
            )
            if snapshot is None:
                raise GatewayDenied("RESOURCE_NOT_FOUND")

    def _saved(self, request, kind):
        if self.draft_catalog:
            return []
        return [
            p for p in self.pins.list_pins(request.analysis_snapshot_id) if p["pin_type"] == kind
        ]

    def _pin(self, request, kind, key, object_id, version_id, version):
        if self.draft_catalog:
            return
        self.pins.add_pin(
            analysis_snapshot_id=request.analysis_snapshot_id,
            pin_type=kind,
            logical_key=key,
            object_id=UUID(str(object_id)),
            version_id=UUID(str(version_id)),
            version_no=version,
        )

    def _as_of(self, request):
        if self.draft_catalog:
            return (
                PostgresProjectRepository(self.sessions, self.context)
                .read_intake(request.project_id)
                .intake.analysis_as_of_date
            )
        with self.sessions() as s:
            row = s.scalar(
                select(b.AnalysisSnapshotEntity).where(
                    b.AnalysisSnapshotEntity.tenant_id == self.tenant,
                    b.AnalysisSnapshotEntity.analysis_snapshot_id
                    == str(request.analysis_snapshot_id),
                )
            )
            if row is None:
                raise GatewayDenied("RESOURCE_NOT_FOUND")
            return row.analysis_as_of_date

    @staticmethod
    def _effective(row, when):
        return (row.effective_from is None or row.effective_from <= when) and (
            row.effective_to is None or row.effective_to >= when
        )

    def policies(self, request):
        self.authorize(request)
        saved = self._saved(request, "LLM_USAGE_POLICY")
        self.policy_registry.refresh()
        active = self.policy_registry.list()
        policies = []
        for role in ("TENANT", "PROJECT"):
            prior = next((p for p in saved if p["logical_key"] == role), None)
            if prior:
                with self.sessions() as s:
                    row = s.scalar(
                        select(m.MetadataVersionEntity)
                        .join(
                            m.MetadataDefinitionEntity,
                            m.MetadataDefinitionEntity.definition_id
                            == m.MetadataVersionEntity.definition_id,
                        )
                        .where(
                            m.MetadataVersionEntity.tenant_id == self.tenant,
                            m.MetadataVersionEntity.version_id == prior["version_id"],
                            m.MetadataVersionEntity.definition_id == prior["object_id"],
                            m.MetadataVersionEntity.lifecycle_status.in_(("ACTIVE", "SUPERSEDED")),
                            m.MetadataVersionEntity.approved_by.is_not(None),
                            m.MetadataVersionEntity.status == "ACTIVE",
                            m.MetadataDefinitionEntity.tenant_id == self.tenant,
                            m.MetadataDefinitionEntity.kind == "MODEL_USAGE_POLICY",
                            m.MetadataDefinitionEntity.status == "ACTIVE",
                        )
                    )
                    if row is None or not self._effective(row, self._as_of(request)):
                        raise GatewayDenied("MODEL_POLICY_REQUIRED")
                    data = dict(row.payload_json)
                    identity = (row.definition_id, row.version_id, row.version_no)
            else:
                matches = [
                    r
                    for r in active
                    if r["payload"].get("scope_type") == role
                    and (
                        role == "TENANT"
                        or r["payload"].get("project_id") == str(request.project_id)
                    )
                ]
                if len(matches) != 1:
                    raise GatewayDenied("MODEL_POLICY_REQUIRED")
                r = matches[0]
                if (r.get("effective_from") and r["effective_from"] > self._as_of(request)) or (
                    r.get("effective_to") and r["effective_to"] < self._as_of(request)
                ):
                    raise GatewayDenied("MODEL_POLICY_REQUIRED")
                data, identity = (
                    dict(r["payload"]),
                    (r["definition_id"], r["version_id"], r["version_no"]),
                )
            policy = ModelUsagePolicy.model_validate(
                dict(
                    data,
                    policy_id=identity[0],
                    version_id=identity[1],
                    version=identity[2],
                    tenant_id=self.tenant,
                )
            )
            if policy.scope_type != role or (
                role == "PROJECT" and policy.project_id != request.project_id
            ):
                raise GatewayDenied("RESOURCE_NOT_FOUND")
            self._pin(request, "LLM_USAGE_POLICY", role, *identity)
            policies.append(policy)
        return tuple(policies)

    def _model(self, deployment_id, when):
        with self.sessions() as s:
            row = s.execute(
                select(
                    m.ModelDefinitionEntity,
                    m.ModelDeploymentEntity,
                    m.ModelProviderEntity,
                    m.ModelProviderVersionEntity,
                )
                .join(
                    m.ModelDeploymentEntity,
                    m.ModelDeploymentEntity.model_definition_id
                    == m.ModelDefinitionEntity.model_definition_id,
                )
                .join(
                    m.ModelProviderEntity,
                    m.ModelProviderEntity.provider_id == m.ModelDefinitionEntity.provider_id,
                )
                .join(
                    m.ModelProviderVersionEntity,
                    m.ModelProviderVersionEntity.provider_version_id
                    == m.ModelDeploymentEntity.provider_version_id,
                )
                .where(
                    m.ModelDeploymentEntity.model_deployment_id == str(deployment_id),
                    *(
                        model.tenant_id == self.tenant
                        for model in (
                            m.ModelDefinitionEntity,
                            m.ModelDeploymentEntity,
                            m.ModelProviderEntity,
                            m.ModelProviderVersionEntity,
                        )
                    ),
                )
            ).first()
            if not row:
                raise GatewayDenied("RESOURCE_NOT_FOUND")
            definition, deployment, provider, version = row
            if (
                any(not x.enabled or x.status != "ACTIVE" for x in row)
                or deployment.lifecycle_status not in ("ACTIVE", "SUPERSEDED")
                or version.lifecycle_status not in ("ACTIVE", "SUPERSEDED")
                or not self._effective(deployment, when)
                or not self._effective(version, when)
            ):
                raise GatewayDenied("MODEL_CONFIGURATION_REVOKED")
            capabilities = list(
                s.scalars(
                    select(m.ModelCapabilityEntity).where(
                        m.ModelCapabilityEntity.tenant_id == self.tenant,
                        m.ModelCapabilityEntity.model_definition_id
                        == definition.model_definition_id,
                        m.ModelCapabilityEntity.status == "ACTIVE",
                    )
                )
            )
            health = s.scalar(
                select(m.ModelHealthMetadataEntity)
                .where(
                    m.ModelHealthMetadataEntity.tenant_id == self.tenant,
                    m.ModelHealthMetadataEntity.model_deployment_id
                    == deployment.model_deployment_id,
                    m.ModelHealthMetadataEntity.status == "ACTIVE",
                )
                .order_by(m.ModelHealthMetadataEntity.observed_at.desc())
                .limit(1)
            )
            config = dict(version.endpoint_config_json or {})
            frozen = dict(deployment.configuration_json or {})
            ttl = float(config.get("health_ttl_seconds", 300))
            healthy = (
                health
                and health.health_status == "HEALTHY"
                and ttl > 0
                and 0 <= (datetime.now(UTC) - health.observed_at).total_seconds() <= ttl
            )
            candidate = ModelCandidate(
                tenant_id=self.tenant,
                model_id=definition.model_definition_id,
                deployment_id=deployment.model_deployment_id,
                provider_id=provider.provider_id,
                provider_version_id=version.provider_version_id,
                provider_version=version.version_no,
                provider_type=provider.provider_type,
                deployment_class=version.deployment_type,
                trust_level=version.trust_level,
                data_boundary=version.data_boundary,
                capabilities=tuple(
                    frozen.get("capabilities", [c.capability for c in capabilities])
                ),
                operations=tuple(frozen.get("operations", config.get("operations", ()))),
                health_status="HEALTHY" if healthy else "UNKNOWN",
                max_output_tokens=frozen.get(
                    "max_output_tokens", definition.max_output_tokens or 1
                ),
                embedding_dimension=frozen.get(
                    "embedding_dimension",
                    next(
                        (
                            c.metadata_json.get("embedding_dimension")
                            for c in capabilities
                            if c.capability == "EMBEDDING"
                        ),
                        None,
                    ),
                ),
                priority=int(frozen.get("priority", config.get("routing_priority", 100))),
                structured_output_format=frozen.get("structured_output_format", "json_schema"),
                analysis_as_of_date=when,
            )
            connection = ProviderConnection(
                model_name=frozen.get("remote_model_name", definition.model_id),
                endpoint=config,
                secret_ref=version.secret_ref,
                auth_type=version.auth_type,
                timeout_policy=dict(version.timeout_policy_json or {}),
                retry_policy=dict(version.retry_policy_json or {}),
                external=version.deployment_type not in ("ON_PREMISE", "PRIVATE_CLOUD"),
            )
            return candidate, connection

    def models(self, request):
        self.authorize(request)
        saved = [
            p
            for p in self._saved(request, "LLM_MODEL")
            if p["logical_key"].startswith(request.operation.value + ":")
        ]
        when = self._as_of(request)
        if saved:
            result = []
            for pin in saved:
                try:
                    candidate, _ = self._model(pin["version_id"], when)
                    if str(candidate.model_id) != pin["object_id"]:
                        raise GatewayDenied()
                    result.append(candidate)
                except GatewayDenied:
                    continue  # Revoked pins are excluded; never replace them with newer models.
            return tuple(result)
        self.model_registry.refresh()
        with self.sessions() as s:
            ids = list(
                s.scalars(
                    select(m.ModelDefinitionEntity.active_deployment_id).where(
                        m.ModelDefinitionEntity.tenant_id == self.tenant,
                        m.ModelDefinitionEntity.model_definition_id.in_(
                            [str(row["model_definition_id"]) for row in self.model_registry.list()]
                        ),
                    )
                )
            )
        result = []
        for identity in ids:
            try:
                result.append(self._model(identity, when)[0])
            except GatewayDenied:
                continue
        return tuple(result)

    def model_display_name(self, model):
        with self.sessions() as s:
            row = s.scalar(
                select(m.ModelDeploymentEntity).where(
                    m.ModelDeploymentEntity.tenant_id == self.tenant,
                    m.ModelDeploymentEntity.model_deployment_id == str(model.deployment_id),
                )
            )
            if row is None:
                raise GatewayDenied("RESOURCE_NOT_FOUND")
            return row.configuration_json.get("display_name", str(model.model_id))

    def pin_models(self, request, models):
        for model in models:
            self._pin(
                request,
                "LLM_MODEL",
                request.operation.value + ":" + str(model.model_id),
                model.model_id,
                model.deployment_id,
                model.provider_version,
            )

    def prompt(self, request):
        if request.prompt_id is None:
            return None
        if (
            not self.context.permission.system
            and f"prompt:{request.prompt_id}:use" not in self.context.permission.scopes
        ):
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        saved = next(
            (
                p
                for p in self._saved(request, "LLM_PROMPT")
                if p["logical_key"] == str(request.prompt_id)
            ),
            None,
        )
        if saved:
            with self.sessions() as s:
                version = s.scalar(
                    select(m.PromptVersionEntity)
                    .join(
                        m.PromptDefinitionEntity,
                        m.PromptDefinitionEntity.prompt_definition_id
                        == m.PromptVersionEntity.prompt_definition_id,
                    )
                    .where(
                        m.PromptVersionEntity.tenant_id == self.tenant,
                        m.PromptDefinitionEntity.tenant_id == self.tenant,
                        m.PromptDefinitionEntity.status == "ACTIVE",
                        m.PromptVersionEntity.status == "ACTIVE",
                        m.PromptVersionEntity.prompt_version_id == saved["version_id"],
                        m.PromptVersionEntity.prompt_definition_id == str(request.prompt_id),
                        m.PromptVersionEntity.lifecycle_status.in_(("ACTIVE", "SUPERSEDED")),
                    )
                )
                if not version or not self._effective(version, self._as_of(request)):
                    raise GatewayDenied("RESOURCE_NOT_FOUND")
                self._prompt_capabilities(request, version.capability_requirement_json)
                return version.template_text
        self.prompt_registry.refresh()
        row = self.prompt_registry.get(request.prompt_id)
        if row is None:
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        self._prompt_capabilities(request, row.get("capability_requirement", []))
        self._pin(
            request,
            "LLM_PROMPT",
            str(request.prompt_id),
            row["definition_id"],
            row["version_id"],
            row["version_no"],
        )
        return str(row["template_text"])

    @staticmethod
    def _prompt_capabilities(request, codes):
        required = {ModelCapabilityCode(code) for code in (codes or [])}
        if not required <= required_capabilities(request):
            raise GatewayDenied("PROMPT_CAPABILITY_REQUIRED")

    def revalidate(self, request, model):
        self.authorize(request)
        current, _ = self._model(model.deployment_id, self._as_of(request))
        if current != model:
            raise GatewayDenied("MODEL_CONFIGURATION_CHANGED")

    def connection(self, model):
        current, connection = self._model(
            model.deployment_id, model.analysis_as_of_date or datetime.now(UTC).date()
        )
        if current != model:
            raise GatewayDenied("MODEL_CONFIGURATION_CHANGED")
        return connection
