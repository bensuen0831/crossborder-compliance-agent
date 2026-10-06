"""Structured routing/refs and real owning decision service delegation."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from phase1j_fixtures import decision_fixture
from pydantic import ValidationError
from test_phase1j_engines import replace_policy
from test_phase1l_a_skeleton import Authority, Operations

from crossborder_compliance.application.decision_services import FormalDecisionService
from crossborder_compliance.application.workflow_formal import (
    FormalWorkflowAuthorization,
    FormalWorkflowPlan,
    FormalWorkflowStages,
    formal_outcome,
)
from crossborder_compliance.application.workflow_skeleton import (
    SemanticStep,
    StageExecutionRequest,
    StageExecutionResult,
)
from crossborder_compliance.workflows.canonical import CanonicalGraphFactory, StateEnvelope
from crossborder_compliance.workflows.runtime_context import RuntimeContext


@pytest.mark.parametrize(
    "ordinary,flags,expected",
    [
        ("COMPLETED", {}, "SUCCESS"),
        ("NOT_APPLICABLE", {}, "NOT_APPLICABLE"),
        ("INSUFFICIENT_INPUT", {}, "INSUFFICIENT_INPUT"),
        ("INSUFFICIENT_EVIDENCE", {}, "EVIDENCE_INSUFFICIENT"),
        ("CONFLICTED", {}, "CONFLICTED"),
        ("REVIEW_REQUIRED", {}, "REVIEW_REQUIRED"),
        ("CAPABILITY_NOT_CONFIGURED", {}, "CAPABILITY_NOT_CONFIGURED"),
        ("LOW_CONFIDENCE", {}, "LOW_CONFIDENCE"),
        ("COMPLETED", {"review_required": True}, "REVIEW_REQUIRED"),
        ("COMPLETED", {"conflict_state": "CONFLICTED", "review_required": True}, "CONFLICTED"),
        (
            "COMPLETED",
            {"input_sufficiency": "INSUFFICIENT_EVIDENCE", "review_required": True},
            "EVIDENCE_INSUFFICIENT",
        ),
        ("TIED", {}, "REVIEW_REQUIRED"),
        ("NO_VIABLE_PATH", {}, "REVIEW_REQUIRED"),
        ("UNRECOGNIZED_FUTURE_STATUS", {}, "NON_RETRYABLE_FAILURE"),
    ],
)
def test_structured_outcomes_and_guard_precedence(ordinary, flags, expected):
    assert formal_outcome(SimpleNamespace(**flags), ordinary) == expected


def test_reference_set_contract_is_bounded_and_legacy_state_compatible():
    a = Authority()
    first, second = uuid4(), uuid4()
    old = StateEnvelope(identity=a.identity).model_dump(mode="json")
    old.pop("result_ref_sets")
    assert StateEnvelope.model_validate(old).result_ref_sets == {}
    with pytest.raises(ValidationError):
        StageExecutionResult(status="SUCCESS", related_result_refs=(first,))
    with pytest.raises(ValidationError):
        StageExecutionResult(status="SUCCESS", result_ref=first, related_result_refs=(first, first))
    with pytest.raises(ValidationError):
        StateEnvelope(
            identity=a.identity,
            result_refs={SemanticStep.APPLICABILITY: first},
            result_ref_sets={SemanticStep.APPLICABILITY: (second,)},
        )


def plan_for(inputs, authority):
    i = inputs.identity
    app = inputs.applicability[0]
    authority.identity = authority.identity.model_copy(
        update={
            "tenant_id": i.tenant_id,
            "project_id": i.project_id,
            "analysis_snapshot_id": i.analysis_snapshot_id,
            "mode": "DATA_AWARE",
        }
    )
    return FormalWorkflowPlan(
        tenant_id=i.tenant_id,
        project_id=i.project_id,
        analysis_snapshot_id=i.analysis_snapshot_id,
        request_context_ref=authority.identity.request_context_ref,
        context_resolution_run_id=uuid4(),
        mode="DATA_AWARE",
        subject_type="DATA_ITEM",
        subject_id=i.subject_id,
        classification_data_item_ids=(i.subject_id,),
        scheme_version_id=uuid4(),
        applicability=[
            {"jurisdiction_id": app.jurisdiction_id, "config_id": app.applicability_config_id}
        ],
        retrieval_query=dict(
            project_id=str(i.project_id),
            analysis_snapshot_id=str(i.analysis_snapshot_id),
            policy_id=str(uuid4()),
            query_text="generic",
            idempotency_key="trusted",
            subject_type="DATA_ITEM",
            subject_id=str(i.subject_id),
        ),
    )


@pytest.mark.parametrize(
    "case,blocked_at",
    [
        ("success", None),
        ("tie", "recommendation"),
        ("prohibition", "candidate_path"),
        ("missing_risk", "risk"),
        ("conflict", "obligation"),
        ("capability", "recommendation"),
    ],
)
def test_nodes_delegate_to_actual_formal_service_and_cannot_fabricate_final(case, blocked_at):
    inputs = decision_fixture(paths=2 if case == "tie" else 1, risk_value=25)
    if case == "missing_risk":
        inputs = inputs.model_copy(update={"facts": ()})
    if case == "prohibition":
        ob = inputs.policy("OBLIGATION_POLICY").config
        inputs = replace_policy(
            inputs,
            "OBLIGATION_POLICY",
            entries=(
                ob.entries[0].model_copy(update={"legal_effect_code": "TRANSFER_PROHIBITED"}),
            ),
        )
    if case == "conflict":
        app = inputs.applicability[0].model_copy(
            update={
                "conflict_status": "CONFLICTED",
                "applicability_status": "CONFLICTED",
                "review_required": True,
            }
        )
        inputs = inputs.model_copy(update={"applicability": (app,)})
    if case == "capability":
        p = inputs.policy("COMPLIANCE_PATH_POLICY").config
        inputs = replace_policy(
            inputs,
            "COMPLIANCE_PATH_POLICY",
            templates=(p.templates[0].model_copy(update={"capability_ids": (uuid4(),)}),),
        )
    saved = {}
    requests = []

    class Repository:
        def prepare_decision(self, request):
            requests.append(request)
            return inputs, {r.kind: saved[r.result_id] for r in request.upstream_refs}

        def save_decision(self, request, result):
            saved[result.result_id] = result
            return result

        def read_decision(self, stage, ident):
            return saved[ident]

    class ReviewOperations(Operations):
        def ensure_review_task(self, **kwargs):
            return uuid4()

        def mark_review_required(self, wf):
            self.status_value = "REVIEW_REQUIRED"

    a = Authority()
    ops = ReviewOperations()
    plan = plan_for(inputs, a)
    stages = FormalWorkflowStages(
        plan,
        contexts=None,
        knowledge_scope=None,
        retrieval=None,
        evidence=None,
        classification=None,
        country=None,
        decisions=FormalDecisionService(Repository()),
    )
    app = inputs.applicability[0]
    stages._rag = lambda request: SimpleNamespace(
        evidence_pack=SimpleNamespace(evidence_pack_id=str(uuid4()))
    )

    class Early:
        def execute(self, request):
            ref = (
                app.applicability_result_id
                if request.step == SemanticStep.APPLICABILITY
                else uuid4()
            )
            if request.step in list(SemanticStep)[:4]:
                ref = plan.context_resolution_run_id
            elif request.step == SemanticStep.KNOWLEDGE_SCOPE:
                ref = plan.analysis_snapshot_id
            return StageExecutionResult(
                status="SUCCESS", result_ref=ref, related_result_refs=(ref,)
            )

    bindings = stages.bindings()
    for step in list(SemanticStep)[:9]:
        bindings[step] = Early()
    factory = CanonicalGraphFactory(authorization=a, stages=bindings, emit_result_refs=True)
    g = factory.build(InMemorySaver(), RuntimeContext(ops, "request", "test", "test", "test"))
    output = g.invoke(
        factory.initial_state(a.identity.workflow_run_id),
        factory.config(a.identity.workflow_run_id),
    )
    if blocked_at:
        assert output["current_step"] == blocked_at
        assert "final_path" not in output["result_refs"]
        assert output["route"] in {"REVIEW", "WARNING"}
    else:
        assert (
            output["route"] == "COMPLETED"
            and saved[UUID(output["result_refs"]["final_path"])].items[0].status
            == "CONDITIONAL_PROPOSAL"
        )
        assert [r.stage_kind for r in requests] == [
            "OBLIGATION",
            "CANDIDATE_PATH",
            "RISK",
            "RECOMMENDATION",
            "FINAL_PATH",
        ]
    assert all(r.applicability_result_ids == (app.applicability_result_id,) for r in requests)
    assert all(not hasattr(r, "score") for r in requests)


def test_plan_mode_scope_and_missing_refs_fail_before_service_calls():
    a = Authority()
    inputs = decision_fixture()
    plan = plan_for(inputs, a)
    data = plan.model_dump(mode="json")
    data["mode"] = "SCENARIO_LEVEL"
    with pytest.raises(ValidationError):
        FormalWorkflowPlan.model_validate(data)
    stages = FormalWorkflowStages(
        plan,
        contexts=None,
        knowledge_scope=None,
        retrieval=None,
        evidence=None,
        classification=None,
        country=None,
        decisions=None,
    )
    req = StageExecutionRequest(
        identity=a.identity, step=SemanticStep.RISK, idempotency_key="stage", timeout_seconds=1
    )
    with pytest.raises(ValueError, match="missing upstream"):
        stages.execute(req)
    with pytest.raises(PermissionError):
        stages.execute(
            req.model_copy(
                update={"identity": a.identity.model_copy(update={"tenant_id": uuid4()})}
            )
        )


@pytest.mark.parametrize(
    "field", ["tenant_id", "project_id", "analysis_snapshot_id", "request_context_ref"]
)
def test_plan_authorization_rejects_mismatched_refs_before_runtime_side_effects(field):
    authority = Authority()
    plan = plan_for(decision_fixture(), authority)
    auth = FormalWorkflowAuthorization(authority, plan)
    assert auth.authorize(authority.identity.workflow_run_id, "execute") == authority.identity
    authority.identity = authority.identity.model_copy(update={field: uuid4()})
    with pytest.raises(PermissionError):
        auth.authorize(authority.identity.workflow_run_id, "execute")


@pytest.mark.parametrize("step", [SemanticStep.FORMAL_CONTEXT, SemanticStep.KNOWLEDGE_SCOPE])
def test_checkpoint_reference_cannot_replace_the_pinned_context_or_scope(step):
    authority = Authority()
    plan = plan_for(decision_fixture(), authority)
    stages = FormalWorkflowStages(
        plan,
        contexts=None,
        knowledge_scope=None,
        retrieval=None,
        evidence=None,
        classification=None,
        country=None,
        decisions=None,
    )
    refs = {s: plan.context_resolution_run_id for s in list(SemanticStep)[:6]}
    refs[SemanticStep.KNOWLEDGE_SCOPE] = plan.analysis_snapshot_id
    refs[step] = uuid4()
    request = StageExecutionRequest(
        identity=authority.identity,
        step=SemanticStep.SUFFICIENCY,
        result_refs=refs,
        idempotency_key="checkpoint-ref-test",
        timeout_seconds=30,
    )
    with pytest.raises(PermissionError):
        stages.execute(request)
