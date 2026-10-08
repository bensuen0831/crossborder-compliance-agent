from datetime import date
from uuid import UUID, uuid4

import pytest
from test_phase1k_a_configuration_postgres import publish as publish_metadata
from test_phase1kb_control_postgres import control as control
from test_phase1kb_selection_postgres import selected as selected

from crossborder_compliance.domain.contracts import ProjectIntakeContext
from crossborder_compliance.domain.llm_gateway import GatewayDenied, ModelOperation
from crossborder_compliance.domain.llm_invocation import InvocationPurpose
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.llm_gateway_configuration import PostgresLLMConfiguration
from crossborder_compliance.infrastructure.llm_invocation_governance import (
    PostgresLLMInvocationGovernance,
)
from crossborder_compliance.infrastructure.llm_snapshot_pins import freeze_llm_configuration
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)

pytestmark = pytest.mark.runtime_smoke


def snapshot_frame(f):
    with f["sf"]() as s:
        original = s.get(b.AnalysisSnapshotEntity, str(f["query"].analysis_snapshot_id))
        version = s.get(b.ProjectVersionEntity, original.project_version_id)
        intake = ProjectIntakeContext.model_validate(version.intake_json)
        version_id = original.project_version_id
    snapshot = uuid4()
    with f["sf"]() as s, s.begin():
        s.add(
            b.AnalysisSnapshotEntity(
                tenant_id=str(f["tenant"]),
                analysis_snapshot_id=str(snapshot),
                project_version_id=version_id,
                snapshot_version="2",
                analysis_as_of_date=date.today(),
                provenance_json={"workflow_run_id": str(uuid4())},
            )
        )
    return intake, f["query"].model_copy(update={"analysis_snapshot_id": snapshot})


def bind_published_prompt(f):
    admin = f["repo"].context
    repository = PostgresGovernedArtifactAdminRepository(f["sf"], admin, "prompts")
    prompt = publish_metadata(
        repository,
        repository.create_draft(
            code=uuid4().hex,
            display_name="Candidate-only extraction",
            payload={
                "template_text": "Extract traceable candidates; never produce legal decisions.",
                "capability_requirement": ["STRUCTURED_OUTPUT"],
            },
        ),
    )
    binding = repository.bind_llm_invocation(
        UUID(prompt["version_id"]), InvocationPurpose.DOCUMENT_CANDIDATE_EXTRACTION
    )
    assert (
        repository.bind_llm_invocation(
            UUID(prompt["version_id"]), InvocationPurpose.DOCUMENT_CANDIDATE_EXTRACTION
        )
        == binding
    )
    return prompt


def test_confirmation_freezes_exact_models_policies_prompt_and_preferences(selected):
    f = selected
    intake, query = snapshot_frame(f)
    prompt = bind_published_prompt(f)
    assert (
        freeze_llm_configuration(f["sf"], f["config"].context, intake, query.analysis_snapshot_id)
        == "CONFIGURED"
    )
    config = PostgresLLMConfiguration(f["sf"], f["config"].context, frozen_snapshot=True)
    policy, preference = PostgresLLMInvocationGovernance(config).load(query)
    assert preference == intake.ai_model_preference
    pins = config.pins.list_pins(query.analysis_snapshot_id)
    assert len([pin for pin in pins if pin["pin_type"] == "LLM_MODEL"]) == 4
    assert {pin["version_id"] for pin in pins if pin["pin_type"] == "LLM_PROMPT"} == {
        prompt["version_id"]
    }
    assert len(config.policies(query)) == 2 and len(config.models(query)) == 4
    assert "secret" not in str(pins)
    assert (
        freeze_llm_configuration(f["sf"], f["config"].context, intake, query.analysis_snapshot_id)
        == "CONFIGURED"
    )
    assert config.pins.list_pins(query.analysis_snapshot_id) == pins


def test_unavailable_frame_cannot_silently_gain_future_llm_capability(selected):
    f = selected
    intake, query = snapshot_frame(f)
    assert (
        freeze_llm_configuration(f["sf"], f["config"].context, intake, query.analysis_snapshot_id)
        == "UNAVAILABLE"
    )
    bind_published_prompt(f)
    assert (
        freeze_llm_configuration(f["sf"], f["config"].context, intake, query.analysis_snapshot_id)
        == "UNAVAILABLE"
    )
    with pytest.raises(GatewayDenied, match="LLM_CAPABILITY_NOT_CONFIGURED"):
        PostgresLLMInvocationGovernance(f["config"]).load(query)


