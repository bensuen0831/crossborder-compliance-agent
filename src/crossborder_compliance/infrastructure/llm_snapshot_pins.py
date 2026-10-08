"""Confirmation-time model configuration freeze in the existing snapshot pin authority."""

from uuid import UUID

from sqlalchemy import select

from crossborder_compliance.application.llm_gateway_policy import (
    ModelRouter,
    ModelUsagePolicyService,
)
from crossborder_compliance.application.llm_invocation_policy import (
    DOCUMENT_TRIGGERS,
    QUERY_TRIGGERS,
)
from crossborder_compliance.application.llm_model_catalog import SnapshotModelConfigurationQuery
from crossborder_compliance.domain.llm_gateway import AuthorizedInput, GatewayDenied, InputReference
from crossborder_compliance.domain.llm_invocation import (
    InvocationPurpose,
    InvocationTrigger,
    LLMInvocationPolicy,
    ModelSelectionMode,
)
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b


def _policy(config, when):
    with config.sessions() as s:
        rows = s.scalars(
            select(m.MetadataVersionEntity)
            .join(
                m.MetadataDefinitionEntity,
                m.MetadataVersionEntity.definition_id == m.MetadataDefinitionEntity.definition_id,
            )
            .where(
                m.MetadataDefinitionEntity.tenant_id == config.tenant,
                m.MetadataDefinitionEntity.kind == "LLM_INVOCATION_POLICY",
                m.MetadataDefinitionEntity.status == "ACTIVE",
                m.MetadataVersionEntity.tenant_id == config.tenant,
                m.MetadataVersionEntity.lifecycle_status == "ACTIVE",
                m.MetadataVersionEntity.status == "ACTIVE",
                m.MetadataVersionEntity.approved_by.is_not(None),
                m.MetadataVersionEntity.published_at.is_not(None),
            )
        ).all()
        rows = [row for row in rows if config._effective(row, when)]
        if len(rows) != 1:
            raise GatewayDenied("LLM_INVOCATION_POLICY_REQUIRED")
        row = rows[0]
        return row, LLMInvocationPolicy.model_validate(
            dict(row.payload_json, policy_id=row.definition_id, version_id=row.version_id)
        )


def _prompts(config, when, intake, triggers):
    purposes = set()
    if set(triggers) & DOCUMENT_TRIGGERS:
        purposes.add(InvocationPurpose.DOCUMENT_CANDIDATE_EXTRACTION)
    if set(triggers) & QUERY_TRIGGERS:
        purposes.add(InvocationPurpose.QUERY_EXPANSION)
    if InvocationTrigger.RESULT_EXPLANATION_REQUESTED in triggers:
        purposes.add(InvocationPurpose.DERIVED_EXPLANATION)
    result = []
    with config.sessions() as s:
        for purpose in sorted(purposes):
            rows = s.execute(
                select(m.PromptBindingEntity, m.PromptVersionEntity)
                .join(
                    m.PromptVersionEntity,
                    m.PromptBindingEntity.prompt_version_id
                    == m.PromptVersionEntity.prompt_version_id,
                )
                .join(
                    m.PromptDefinitionEntity,
                    m.PromptDefinitionEntity.prompt_definition_id
                    == m.PromptVersionEntity.prompt_definition_id,
                )
                .where(
                    m.PromptBindingEntity.tenant_id == config.tenant,
                    m.PromptBindingEntity.binding_type == "LLM_INVOCATION_PURPOSE",
                    m.PromptBindingEntity.binding_ref == purpose.value,
                    m.PromptBindingEntity.status == "ACTIVE",
                    m.PromptBindingEntity.language_code.is_(None),
                    m.PromptVersionEntity.tenant_id == config.tenant,
                    m.PromptVersionEntity.lifecycle_status == "ACTIVE",
                    m.PromptVersionEntity.status == "ACTIVE",
                    m.PromptDefinitionEntity.tenant_id == config.tenant,
                    m.PromptDefinitionEntity.status == "ACTIVE",
                )
            ).all()
            selected = {
                version.prompt_version_id: version
                for binding, version in rows
                if config._effective(binding, when)
                and config._effective(version, when)
                and (
                    binding.scenario_definition_id is None
                    or binding.scenario_definition_id == intake.business_scenario
                )
                and (
                    binding.jurisdiction_id is None
                    or binding.jurisdiction_id
                    in intake.source_locations + intake.destination_locations
                )
            }
            if len(selected) != 1:
                raise GatewayDenied("LLM_PROMPT_BINDING_REQUIRED")
            version = next(iter(selected.values()))
            published = s.scalar(
                select(m.AdminPublishRecordEntity.publish_record_id).where(
                    m.AdminPublishRecordEntity.tenant_id == config.tenant,
                    m.AdminPublishRecordEntity.object_kind == "PROMPT",
                    m.AdminPublishRecordEntity.version_id == version.prompt_version_id,
                )
            )
            if not published:
                raise GatewayDenied("LLM_PROMPT_PUBLISH_REQUIRED")
            result.append((purpose, version))
    return result


