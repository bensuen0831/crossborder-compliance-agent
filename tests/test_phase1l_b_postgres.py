"""Real E/F/G/H/I/J services through the canonical PostgreSQL runtime."""

# ruff: noqa: F811,F401 -- pytest fixture imports
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from phase1l_b_worker import build
from sqlalchemy import func, select, update
from test_phase1j_postgres import fixture, foundation_i
from test_phase1j_postgres import foundation_j as original_foundation_j

from crossborder_compliance.application.workflow_formal import FormalWorkflowPlan
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.contracts import ReviewDecisionDTO
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import decision_models as j
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.workflows.canonical import GRAPH_VERSION, PIPELINE, STATE_VERSION
from crossborder_compliance.workflows.langgraph_adapter import installed_version

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def foundation_j(foundation_i, request):
    from types import SimpleNamespace

    from m2c_policy_fixtures import configure_authorities
    params = dict(getattr(request, 'param', {}))
    params['before_j_initialization'] = configure_authorities
    return original_foundation_j.__wrapped__(foundation_i, SimpleNamespace(param=params))


def manifest(f, *, review=False):
    wf, request_ref = uuid4(), uuid4()
    with f["sf"]() as s, s.begin():
        pin = s.scalar(
            select(c.AnalysisSnapshotContextPinEntity).where(
                c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == f["snapshot"]
            )
        )
        s.add(
            b.WorkflowRunEntity(
                workflow_run_id=str(wf),
                thread_id=str(wf),
                tenant_id=f["tenant"],
                analysis_snapshot_id=f["snapshot"],
                status="RUNNING",
                graph_definition_version=GRAPH_VERSION,
                state_schema_version=STATE_VERSION,
                langgraph_runtime_version=installed_version("langgraph"),
                checkpointer_version=installed_version("langgraph-checkpoint-postgres"),
            )
        )
        context_run = pin.context_resolution_run_id
    scenario = f["request"].subject_type == "SCENARIO"
    plan = FormalWorkflowPlan(
        tenant_id=f["tenant"],
        project_id=f["project"],
        analysis_snapshot_id=f["snapshot"],
        request_context_ref=request_ref,
        context_resolution_run_id=context_run,
        mode="SCENARIO_LEVEL" if scenario else "DATA_AWARE",
        subject_type=f["request"].subject_type,
        subject_id=f["request"].subject_id,
        classification_data_item_ids=() if scenario else (f["request"].subject_id,),
        scheme_version_id=None if scenario else f["scheme_version"],
        applicability=[{"jurisdiction_id": f["juri"], "config_id": f["config"]["definition_id"]}],
        retrieval_query=dict(
            project_id=f["project"],
            analysis_snapshot_id=f["snapshot"],
            policy_id=f["policy"]["policy_id"],
            query_text="Generic",
            idempotency_key="overridden-by-stage",
            subject_type="PROJECT" if scenario else "DATA_ITEM",
            subject_id=f["project"] if scenario else str(f["request"].subject_id),
        ),
        requirement_review=review,
    )
    return dict(
        run=str(wf),
        tenant=f["tenant"],
        scopes=sorted(
            set(f["jctx"].permission.scopes)
            | {"workflow:execute", "workflow:read", "workflow:review"}
        ),
        plan=plan.model_dump(mode="json"),
        locale="zh-CN",
    )


