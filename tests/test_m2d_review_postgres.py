"""Canonical review history, CAS and current authorization on real PostgreSQL."""

# ruff: noqa: F401,F811 -- shared PostgreSQL fixture graph
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from phase1l_b_worker import build
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from test_phase1j_postgres import fixture, foundation_i
from test_phase1l_b_postgres import foundation_j, manifest

from crossborder_compliance.application.review_services import (
    HumanReviewService,
    ReviewDecisionRequest,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresReviewRepository,
)
from crossborder_compliance.infrastructure.persistence.review_governance import ReviewConflict

pytestmark = pytest.mark.runtime_smoke


def pending(f):
    m = manifest(f, review=True)
    runtime, factory = build(m)
    run = UUID(m["run"])
    runtime.inspect_checkpoint_state(run)  # Official saver DDL precedes delivery lock.
    assert runtime.start(run, factory.initial_state(run)).status == "REVIEW_REQUIRED"
    context = RepositoryContext.user(UUID(f["tenant"]), "author", set(m["scopes"]))
    repo = PostgresReviewRepository(f["sf"], context)
    page = repo.list()
    assert page.total == 1
    return repo, page.items[0], runtime, factory, m


def command(task, code, key=None):
    return ReviewDecisionRequest(
        decision=code,
        expected_record_version=task.record_version,
        idempotency_key=key or str(uuid4()),
        comment="Governed reviewer action",
    )


def test_request_changes_history_no_resume_and_duplicate_cas(foundation_j):
    repo, task, runtime, _factory, _m = pending(foundation_j)
    before = runtime.inspect_checkpoint_state(task.workflow_run_id)
    request = command(task, "REQUEST_CHANGES")
    service = HumanReviewService(repo, lambda _: pytest.fail("REQUEST_CHANGES must not resume"))
    view = service.decide(task.review_id, request)
    assert view.status == "PENDING" and view.presentation_state == "CHANGES_REQUESTED"
    assert view.record_version == task.record_version + 1 and len(view.history) == 1
    assert service.decide(task.review_id, request) == view
    assert runtime.get_status(task.workflow_run_id) == "REVIEW_REQUIRED"
    assert runtime.inspect_checkpoint_state(task.workflow_run_id) == before
    with pytest.raises(ReviewConflict, match="REVIEW_VERSION_CONFLICT"):
        repo.decide(task.review_id, command(task, "REJECT"))
    with pytest.raises(ReviewConflict, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        repo.decide(task.review_id, command(task, "REJECT", request.idempotency_key))


def test_reject_is_review_boundary_not_failed_and_history_immutable(foundation_j):
    f = foundation_j
    repo, task, runtime, _factory, _m = pending(f)
    service = HumanReviewService(repo, lambda _: pytest.fail("REJECT must not resume"))
    view = service.decide(task.review_id, command(task, "REJECT"))
    assert view.status == "REJECTED" and view.allowed_actions == () and len(view.history) == 1
    assert runtime.get_status(task.workflow_run_id) == "REVIEW_REQUIRED"
    with f["sf"]() as session:
        history = session.get(b.ReviewDecisionEntity, str(view.history[0].decision_id))
        history.comment = "overwrite"
        with pytest.raises(DBAPIError, match="immutable review governance history"):
            session.commit()
        session.rollback()
    with f["sf"]() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(b.AuditEventEntity)
                .where(
                    b.AuditEventEntity.workflow_run_id == str(task.workflow_run_id),
                    b.AuditEventEntity.event_type == "REVIEW_DECISION_RECORDED",
                )
            )
            == 1
        )


def test_approval_reexecutes_owner_duplicate_identity_and_history(foundation_j):
    repo, task, runtime, _factory, _m = pending(foundation_j)
    request = command(task, "APPROVE")
    service = HumanReviewService(repo, lambda _: runtime)
    value = service.decide(task.review_id, request)
    assert value.status == "APPROVED" and len(value.history) == 1
    assert runtime.get_status(task.workflow_run_id) == "COMPLETED"
    before = runtime.inspect_checkpoint_state(task.workflow_run_id)
    assert before["values"]["visits"]["requirement"] == 2
    assert service.decide(task.review_id, request) == value
    assert runtime.inspect_checkpoint_state(task.workflow_run_id) == before
    assert value.analysis_snapshot_id == task.analysis_snapshot_id


def test_current_tenant_project_role_and_list_filters(foundation_j):
    f = foundation_j
    repo, task, _runtime, _factory, m = pending(f)
    assert (
        repo.list(
            project_id=task.project_id, owning_stage="requirement", status="PENDING", limit=1
        ).total
        == 1
    )
    assert repo.list(status="APPROVED").total == 0
    assert repo.list(offset=1, limit=1).items == ()
    for ctx in (
        RepositoryContext.user(uuid4(), "author", set(m["scopes"])),
        RepositoryContext.user(UUID(f["tenant"]), "other", {"workflow:read", "workflow:review"}),
    ):
        other = PostgresReviewRepository(f["sf"], ctx)
        with pytest.raises(LookupError):
            other.read(task.review_id)
        assert other.list().total == 0
    scopes = set(m["scopes"]) - {"workflow:review"}
    reader = PostgresReviewRepository(
        f["sf"], RepositoryContext.user(UUID(f["tenant"]), "author", scopes)
    )
    assert reader.read(task.review_id).allowed_actions == ()
    with pytest.raises(LookupError):
        reader.decide(task.review_id, command(task, "APPROVE"))


