import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from crossborder_compliance.application.workflow_skeleton import (
    ExecutionIdentity,
    SemanticStep,
    StageExecutionResult,
    StageTransientFailure,
    WorkflowExecutionPolicy,
    WorkflowRetryPolicy,
)
from crossborder_compliance.workflows.canonical import (
    GRAPH_VERSION,
    PIPELINE,
    STATE_VERSION,
    CanonicalGraphFactory,
    StateEnvelope,
)
from crossborder_compliance.workflows.langgraph_adapter import installed_version
from crossborder_compliance.workflows.runtime_context import RuntimeContext


class Authority:
    def __init__(self):
        self.identity = ExecutionIdentity(
            workflow_run_id=uuid4(),
            tenant_id=uuid4(),
            project_id=uuid4(),
            analysis_snapshot_id=uuid4(),
            request_context_ref=uuid4(),
            mode="SCENARIO_LEVEL",
            graph_definition_version=GRAPH_VERSION,
            state_schema_version=STATE_VERSION,
            langgraph_runtime_version=installed_version("langgraph"),
            checkpointer_version=installed_version("langgraph-checkpoint-postgres"),
        )
        self.allowed = True

    def authorize(self, wf, operation):
        if not self.allowed or wf != self.identity.workflow_run_id:
            raise PermissionError()
        return self.identity


class Operations:
    def __init__(self):
        self.events = []
        self.status_value = "RUNNING"

    def record_event(self, tenant, event):
        self.events.append(event)

    def set_status(self, wf, status):
        self.status_value = status

    def mark_completed(self, *args):
        self.status_value = "COMPLETED"


class Stage:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def build(result, policy=None, all_steps=False):
    authority, ops = Authority(), Operations()
    stage = Stage(result)
    factory = CanonicalGraphFactory(
        authorization=authority,
        stages={step: stage for step in PIPELINE}
        if all_steps
        else {SemanticStep.REQUIREMENT: stage},
        policy=policy,
    )
    context = RuntimeContext(ops, "request", GRAPH_VERSION, "test", "test")
    graph = factory.build(InMemorySaver(), context)
    wf = authority.identity.workflow_run_id
    state = factory.initial_state(wf)
    return factory, graph, wf, state, stage, ops, authority


@pytest.mark.parametrize(
    "status,expected",
    [
        ("SUCCESS", "WARNING"),
        ("NOT_APPLICABLE", "WARNING"),
        ("EVIDENCE_SUFFICIENT", "WARNING"),
        ("INSUFFICIENT_INPUT", "WARNING"),
        ("CAPABILITY_NOT_CONFIGURED", "WARNING"),
        ("NON_RETRYABLE_FAILURE", "FAILED"),
        ("FAILED", "FAILED"),
        ("RETRYABLE_FAILURE", "FAILED"),
    ],
)
def test_routing_without_fabricating_future_results(status, expected):
    f, g, w, s, stage, ops, _ = build(StageExecutionResult(status=status))
    output = g.invoke(s, f.config(w))
    assert output["route"] == expected and ops.status_value == expected
    assert stage.calls == (3 if status == "RETRYABLE_FAILURE" else 1)
    assert output["result_refs"] == {}


def test_evidence_insufficient_retains_only_fallback_reference():
    fallback = uuid4()
    f, g, w, s, _, _, _ = build(
        StageExecutionResult(status="EVIDENCE_INSUFFICIENT", fallback_ref=fallback)
    )
    result = g.invoke(s, f.config(w))
    assert result["fallback_ref"] == str(fallback) and result["route"] == "WARNING"
    with pytest.raises(ValidationError):
        StageExecutionResult(status="EVIDENCE_INSUFFICIENT")


def test_compile_order_small_state_and_unconfigured_production():
    f, g, w, s, _, _, a = build(StageExecutionResult(status="SUCCESS"), all_steps=True)
    result = g.invoke(s, f.config(w))
    assert result["completed_steps"] == [x.value for x in PIPELINE]
    assert len(result["completed_steps"]) == 16 and result["route"] == "COMPLETED"
    with pytest.raises(ValidationError):
        StateEnvelope.model_validate(dict(s, secret="forbidden"))
    with pytest.raises(ValidationError):
        StageExecutionResult(status="SUCCESS", result_ref=object())
    absent = CanonicalGraphFactory(authorization=a)
    stopped = absent.build(InMemorySaver(), OperationsContext()).invoke(s, absent.config(w))
    assert stopped["route"] == "WARNING" and stopped["completed_steps"] == []


def OperationsContext():
    return RuntimeContext(Operations(), "request", GRAPH_VERSION, "test", "test")


def test_retry_guards_and_current_authorization():
    f, g, w, s, stage, ops, a = build(
        StageTransientFailure(),
        WorkflowExecutionPolicy(retry=WorkflowRetryPolicy(max_attempts=2, interval_seconds=0)),
    )
    assert g.invoke(s, f.config(w))["route"] == "FAILED" and stage.calls == 2
    f, g, w, s, stage, ops, a = build(
        StageExecutionResult(status="SUCCESS"), WorkflowExecutionPolicy(max_steps=1), all_steps=True
    )
    assert g.invoke(s, f.config(w))["reason_codes"] == ["WORKFLOW_STEP_GUARD"]
    a.allowed = False
    with pytest.raises(PermissionError):
        f.validate(w, s)