def test_historical_snapshot_model_and_prompt_do_not_use_new_versions(selected):
    f = selected
    intake, query = snapshot_frame(f)
    prompt = bind_published_prompt(f)
    assert (
        freeze_llm_configuration(f["sf"], f["config"].context, intake, query.analysis_snapshot_id)
        == "CONFIGURED"
    )
    config = PostgresLLMConfiguration(f["sf"], f["config"].context, frozen_snapshot=True)
    before = config.models(query)
    # Future mutable projection pointers cannot replace the pinned deployment configuration.
    with f["sf"]() as s, s.begin():
        definition = s.get(m.ModelDefinitionEntity, str(before[0].model_id))
        definition.max_output_tokens = 1
        definition.display_name = "New presentation"
        prompt_definition = s.get(m.PromptDefinitionEntity, prompt["definition_id"])
        prompt_definition.active_version_id = None
    assert config.models(query) == before
    scoped = RepositoryContext.user(
        f["tenant"],
        "owner",
        set(config.context.permission.scopes) | {f"prompt:{prompt['definition_id']}:use"},
    )
    assert (
        PostgresLLMConfiguration(f["sf"], scoped, frozen_snapshot=True).prompt(
            query.model_copy(update={"prompt_id": UUID(prompt["definition_id"])})
        )
        == "Extract traceable candidates; never produce legal decisions."
    )


def test_frozen_configuration_rejects_unpinned_operation_instead_of_latest(selected):
    f = selected
    intake, query = snapshot_frame(f)
    bind_published_prompt(f)
    freeze_llm_configuration(f["sf"], f["config"].context, intake, query.analysis_snapshot_id)
    config = PostgresLLMConfiguration(f["sf"], f["config"].context, frozen_snapshot=True)
    with pytest.raises(GatewayDenied, match="LLM_SNAPSHOT_PIN_REQUIRED"):
        config.models(query.model_copy(update={"operation": ModelOperation.EMBEDDING}))


def test_review_successor_preserves_original_model_frame(selected):
    f = selected
    intake, source = snapshot_frame(f)
    bind_published_prompt(f)
    freeze_llm_configuration(f["sf"], f["config"].context, intake, source.analysis_snapshot_id)
    with f["sf"]() as s, s.begin():
        original = s.get(b.AnalysisSnapshotEntity, str(source.analysis_snapshot_id))
        old = s.get(b.ProjectVersionEntity, original.project_version_id)
        old.status = "SUPERSEDED"
        successor_version = uuid4()
        s.add(
            b.ProjectVersionEntity(
                tenant_id=str(f["tenant"]),
                project_id=old.project_id,
                project_version_id=str(successor_version),
                version_no=2,
                status="CONFIRMED",
                intake_json=old.intake_json,
            )
        )
        s.flush()
        successor_snapshot = uuid4()
        s.add(
            b.AnalysisSnapshotEntity(
                tenant_id=str(f["tenant"]),
                analysis_snapshot_id=str(successor_snapshot),
                project_version_id=str(successor_version),
                snapshot_version="3",
                analysis_as_of_date=date.today(),
                provenance_json={"workflow_run_id": str(uuid4())},
            )
        )
    before = f["config"].pins.list_pins(source.analysis_snapshot_id)
    freeze_llm_configuration(
        f["sf"],
        f["config"].context,
        intake,
        successor_snapshot,
        source_snapshot_id=source.analysis_snapshot_id,
    )
    query = source.model_copy(update={"analysis_snapshot_id": successor_snapshot})
    policy, preference = PostgresLLMInvocationGovernance(f["config"]).load(query)
    assert preference == intake.ai_model_preference
    after = f["config"].pins.list_pins(successor_snapshot)
    fields = ("pin_type", "logical_key", "object_id", "version_id", "version_no")
    assert [{key: pin[key] for key in fields} for pin in after] == [
        {key: pin[key] for key in fields} for pin in before
    ]


def test_published_invocation_policy_payload_cannot_be_changed(selected):
    f = selected
    with pytest.raises(Exception, match="immutable LLM policy configuration"):
        with f["sf"]() as s, s.begin():
            pin = f["config"]._saved(f["query"], "LLM_INVOCATION_POLICY")[0]
            row = s.get(m.MetadataVersionEntity, pin["version_id"])
            row.payload_json = {"allowed_triggers": {}, "max_models": 16}
