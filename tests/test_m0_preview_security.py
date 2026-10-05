"""Track C local UAT adapter; security is exercised before data reaches a client."""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from phase1g_fixtures import publish
from test_phase1f_postgres import binding, fixture as fixture
from test_phase1g_persistence_postgres import policies

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m0_uat_server", ROOT / "scripts/m0_preview/server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def demo(fixture, tmp_path, monkeypatch):
    f = fixture
    allowed = publish(f, [binding(f, permissions=["read:internal"])])
    forbidden = publish(f, [binding(f, permissions=["secret:read"])])
    _, policy, _ = policies(f)
    from uuid import uuid4

    base = {
        "tenant_id": f["tenant"], "actor_id": "author", "display_name": "UAT User A",
        "tenant_label": "Synthetic Tenant A", "permissions": sorted(f["ctx"].permission.scopes),
        "contexts": [{"project_id": f["project"], "display_name": "Generic Project", "analysis_snapshot_id": f["snapshot"], "policy_id": policy["policy_id"]}],
    }
    path = tmp_path / "personas.json"
    path.write_text(json.dumps({"A": base, "B": {**base, "tenant_id": str(uuid4()), "actor_id": "outsider", "contexts": []}}))
    monkeypatch.setenv("M0_LOCAL_UAT", "1")
    app = server.create_demo_app(path)
    return TestClient(app), f, policy, allowed, forbidden


def test_m0_adapter_requires_explicit_local_uat(monkeypatch, tmp_path):
    monkeypatch.delenv("M0_LOCAL_UAT", raising=False)
    with pytest.raises(RuntimeError, match="Explicit"):
        server.create_demo_app(tmp_path / "missing.json")


def test_m0_login_requires_registered_persona_and_ignores_client_tenant(demo):
    c, f, *_ = demo
    assert c.get("/m0-demo/session").status_code == 401
    assert c.post("/m0-demo/login", json={"persona": "A", "tenant_id": "forged"}).status_code == 422
    assert c.post("/m0-demo/login", json={"persona": "UNKNOWN"}).status_code == 403
    login = c.post("/m0-demo/login", json={"persona": "A"})
    assert login.status_code == 200
    assert "HttpOnly" in login.headers["set-cookie"]
    assert c.cookies["m0_session"] not in login.text
    assert login.headers["cache-control"] == "no-store"
    current = c.get("/m0-demo/session", headers={"X-Tenant-ID": "forged"}).json()
    assert current["contexts"][0]["project_id"] == f["project"]
    assert current["organization_label"] is None and current["department_label"] is None


def test_m0_blocks_cross_origin_and_external_host(demo):
    c, *_ = demo
    assert c.post("/m0-demo/login", json={"persona": "A"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.get("/health/live", headers={"Host": "public.example"}).status_code == 403


def test_m0_real_retrieval_filters_permission_before_browser_and_tenant_b_cannot_read_a(demo):
    c, f, policy, visible, forbidden = demo
    assert c.post("/m0-demo/login", json={"persona": "A"}).status_code == 200
    payload = {
        "analysis_snapshot_id": f["snapshot"], "policy_id": policy["policy_id"],
        "query_text": "Generic", "idempotency_key": "m0-isolation",
    }
    route = f"/api/v1/projects/{f['project']}/knowledge/retrieve"
    response = c.post(route, json=payload)
    assert response.status_code == 200, response.status_code
    data = response.json()
    items = data["rag_context_pack"]["evidence_pack"]["items"]
    assert items and {x["knowledge_version_id"] for x in items} == {visible["knowledge_version_id"]}
    assert forbidden["knowledge_version_id"] not in response.text
    assert data["rag_context_pack"]["fallback_guidance_context"]["operational_next_steps"]
    assert c.post("/m0-demo/login", json={"persona": "B"}).status_code == 200
    assert c.get("/api/v1/retrieval-runs/" + data["retrieval_run_id"]).status_code == 404
    assert c.post(route, json={**payload, "idempotency_key": "b-guess"}).status_code == 404


def test_m0_logout_revokes_cookie_session(demo):
    c, *_ = demo
    c.post("/m0-demo/login", json={"persona": "A"})
    token = c.cookies["m0_session"]
    assert c.post("/m0-demo/logout").status_code == 200
    c.cookies.set("m0_session", token)
    assert c.get("/m0-demo/session").status_code == 401
