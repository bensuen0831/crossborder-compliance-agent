"""Production intake lifecycle on actual PostgreSQL and canonical START/READ."""

# ruff: noqa: F401,F811 -- inherited PostgreSQL fixture graph
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_phase1j_postgres import fixture, foundation_i, foundation_j

from crossborder_compliance.application.intake_services import (
    CreateProjectFromIntake,
    UpdateIntakeDraft,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.intake_composition import intake_service
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    ProjectVersionEntity,
)
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.intake import router as intake_router
from crossborder_compliance.interfaces.api.routes.workflow import router

pytestmark = pytest.mark.runtime_smoke


def setup(f):
    scopes = set(f["jctx"].permission.scopes) | {
        "project:create",
        "project:read",
        "project:update",
        "project:confirm",
        "workflow:execute",
        "workflow:read",
    }
    context = RepositoryContext.user(UUID(f["tenant"]), "author", scopes)
    app = FastAPI()
    app.include_router(intake_router)
    app.include_router(router)
    app.state.knowledge_session_factory = f["sf"]
    app.dependency_overrides[get_repository_context] = lambda: context
    facts = dict(
        analysis_as_of_date=date.today().isoformat(),
        business_scenario=f["scenario"],
        selected_products=[f["a"]],
        source_locations=[f["juri"]],
        destination_locations=[f["juri"]],
        business_purpose="Generic",
        scenario_description="User provided scenario",
        requested_outputs=["APPLICABILITY"],
    )
    return app, TestClient(app), context, facts


def create(client, facts, key=None):
    return client.post(
        "/api/v1/projects",
        json=dict(name=str(uuid4()), facts=facts, idempotency_key=key or str(uuid4())),
    )


def test_draft_restore_version_stale_and_immutable_history(foundation_j):
    f = foundation_j
    _, c, _, facts = setup(f)
    first = create(c, facts)
    assert first.status_code == 201, first.text
    one = first.json()
    url = f"/api/v1/projects/{one['project_id']}/intake"
    assert one["status"] == "DRAFT" and one["analysis_snapshot_id"] is None
    assert c.get(url).json() == one
    payload = dict(
        expected_version=1,
        idempotency_key=str(uuid4()),
        facts={**facts, "business_purpose": "changed"},
    )
    saved = c.put(url, json=payload)
    assert saved.status_code == 200, saved.text
    two = saved.json()
    assert two["version"] == 2 and two["intake"]["business_purpose"] == "changed"
    assert c.put(url, json=payload).json() == two
    assert c.put(url, json={**payload, "idempotency_key": str(uuid4())}).status_code == 409
    history = c.get(url + "?version=1").json()
    assert history["status"] == "SUPERSEDED"
    assert history["intake"] == one["intake"]


def test_create_idempotency_and_payload_conflict(foundation_j):
    _, c, _, facts = setup(foundation_j)
    payload = dict(name=str(uuid4()), facts=facts, idempotency_key=str(uuid4()))
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: c.post("/api/v1/projects", json=payload), range(2)))
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json() == results[1].json()
    assert c.post("/api/v1/projects", json={**payload, "name": "different"}).status_code == 409


def test_browser_authority_injection_and_required_confirmation(foundation_j):
    _, c, _, facts = setup(foundation_j)
    for field in [
        "tenant_id",
        "PermissionContext",
        "policy_id",
        "risk_score",
        "final_path",
        "workflow_run_id",
        "confirmed",
    ]:
        assert (
            c.post(
                "/api/v1/projects",
                json=dict(name="x", facts=facts, idempotency_key="k", **{field: "bad"}),
            ).status_code
            == 422
        )
        assert create(c, {**facts, field: "bad"}).status_code == 422
    one = create(c, {"analysis_as_of_date": "2026-01-01"}).json()
    url = f"/api/v1/projects/{one['project_id']}/intake"
    assert c.post(url + "/confirm", json={"expected_version": 1}).status_code == 422
    assert (
        c.post(
            f"/api/v1/projects/{one['project_id']}/snapshots/{uuid4()}/workflow", json={}
        ).status_code
        == 404
    )


def test_cross_tenant_actor_and_current_permissions(foundation_j):
    app, c, ctx, facts = setup(foundation_j)
    one = create(c, facts).json()
    url = f"/api/v1/projects/{one['project_id']}/intake"
    for context in [
        RepositoryContext.user(uuid4(), "author", set(ctx.permission.scopes)),
        RepositoryContext.user(ctx.tenant_id, "other", set(ctx.permission.scopes)),
        RepositoryContext.user(ctx.tenant_id, "author", set()),
    ]:
        app.dependency_overrides[get_repository_context] = lambda context=context: context
        assert c.get(url).status_code == 404
        assert c.post(url + "/confirm", json={"expected_version": 1}).status_code == 404


def test_atomic_confirmation_exact_snapshot_and_canonical_start(foundation_j):
    f = foundation_j
    app, c, ctx, facts = setup(f)
    one = create(c, facts).json()
    url = f"/api/v1/projects/{one['project_id']}/intake"
    from crossborder_compliance.application.intake_services import ConfirmProjectIntake
    intake_service(f["sf"], ctx).confirm(
        UUID(one["project_id"]), ConfirmProjectIntake(expected_version=1)
    )
    result = c.post(url + "/confirm", json={"expected_version": 1})
    assert result.status_code == 200, result.text
    confirmed = result.json()
    assert confirmed["status"] == "CONFIRMED"
    assert c.post(url + "/confirm", json={"expected_version": 1}).json() == confirmed
    with f["sf"]() as s:
        snaps = s.scalars(
            select(AnalysisSnapshotEntity).where(
                AnalysisSnapshotEntity.project_version_id == one["project_version_id"]
            )
        ).all()
        assert len(snaps) == 1 and snaps[0].provenance_json["intake_version"] == 1
        assert snaps[0].provenance_json["confirmed_by"] == "author"
    assert (
        c.put(
            url, json=dict(expected_version=1, idempotency_key=str(uuid4()), facts=facts)
        ).status_code
        == 409
    )
    start = f"/api/v1/projects/{one['project_id']}/snapshots/{confirmed['analysis_snapshot_id']}/workflow"
    response = c.post(start, json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["project_id"] == one["project_id"]
    assert result["analysis_snapshot_id"] == confirmed["analysis_snapshot_id"]
    assert result["workflow_run_id"] == confirmed["workflow_run_id"]
    assert c.post(start, json={}).json() == result
    assert c.get(f"/api/v1/workflows/{result['workflow_run_id']}").json() == result
    # Absent user facts/evidence cannot produce a fabricated final decision.
    assert result["status"] in ["WARNING", "REVIEW_REQUIRED", "COMPLETED"], result


def test_failed_preparation_rolls_back_snapshot_and_confirmation(foundation_j):
    f = foundation_j
    _, c, ctx, facts = setup(f)
    one = create(c, facts).json()
    svc = intake_service(f["sf"], ctx)

    def fail(*args):
        raise ValueError("proven preparation failure")

    svc.prepare_snapshot = fail
    from crossborder_compliance.application.intake_services import ConfirmProjectIntake

    with pytest.raises(ValueError, match="proven"):
        svc.confirm(UUID(one["project_id"]), ConfirmProjectIntake(expected_version=1))
    assert svc.read(UUID(one["project_id"])).status == "DRAFT"
    with f["sf"]() as s:
        assert not s.scalar(
            select(AnalysisSnapshotEntity).where(
                AnalysisSnapshotEntity.project_version_id == one["project_version_id"]
            )
        )
