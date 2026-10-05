import time
from uuid import uuid4

import pytest
from phase1h_fixtures import domain_fixture
from test_phase1l_a_skeleton import build

from crossborder_compliance.application.classification_services import ClassificationService
from crossborder_compliance.application.workflow_classification import ClassificationWorkflowStage
from crossborder_compliance.application.workflow_skeleton import (
    SemanticStep,
    StageExecutionRequest,
    StageExecutionResult,
    WorkflowExecutionPolicy,
    WorkflowRetryPolicy,
    WorkflowTimeoutPolicy,
)


def test_timeout_boundary_is_bounded_and_does_not_accept_late_result():
    f, g, w, s, stage, ops, _ = build(
        StageExecutionResult(status="SUCCESS"),
        WorkflowExecutionPolicy(
            retry=WorkflowRetryPolicy(max_attempts=2, interval_seconds=0),
            timeout=WorkflowTimeoutPolicy(stage_seconds=0.001),
        ),
    )

    def slow(request):
        stage.calls += 1
        time.sleep(0.005)
        return StageExecutionResult(status="SUCCESS")

    stage.execute = slow
    assert g.invoke(s, f.config(w))["reason_codes"] == ["STAGE_RETRY_EXHAUSTED"]
    assert stage.calls == 2


def test_repeated_route_guard_and_state_identity_tampering():
    f, g, w, s, stage, ops, _ = build(
        StageExecutionResult(status="SUCCESS"), WorkflowExecutionPolicy(max_visits_per_step=1)
    )
    s["visits"] = {"requirement": 1}
    assert g.invoke(s, f.config(w))["route"] == "FAILED" and stage.calls == 0
    s["identity"]["analysis_snapshot_id"] = str(uuid4())
    with pytest.raises(PermissionError):
        f.validate(w, s)


def test_real_classification_service_no_data_returns_no_fabricated_result():
    rule, facts, scheme = domain_fixture()

    class Repository:
        def prepare(self, *args):
            return facts.model_copy(update={"data_item_id": None}), scheme, (rule,)

        def save(self, outcome):
            raise AssertionError("no formal result may be persisted")

    f, _, w, _, _, _, auth = build(StageExecutionResult(status="SUCCESS"))
    identity = auth.identity.model_copy(
        update={
            "tenant_id": facts.tenant_id,
            "project_id": facts.project_id,
            "analysis_snapshot_id": facts.analysis_snapshot_id,
        }
    )
    request = StageExecutionRequest(
        identity=identity,
        step=SemanticStep.CLASSIFICATION,
        idempotency_key="test",
        timeout_seconds=10,
    )
    stage = ClassificationWorkflowStage(
        ClassificationService(Repository()),
        project_id=facts.project_id,
        snapshot_id=facts.analysis_snapshot_id,
        data_item_id=None,
        scheme_version_id=scheme.scheme_version_id,
    )
    outcome = stage.execute(request)
    assert outcome.status == "NOT_APPLICABLE" and outcome.result_ref is None
    assert outcome.reason_codes == ("NO_DATA_ITEM",)


def test_canonical_events_are_small_and_domain_neutral():
    f, g, w, s, _, ops, _ = build(
        StageExecutionResult(status="INSUFFICIENT_INPUT", reason_codes=("NO_FORMAL_INPUT",))
    )
    g.invoke(s, f.config(w))
    assert {"WAITING", "RUNNING", "WARNING"} <= {e.status for e in ops.events}
    assert all(set(e.payload) == {"reason_codes", "status", "request_id"} for e in ops.events)
    assert all(e.workflow_run_id == w for e in ops.events)
    assert all(
        e.event_type.value in {"NODE_STARTED", "NODE_COMPLETED", "NODE_PROGRESS"}
        for e in ops.events
    )


def test_revocation_during_stage_blocks_checkpoint_update():
    f, g, w, s, stage, _, auth = build(StageExecutionResult(status="SUCCESS"))

    def revoke(request):
        auth.allowed = False
        return StageExecutionResult(status="SUCCESS", result_ref=uuid4())

    stage.execute = revoke
    with pytest.raises(PermissionError):
        g.invoke(s, f.config(w))
    assert g.get_state(f.config(w)).values["completed_steps"] == []
