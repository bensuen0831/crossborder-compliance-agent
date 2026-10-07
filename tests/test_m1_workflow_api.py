"""Real PostgreSQL canonical workflow through reference-only HTTP transport."""

# ruff: noqa: F401,F811 -- inherited real-PG fixtures
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_phase1j_postgres import fixture, foundation_i
from test_phase1l_b_postgres import foundation_j, manifest

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.routes.workflow import router

pytestmark = pytest.mark.runtime_smoke


def host(f, review=False):
    m = manifest(f, review=review)
    app = FastAPI()
    app.include_router(router)
    app.state.knowledge_session_factory = f["sf"]
    app.state.formal_workflow_host = lambda context, project, snapshot: (m["run"], m["plan"])
    context = RepositoryContext.user(UUID(f["tenant"]), "author", set(m["scopes"]))
    app.dependency_overrides[get_repository_context] = lambda: context
    return app, TestClient(app), m, context


def test_public_start_read_idempotency_and_authorization(foundation_j):
    f = foundation_j
    app, client, m, context = host(f)
    url = f"/api/v1/projects/{f['project']}/snapshots/{f['snapshot']}/workflow"
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        context.tenant_id, "author", set(m["scopes"]) - {"workflow:read"}
    )
    assert client.post(url, json={}).status_code == 404
    app.dependency_overrides[get_repository_context] = lambda: context
    for forbidden in (
        "tenant_id",
        "facts",
        "classification",
        "applicability",
        "risk",
        "recommendation",
        "final_path",
        "policy_id",
        "workflow_run_id",
    ):
        assert client.post(url, json={forbidden: "injected"}).status_code == 422
    first = client.post(url, json={})
    assert first.status_code == 200, first.text
    value = first.json()
    assert value["status"] == "COMPLETED" and value["workflow_run_id"] == m["run"]
    assert value["analysis_snapshot_id"] == f["snapshot"]
    assert all(
        value["result_refs"][key] for key in ("classification", "applicability", "retrieval")
    )
    assert set(value) == {
        "workflow_run_id",
        "project_id",
        "analysis_snapshot_id",
        "status",
        "current_step",
        "result_refs",
        "reason_codes",
        "review_id",
        "fallback_ref",
    }
    assert "final_path" not in value["result_refs"]
    assert client.post(url, json={}).json() == value
    assert client.get(f"/api/v1/workflows/{m['run']}").json() == value
    assert client.get(f"/api/v1/workflows/{uuid4()}").status_code == 404
    assert client.post(url.replace(f["snapshot"], str(uuid4())), json={}).status_code == 404
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        uuid4(), "author", set(m["scopes"])
    )
    assert client.get(f"/api/v1/workflows/{m['run']}").status_code == 404
    assert client.post(url, json={}).status_code == 404
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        context.tenant_id, "other", set(m["scopes"])
    )
    assert client.get(f"/api/v1/workflows/{m['run']}").status_code == 404
    app.dependency_overrides[get_repository_context] = lambda: RepositoryContext.user(
        context.tenant_id, "other", set()
    )
    assert client.get(f"/api/v1/workflows/{m['run']}").status_code == 404
    app.dependency_overrides[get_repository_context] = lambda: context
    del app.state.formal_workflow_host
    assert client.post(url, json={}).status_code == 409
    app.dependency_overrides.clear()
    assert client.post(url, json={}).status_code == 401


def test_public_review_state_preserves_pending_identifier(foundation_j):
    f = foundation_j
    _, client, m, _ = host(f, review=True)
    value = client.post(
        f"/api/v1/projects/{f['project']}/snapshots/{f['snapshot']}/workflow", json={}
    ).json()
    assert value["status"] == "REVIEW_REQUIRED" and value["review_id"]
    assert not value["result_refs"].get("classification")
    assert client.get(f"/api/v1/workflows/{m['run']}").json() == value


@pytest.mark.parametrize("foundation_i", [{"partial": True}], indirect=True)
def test_public_insufficient_evidence_cannot_be_success(foundation_j):
    f = foundation_j
    _, client, _, _ = host(f)
    response = client.post(
        f"/api/v1/projects/{f['project']}/snapshots/{f['snapshot']}/workflow", json={}
    )
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["status"] == "WARNING" and value["fallback_ref"]
    assert value["result_refs"]["retrieval"] and not value["result_refs"].get("applicability")
