from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_phase1f_postgres import fixture as fixture
from test_phase1g_persistence_postgres import policies

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.routes.retrieval import router

pytestmark = pytest.mark.runtime_smoke


def client(f, context):
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)

    @app.middleware("http")
    async def trusted(request, call_next):
        if context is not None:
            request.state.repository_context = context
        return await call_next(request)

    return TestClient(app)


def test_retrieval_api_dtos_auth_snapshot_and_scope_injection(fixture):
    f = fixture
    _, p, _ = policies(f)
    c = client(f, f["ctx"])
    payload = dict(
        analysis_snapshot_id=f["snapshot"],
        policy_id=p["policy_id"],
        query_text="Generic",
        idempotency_key="api",
    )
    route = f"/api/v1/projects/{f['project']}/knowledge/retrieve"
    assert c.post(route, json=dict(payload, allowed_product_ids=[f["b"]])).status_code == 422
    response = c.post(route, json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    rag = result["rag_context_pack"]
    assert rag["fallback_guidance_context"]["operational_next_steps"]
    run = result["retrieval_run_id"]
    assert c.get("/api/v1/retrieval-runs/" + run).status_code == 200
    pack = rag["evidence_pack"]["evidence_pack_id"]
    assert c.get("/api/v1/evidence-packs/" + pack).status_code == 200
    suff = rag["knowledge_sufficiency"]["sufficiency_result_id"]
    assert c.get("/api/v1/knowledge-sufficiency/" + suff).status_code == 200
    assert client(f, None).get("/api/v1/retrieval-runs/" + run).status_code == 401
    other = client(f, RepositoryContext.user(uuid4(), "other"))
    assert other.get("/api/v1/retrieval-runs/" + run).status_code == 404
    same = client(f, RepositoryContext.user(UUID(f["tenant"]), "other"))
    assert same.get("/api/v1/retrieval-runs/" + run).status_code == 403
    assert (
        c.post(
            route, json=dict(payload, analysis_snapshot_id=str(uuid4()), idempotency_key="other")
        ).status_code
        == 404
    )


def test_admin_policy_typed_creation_publish_and_permission(fixture):
    f = fixture
    c = client(f, f["ctx"])
    route = "/api/v1/admin/knowledge-sufficiency-policies"
    response = c.post(route, json={"parameters": {}})
    assert response.status_code == 201, response.text
    policy = response.json()
    endpoint = route + "/versions/" + policy["policy_version_id"] + "/publish"
    assert c.post(endpoint, json={"expected_record_version": 99}).status_code == 409
    assert c.post(endpoint, json={"expected_record_version": 1}).status_code == 200
    assert c.get(route + "/" + policy["policy_version_id"]).status_code == 200
    noadmin = client(f, RepositoryContext.user(UUID(f["tenant"]), "reader"))
    assert noadmin.post(route, json={"parameters": {}}).status_code == 403


def test_wiki_specific_admin_route_and_runtime_readiness_dto(fixture):
    from phase1g_fixtures import publish

    f = fixture
    v = publish(f)
    c = client(f, f["ctx"])
    response = c.post(
        "/api/v1/admin/wiki",
        json={"title": "Generic Wiki", "knowledge_version_ids": [v["knowledge_version_id"]]},
    )
    assert response.status_code == 201, response.text
    wiki = response.json()["result"]
    assert wiki["lifecycle"] == "DRAFT"
    ready = c.get(
        "/api/v1/admin/knowledge-versions/" + v["knowledge_version_id"] + "/runtime-readiness"
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "READY"