@pytest.mark.parametrize("foundation_i", [{}, {"no_data": True}], indirect=True)
def test_real_full_formal_chain_both_modes_and_locale_replay(foundation_j):
    f = foundation_j
    m = manifest(f)
    runtime, factory = build(m)
    wf = UUID(m["run"])

    def deliver(_):
        current, own_factory = build(m)
        return current.start(wf, own_factory.initial_state(wf))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(deliver, range(2)))
    assert all(r.status == "COMPLETED" for r in results)
    result = results[0]
    checkpoint = runtime.inspect_checkpoint_state(wf)
    assert result.status == "COMPLETED", (
        checkpoint["values"]["current_step"],
        checkpoint["values"]["reason_codes"],
    )
    state = checkpoint["values"]
    assert state["completed_steps"] == [s.value for s in PIPELINE]
    final_id = UUID(state["result_refs"]["final_path"])
    final = f["jrepo"].read_decision("FINAL_PATH", final_id)
    assert final.items[0].status == "CONDITIONAL_PROPOSAL"
    assert final.items[0].selected_candidate_path_id is not None
    assert all(not a.performed for a in final.items[0].actions)
    assert state["result_refs"]["documents"] == state["result_refs"]["report"]
    assert state["result_refs"]["documents"] != str(final_id)
    docs = f["jrepo"].read_formal_result(
        "DOCUMENT_REQUIREMENT", UUID(state["result_refs"]["documents"])
    )
    assert docs.items[0].requirement_level == "REQUIRED"
    if m["plan"]["mode"] == "SCENARIO_LEVEL":
        assert "classification" not in state["result_refs"]
    for locale in ["zh-HK", "en-US"]:
        m["locale"] = locale
        other, _ = build(m)
        read = other.inspect_checkpoint_state(wf)
        assert (
            read["config"]["configurable"]["checkpoint_id"]
            == checkpoint["config"]["configurable"]["checkpoint_id"]
        )
        assert read["values"] == state
        assert other.start(wf, factory.initial_state(wf)).status == "COMPLETED"
    with f["sf"]() as s:
        events = s.scalars(
            select(b.WorkflowEventEntity).where(b.WorkflowEventEntity.workflow_run_id == str(wf))
        ).all()
        assert events and all("preferred_locale" not in e.payload_json for e in events)
        assert any(
            e.payload_json.get("result_refs", {}).get("final_path") == [str(final_id)]
            for e in events
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.MODELS["FINAL_PATH"])
                .where(j.MODELS["FINAL_PATH"].analysis_snapshot_id == f["snapshot"])
            )
            == 1
        )


@pytest.mark.parametrize("foundation_i", [{}, {"no_data": True}], indirect=True)
def test_full_chain_process_restart_review_and_duplicate_resume(foundation_j, tmp_path):
    f = foundation_j
    m = manifest(f, review=True)
    path = tmp_path / "refs.json"

    def run(action):
        path.write_text(json.dumps(m))
        r = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("phase1l_b_worker.py")),
                action,
                str(path),
            ],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")
                + os.pathsep
                + os.environ.get("PYTHONPATH", ""),
            },
            timeout=180,
        )
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout.strip().splitlines()[-1])

    first = run("start")
    assert first["status"] == "REVIEW_REQUIRED" and first["next"] == ["human_review"]
    with f["sf"]() as s:
        review = s.scalar(
            select(b.ReviewTaskEntity).where(b.ReviewTaskEntity.workflow_run_id == m["run"])
        )
        m["decision"] = ReviewDecisionDTO(
            review_id=review.review_id,
            decision="APPROVE",
            decided_by="author",
            comment="Requirement confirmation only",
            provenance={
                "source_type": "human_review",
                "source_ref": review.review_id,
                "generated_by": "author",
            },
        ).model_dump(mode="json")
    m["locale"] = "en-US"
    second = run("resume")
    assert second["status"] == "COMPLETED", json.dumps(second, sort_keys=True)
    assert run("resume")["checkpoint_id"] == second["checkpoint_id"]
    assert run("start")["checkpoint_id"] == second["checkpoint_id"]
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.ReviewTaskEntity)
                .where(b.ReviewTaskEntity.workflow_run_id == m["run"])
            )
            == 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.MODELS["FINAL_PATH"])
                .where(j.MODELS["FINAL_PATH"].analysis_snapshot_id == f["snapshot"])
            )
            == 1
        )


def test_current_permission_tenant_snapshot_and_evidence_revocation(foundation_j):
    f = foundation_j
    m = manifest(f)
    runtime, factory = build(m)
    wf = UUID(m["run"])
    assert runtime.start(wf, factory.initial_state(wf)).status == "COMPLETED"
    m["tenant"] = str(uuid4())
    with pytest.raises(PermissionError):
        build(m)
    m["tenant"] = f["tenant"]
    m["scopes"].remove(f"project:{f['project']}:comply")
    with pytest.raises(PermissionError):
        build(m)
    m = manifest(f)
    m["plan"]["analysis_snapshot_id"] = str(uuid4())
    with pytest.raises(ValueError):
        build(m)
    source = f["repo"].get_source(f["source"])
    f["repo"].update_source(f["source"], {"enabled": False}, source["record_version"])
    with pytest.raises(LookupError):
        f["jrepo"].read_decision(
            "FINAL_PATH",
            UUID(runtime.inspect_checkpoint_state(wf)["values"]["result_refs"]["final_path"]),
        )


