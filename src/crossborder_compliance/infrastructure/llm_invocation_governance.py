"""Exact confirmed-intake preferences and governed policy pins; no latest fallback."""

from sqlalchemy import select

from crossborder_compliance.domain.llm_gateway import GatewayDenied
from crossborder_compliance.domain.llm_invocation import AIModelPreference, LLMInvocationPolicy
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b


class PostgresLLMInvocationGovernance:
    def __init__(self, configuration):
        self.configuration = configuration

    def load(self, request):
        config = self.configuration
        config.authorize(request)
        selection = config._saved(request, "LLM_SELECTION")
        policies = config._saved(request, "LLM_INVOCATION_POLICY")
        if len(selection) != 1 or len(policies) != 1 or selection[0]["logical_key"] != "CONFIGURED":
            raise GatewayDenied("LLM_CAPABILITY_NOT_CONFIGURED")
        with config.sessions() as s:
            intake = s.scalar(
                select(b.ProjectVersionEntity).where(
                    b.ProjectVersionEntity.project_version_id == selection[0]["version_id"],
                    b.ProjectVersionEntity.tenant_id == config.tenant,
                    b.ProjectVersionEntity.project_id == str(request.project_id),
                    b.ProjectVersionEntity.status.in_(("CONFIRMED", "SUPERSEDED")),
                )
            )
            if intake is None or selection[0]["object_id"] != str(request.project_id):
                raise GatewayDenied("RESOURCE_NOT_FOUND")
            pin = policies[0]
            row = s.scalar(
                select(m.MetadataVersionEntity)
                .join(
                    m.MetadataDefinitionEntity,
                    m.MetadataVersionEntity.definition_id
                    == m.MetadataDefinitionEntity.definition_id,
                )
                .where(
                    m.MetadataVersionEntity.tenant_id == config.tenant,
                    m.MetadataVersionEntity.version_id == pin["version_id"],
                    m.MetadataVersionEntity.definition_id == pin["object_id"],
                    m.MetadataVersionEntity.status == "ACTIVE",
                    m.MetadataVersionEntity.lifecycle_status.in_(("ACTIVE", "SUPERSEDED")),
                    m.MetadataVersionEntity.approved_by.is_not(None),
                    m.MetadataDefinitionEntity.tenant_id == config.tenant,
                    m.MetadataDefinitionEntity.kind == "LLM_INVOCATION_POLICY",
                    m.MetadataDefinitionEntity.status == "ACTIVE",
                )
            )
            if row is None or not PostgresLLMConfiguration._effective(row, config._as_of(request)):
                raise GatewayDenied("LLM_INVOCATION_POLICY_REQUIRED")
            policy = LLMInvocationPolicy.model_validate(
                dict(row.payload_json, policy_id=row.definition_id, version_id=row.version_id)
            )
            preference = AIModelPreference.model_validate(
                intake.intake_json.get("ai_model_preference", {})
            )
            return policy, preference