def freeze_llm_configuration(sessions, context, intake, snapshot_id, *, source_snapshot_id=None):
    config = PostgresLLMConfiguration(sessions, context)
    with sessions() as s:
        snapshot = s.get(b.AnalysisSnapshotEntity, str(snapshot_id))
        if snapshot is None or snapshot.tenant_id != config.tenant:
            raise GatewayDenied("RESOURCE_NOT_FOUND")
        version_id = UUID(snapshot.project_version_id)
    request = SnapshotModelConfigurationQuery(
        project_id=intake.project_id, analysis_snapshot_id=snapshot_id
    )
    existing = config._saved(request, "LLM_SELECTION")
    if existing:
        return existing[0]["logical_key"]
    if source_snapshot_id is not None:
        source = request.model_copy(update={"analysis_snapshot_id": source_snapshot_id})
        with sessions() as s:
            original = s.scalar(
                select(b.AnalysisSnapshotEntity)
                .join(
                    b.ProjectVersionEntity,
                    b.AnalysisSnapshotEntity.project_version_id
                    == b.ProjectVersionEntity.project_version_id,
                )
                .where(
                    b.AnalysisSnapshotEntity.tenant_id == config.tenant,
                    b.AnalysisSnapshotEntity.analysis_snapshot_id == str(source_snapshot_id),
                    b.ProjectVersionEntity.project_id == str(intake.project_id),
                    b.ProjectVersionEntity.tenant_id == config.tenant,
                )
            )
            if original is None:
                raise GatewayDenied("RESOURCE_NOT_FOUND")
        for pin in config.pins.list_pins(source.analysis_snapshot_id):
            if pin["pin_type"].startswith("LLM_"):
                config._pin(
                    request,
                    pin["pin_type"],
                    pin["logical_key"],
                    pin["object_id"],
                    pin["version_id"],
                    pin["version_no"],
                )
        if config._saved(request, "LLM_SELECTION"):
            return config._saved(request, "LLM_SELECTION")[0]["logical_key"]
        config._pin(
            request,
            "LLM_SELECTION",
            "UNAVAILABLE",
            intake.project_id,
            version_id,
            intake.record_version,
        )
        return "UNAVAILABLE"
    preference = intake.ai_model_preference
    try:
        config.authorize(request)
        row, policy = _policy(config, intake.analysis_as_of_date)
        if len(preference.selected_model_ids) > policy.max_models:
            raise GatewayDenied("MODEL_SELECTION_LIMIT_EXCEEDED")
        prompts = _prompts(
            config,
            intake.analysis_as_of_date,
            intake,
            policy.allowed_triggers.get(preference.usage_mode, ()),
        )
        policies = config.policies(request)
        models = config.models(request)
        item = AuthorizedInput(
            ref=InputReference(
                resource_type="PROJECT_INTAKE", resource_id=intake.project_id, version_id=version_id
            ),
            tenant_id=context.tenant_id,
            project_id=intake.project_id,
            required_scopes=("project:read",),
            texts=(intake.scenario_description or "",),
        )
        decision = ModelUsagePolicyService().evaluate(request, context, (item,), policies, models)
        eligible = ModelRouter().route(request, decision, models)
        if preference.selected_model_ids:
            if not set(preference.selected_model_ids) <= {model.model_id for model in eligible}:
                raise GatewayDenied("MODEL_SELECTION_NOT_ALLOWED")
            eligible = tuple(
                model for model in eligible if model.model_id in preference.selected_model_ids
            )
        config.pin_models(request, eligible)
        for purpose, prompt in prompts:
            config._pin(
                request,
                "LLM_PURPOSE_PROMPT",
                purpose.value,
                prompt.prompt_definition_id,
                prompt.prompt_version_id,
                prompt.version_no,
            )
            config._pin(
                request,
                "LLM_PROMPT",
                prompt.prompt_definition_id,
                prompt.prompt_definition_id,
                prompt.prompt_version_id,
                prompt.version_no,
            )
        config._pin(
            request,
            "LLM_INVOCATION_POLICY",
            "INVOCATION",
            row.definition_id,
            row.version_id,
            row.version_no,
        )
    except GatewayDenied:
        if preference.selection_mode != ModelSelectionMode.AUTO:
            raise
        config._pin(
            request,
            "LLM_SELECTION",
            "UNAVAILABLE",
            intake.project_id,
            version_id,
            intake.record_version,
        )
        return "UNAVAILABLE"
    config._pin(
        request, "LLM_SELECTION", "CONFIGURED", intake.project_id, version_id, intake.record_version
    )
    return "CONFIGURED"