def test_delivery_contention_is_not_a_node_retry_and_releases_on_error(foundation_j):
    from crossborder_compliance.application.workflow_skeleton import (
        StageTransientFailure,
        WorkflowDeliveryRetryableFailure,
    )
    from crossborder_compliance.infrastructure.persistence.workflow_delivery_guard import (
        PostgresWorkflowDeliveryGuard,
    )

    f = foundation_j
    m = manifest(f)
    wf = UUID(m["run"])
    first = PostgresWorkflowDeliveryGuard(f["sf"], f["jctx"])
    bounded = PostgresWorkflowDeliveryGuard(f["sf"], f["jctx"], 0.02)
    with first.acquire(wf):
        with pytest.raises(WorkflowDeliveryRetryableFailure) as raised:
            with bounded.acquire(wf):
                pytest.fail("concurrent delivery entered")
        assert not isinstance(raised.value, StageTransientFailure)
    with bounded.acquire(wf):
        pass


def test_process_crash_after_formal_save_before_checkpoint_recovers_without_duplicate(
    foundation_j, tmp_path
):
    f = foundation_j
    m = manifest(f)
    m["crash_stage"] = "obligation"
    path = tmp_path / "crash-refs.json"
    path.write_text(json.dumps(m))
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")
        + os.pathsep
        + os.environ.get("PYTHONPATH", ""),
    }
    worker = str(Path(__file__).with_name("phase1l_b_worker.py"))
    stopped = subprocess.run(
        [sys.executable, worker, "start", str(path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert stopped.returncode == 73, stopped.stderr
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.MODELS["OBLIGATION"])
                .where(j.MODELS["OBLIGATION"].analysis_snapshot_id == f["snapshot"])
            )
            == 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.MODELS["FINAL_PATH"])
                .where(j.MODELS["FINAL_PATH"].analysis_snapshot_id == f["snapshot"])
            )
            == 0
        )
    del m["crash_stage"]
    path.write_text(json.dumps(m))
    resumed = subprocess.run(
        [sys.executable, worker, "start", str(path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads(resumed.stdout.strip().splitlines()[-1])
    assert result["status"] == "COMPLETED"
    with f["sf"]() as s:
        for stage in j.MODELS:
            assert (
                s.scalar(
                    select(func.count())
                    .select_from(j.MODELS[stage])
                    .where(j.MODELS[stage].analysis_snapshot_id == f["snapshot"])
                )
                == 1
            )


def test_sufficiency_cannot_consume_another_authorized_subjects_retrieval(foundation_j):
    from test_phase1g_persistence_postgres import query, service

    from crossborder_compliance.application.workflow_skeleton import (
        SemanticStep,
        StageExecutionRequest,
    )
    from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
        PostgresRetrievalRepository,
    )

    f = foundation_j
    m = manifest(f)
    _, factory = build(m)
    repo = PostgresRetrievalRepository(f["sf"], f["ctx"])
    other = service(f, repo).retrieve(
        query(f, f["policy"], subject_type="PROJECT", subject_id=f["project"])
    )
    refs = {step: UUID(m["plan"]["context_resolution_run_id"]) for step in PIPELINE[:6]}
    refs[SemanticStep.KNOWLEDGE_SCOPE] = UUID(f["snapshot"])
    refs[SemanticStep.RETRIEVAL] = UUID(other["retrieval_run_id"])
    request = StageExecutionRequest(
        identity=factory.authorize(UUID(m["run"]), "execute"),
        step=SemanticStep.SUFFICIENCY,
        result_refs=refs,
        idempotency_key="subject-scope-regression",
        timeout_seconds=30,
    )
    with pytest.raises(PermissionError, match="retrieval scope mismatch"):
        factory.stages[SemanticStep.SUFFICIENCY].execute(request)