@pytest.mark.runtime_smoke
@pytest.mark.parametrize(
    "review_status,decision_code",
    [
        ("REVIEW_REQUIRED", "APPROVE"),
        ("CONFLICTED", "APPROVE"),
        ("LOW_CONFIDENCE", "APPROVE"),
        ("REVIEW_REQUIRED", "REJECT"),
    ],
)
def test_postgres_process_restart_review_idempotency_and_snapshot(
    tmp_path, review_status, decision_code
):
    from phase1l_a_worker import adapter
    from sqlalchemy import select

    from crossborder_compliance.config import get_settings
    from crossborder_compliance.domain.contracts import ReviewDecisionDTO
    from crossborder_compliance.infrastructure.persistence.db import build_session_factory
    from crossborder_compliance.infrastructure.persistence.models import (
        AnalysisSnapshotEntity,
        ProjectEntity,
        ProjectVersionEntity,
        ReviewTaskEntity,
    )
    from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository

    sessions = build_session_factory(get_settings().database_url)[1]
    ids = {k: str(uuid4()) for k in ("tenant", "project", "version", "snapshot", "run", "request")}
    ids["review_status"] = review_status
    ids["preferred_locale"] = "zh-CN"
    with sessions() as db, db.begin():
        db.add(
            ProjectEntity(
                project_id=ids["project"],
                tenant_id=ids["tenant"],
                name="orchestration-test",
                status="ACTIVE",
            )
        )
        db.flush()
        db.add(
            ProjectVersionEntity(
                project_version_id=ids["version"],
                project_id=ids["project"],
                tenant_id=ids["tenant"],
                version_no=1,
                status="ACTIVE",
            )
        )
    repo = RuntimeRepository(sessions)
    repo.create_snapshot_and_run(
        snapshot_id=UUID(ids["snapshot"]),
        workflow_run_id=UUID(ids["run"]),
        tenant_id=UUID(ids["tenant"]),
        project_version_id=UUID(ids["version"]),
        graph_definition_version=GRAPH_VERSION,
        state_schema_version=STATE_VERSION,
        langgraph_runtime_version=installed_version("langgraph"),
        checkpointer_version=installed_version("langgraph-checkpoint-postgres"),
    )
    manifest = tmp_path / "ids.json"
    manifest.write_text(json.dumps(ids))

    def worker(action):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1] / "src"))
        return json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(Path(__file__).with_name("phase1l_a_worker.py")),
                    action,
                    str(manifest),
                ],
                env=env,
                text=True,
                timeout=60,
            )
        )

    first = worker("start")
    assert first["status"] == "REVIEW_REQUIRED" and first["reviews"] == 1
    for locale in ("zh-HK", "en-US", "zh-CN"):
        ids["preferred_locale"] = locale
        manifest.write_text(json.dumps(ids))
        assert worker("inspect") == first
    ids["preferred_locale"] = "zh-HK"
    manifest.write_text(json.dumps(ids))
    duplicate = worker("start")
    assert duplicate == first
    with sessions() as db:
        review = db.scalar(
            select(ReviewTaskEntity).where(ReviewTaskEntity.workflow_run_id == ids["run"])
        )
        snapshot = db.get(AnalysisSnapshotEntity, ids["snapshot"])
        snapshot_before = {c.name: getattr(snapshot, c.name) for c in snapshot.__table__.columns}
        ids["decision"] = ReviewDecisionDTO(
            review_id=UUID(review.review_id),
            decision=decision_code,
            decided_by="reviewer",
            provenance={
                "source_type": "test-human",
                "source_ref": "reviewer",
                "generated_by": "test-human",
            },
        ).model_dump(mode="json")
    ids["preferred_locale"] = "en-US"
    manifest.write_text(json.dumps(ids))
    runtime, factory, _ = adapter(ids)
    assert factory.authorization.authorize_review(UUID(ids["run"]), ids["decision"])
    forged = dict(ids["decision"], decided_by="another-actor")
    with pytest.raises(PermissionError):
        factory.authorize_resume(UUID(ids["run"]), forged)
    with pytest.raises(ValueError):
        runtime.start(
            UUID(ids["run"]),
            dict(factory.initial_state(UUID(ids["run"])), completed_steps=["risk"]),
        )
    resumed = worker("resume")
    assert resumed["status"] == ("WARNING" if decision_code == "APPROVE" else "FAILED")
    assert resumed["reviews"] == 1
    assert resumed["checkpoint_id"] != first["checkpoint_id"]
    for locale in ("zh-CN", "zh-HK", "en-US"):
        ids["preferred_locale"] = locale
        manifest.write_text(json.dumps(ids))
        assert worker("inspect") == resumed
        assert worker("resume") == resumed
    events = list(runtime.stream_events(UUID(ids["run"])))
    assert events and len({e.event_id for e in events}) == len(events)
    assert {"RUNNING", "WAITING", "REVIEW_REQUIRED"} <= {e.status for e in events}
    assert all(e.workflow_run_id == UUID(ids["run"]) for e in events)
    assert all("raw_event_name" not in e.payload for e in events)
    assert resumed["checkpoint"]["identity"]["analysis_snapshot_id"] == ids["snapshot"]
    with sessions() as db:
        snapshot = db.get(AnalysisSnapshotEntity, ids["snapshot"])
        assert {
            c.name: getattr(snapshot, c.name) for c in snapshot.__table__.columns
        } == snapshot_before
    foreign = dict(ids, tenant=str(uuid4()))
    for locale in ("zh-CN", "zh-HK", "en-US"):
        foreign["preferred_locale"] = locale
        foreign_runtime, _, _ = adapter(foreign)
        with pytest.raises(PermissionError):
            foreign_runtime.inspect_checkpoint_state(UUID(ids["run"]))
        with pytest.raises(PermissionError):
            list(foreign_runtime.stream_events(UUID(ids["run"])))