def test_concurrent_reviewers_one_cas_winner(foundation_j):
    repo, task, _runtime, _factory, _m = pending(foundation_j)

    def submit(_):
        try:
            repo.decide(task.review_id, command(task, "REQUEST_CHANGES"))
            return "PASS"
        except ReviewConflict as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, range(2)))
    assert sorted(outcomes) == ["PASS", "REVIEW_VERSION_CONFLICT"]
    assert len(repo.read(task.review_id).history) == 1


def test_delivery_failure_recovery_uses_persisted_approval(foundation_j):
    repo, task, runtime, _factory, _m = pending(foundation_j)
    request = command(task, "APPROVE")

    def unavailable(_):
        raise ConnectionError("delivery unavailable after commit")

    with pytest.raises(ConnectionError):
        HumanReviewService(repo, unavailable).decide(task.review_id, request)
    value = repo.read(task.review_id)
    assert value.status == "APPROVED" and value.continuation_status == "RESUME_PENDING"
    assert value.allowed_actions == ("RESUME",) and len(value.history) == 1
    value = HumanReviewService(repo, lambda _: runtime).resume(task.review_id)
    assert (
        value.continuation_status == "CONTINUED"
        and runtime.get_status(task.workflow_run_id) == "COMPLETED"
    )
    assert HumanReviewService(repo, lambda _: runtime).resume(task.review_id) == value
    assert len(value.history) == 1


def test_approval_process_restart_keeps_canonical_history_and_checkpoint(foundation_j, tmp_path):
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo, task, runtime, _factory, m = pending(foundation_j)
    decision, _ = repo.decide(task.review_id, command(task, "APPROVE"))
    m["decision"] = decision.model_dump(mode="json")
    path = tmp_path / "refs.json"
    path.write_text(json.dumps(m))

    def fresh():
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("phase1l_b_worker.py")),
                "resume",
                str(path),
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=180,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout.strip().splitlines()[-1])

    first = fresh()
    assert first["status"] == "COMPLETED" and first["state"]["visits"]["requirement"] == 2
    assert fresh()["checkpoint_id"] == first["checkpoint_id"]
    assert runtime.inspect_checkpoint_state(task.workflow_run_id)["values"] == first["state"]
    assert len(repo.read(task.review_id).history) == 1


def test_required_role_current_on_read_write_and_direct_resume(foundation_j):
    f = foundation_j
    repo, task, runtime, _factory, m = pending(f)
    with f["sf"]() as session, session.begin():
        row = session.get(b.ReviewTaskEntity, str(task.review_id))
        row.required_role = "review:legal"
    assert repo.read(task.review_id).allowed_actions == ()
    with pytest.raises(LookupError):
        repo.decide(task.review_id, command(task, "APPROVE"))
    elevated = PostgresReviewRepository(
        f["sf"],
        RepositoryContext.user(UUID(f["tenant"]), "author", set(m["scopes"]) | {"review:legal"}),
    )
    decision, _ = elevated.decide(task.review_id, command(task, "APPROVE"))
    assert repo.read(task.review_id).allowed_actions == ()
    with pytest.raises(LookupError):
        runtime.resume(task.workflow_run_id, decision)
    assert runtime.get_status(task.workflow_run_id) == "REVIEW_REQUIRED"
    assert repo.list(order="CREATED_ASC").items[0].review_id == task.review_id
    with pytest.raises(ValueError):
        repo.list(order="unsafe")


def test_direct_worker_approval_records_canonical_snapshot_audit(foundation_j):
    from crossborder_compliance.domain.contracts import ReviewDecisionDTO

    repo, task, runtime, _factory, _m = pending(foundation_j)
    decision = ReviewDecisionDTO(
        review_id=task.review_id,
        decision="APPROVE",
        decided_by="author",
        provenance={
            "source_type": "human_review",
            "source_ref": str(task.review_id),
            "generated_by": "author",
        },
    )
    runtime.resume(task.workflow_run_id, decision.model_dump(mode="json"))
    assert runtime.get_status(task.workflow_run_id) == "COMPLETED"
    with foundation_j["sf"]() as session:
        audit = session.scalar(
            select(b.AuditEventEntity).where(
                b.AuditEventEntity.workflow_run_id == str(task.workflow_run_id),
                b.AuditEventEntity.event_type == "REVIEW_DECISION_RECORDED",
            )
        )
        assert audit.analysis_snapshot_id == str(task.analysis_snapshot_id)
        assert audit.tenant_id == str(repo._context.tenant_id)
    runtime.resume(task.workflow_run_id, decision.model_dump(mode="json"))
    assert len(repo.read(task.review_id).history) == 1
