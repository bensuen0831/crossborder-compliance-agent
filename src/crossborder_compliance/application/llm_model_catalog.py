"""Advisory eligibility over the canonical policy/router; selection is never authority."""

from uuid import UUID

from pydantic import Field

from crossborder_compliance.application.llm_gateway_policy import (
    ModelRouter,
    ModelUsagePolicyService,
)
from crossborder_compliance.domain.knowledge import Contract
from crossborder_compliance.domain.llm_gateway import GatewayDenied, ModelOperation
from crossborder_compliance.domain.metadata import ModelCapabilityCode


class ModelCatalogQuery(Contract):
    project_id: UUID
    operation: ModelOperation = ModelOperation.STRUCTURED_OUTPUT
    required_capabilities: tuple[ModelCapabilityCode, ...] = ()
    max_output_tokens: int = Field(default=512, ge=1, le=65536)
    selected_model_id: UUID | None = None


class SnapshotModelConfigurationQuery(ModelCatalogQuery):
    analysis_snapshot_id: UUID


class EligibleModel(Contract):
    model_id: UUID
    deployment_id: UUID
    provider_id: UUID
    provider_version_id: UUID
    display_name: str
    capabilities: tuple[str, ...]
    operations: tuple[ModelOperation, ...]
    health_status: str


class EligibleModelCatalog(Contract):
    project_id: UUID
    eligible_models: tuple[EligibleModel, ...]
    status: str
    reason_code: str | None = None


class EligibleModelCatalogService:
    def __init__(self, configuration, profile_source, context):
        self.configuration, self.profile_source, self.context = (
            configuration,
            profile_source,
            context,
        )

    def read(self, query: ModelCatalogQuery):
        self.configuration.authorize(query)
        inputs = self.profile_source(query.project_id)
        try:
            policies = self.configuration.policies(query)
            models = self.configuration.models(query)
            decision = ModelUsagePolicyService().evaluate(
                query, self.context, inputs, policies, models
            )
            eligible = ModelRouter().route(query, decision, models)
        except GatewayDenied as error:
            return EligibleModelCatalog(
                project_id=query.project_id,
                eligible_models=(),
                status="CAPABILITY_NOT_CONFIGURED",
                reason_code=error.code,
            )
        return EligibleModelCatalog(
            project_id=query.project_id,
            status="AVAILABLE",
            eligible_models=tuple(
                EligibleModel(
                    model_id=model.model_id,
                    deployment_id=model.deployment_id,
                    provider_id=model.provider_id,
                    provider_version_id=model.provider_version_id,
                    display_name=self.configuration.model_display_name(model),
                    capabilities=tuple(c.value for c in model.capabilities),
                    operations=model.operations,
                    health_status=model.health_status,
                )
                for model in eligible
            ),
        )
