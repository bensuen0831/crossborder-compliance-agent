from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_phase1h_postgres import foundation as foundation
from test_phase1h_postgres import payload

from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.main import app

pytestmark = pytest.mark.runtime_smoke


@contextmanager
def client(context):
    if context is not None:
        app.dependency_overrides[get_repository_context] = lambda: context
    try:
        with TestClient(app) as value:
            yield value
    finally:
        app.dependency_overrides.pop(get_repository_context, None)


def request(f):
    return {
        "analysis_snapshot_id": str(f["snapshot"]),
        "data_item_id": str(f["item"]),
        "scheme_version_id": str(f["scheme_version"]),
    }


def test_trusted_auth_required_and_no_public_rule_evaluation(foundation):
    f = foundation
    with client(None) as c:
        assert (
            c.post(f"/api/v1/projects/{f['project']}/classifications", json=request(f)).status_code
            == 401
        )
        assert (
            c.post("/api/v1/rules/evaluate", json={"code": "__import__('os')"}).status_code == 404
        )
    ordinary = RepositoryContext.user(f["tenant"], "ordinary")
    with client(ordinary) as c:
        assert c.post(f"/api/v1/admin/rules/{f['rule_version']}/test").status_code == 403
        assert c.get(f"/api/v1/admin/rules/{f['rule_version']}").status_code == 403
        assert (
            c.post(f"/api/v1/projects/{f['project']}/classifications", json=request(f)).status_code
            == 404
        )


def test_reference_only_request_execution_and_result_read(foundation):
    f = foundation
    with client(f["runtime"]) as c:
        base = f"/api/v1/projects/{f['project']}"
        pinned = c.post(
            f"{base}/snapshots/{f['snapshot']}/classification-pins",
            json={"scheme_version_id": str(f["scheme_version"])},
        )
        assert pinned.status_code == 200, pinned.text
        response = c.post(f"{base}/classifications", json=request(f))
        assert response.status_code == 200, response.text
        out = response.json()
        assert out["status"] == "CLASSIFIED"
        ident = out["result"]["classification_result_id"]
        assert (
            c.get(f"/api/v1/classifications/{ident}").json()["generated_by"]
            == "SAFE_RULE_ENGINE_V1"
        )
        repeat = c.post(f"{base}/classifications", json=request(f)).json()
        assert repeat["result"]["classification_result_id"] == ident
        for extra in (
            {"values": {"count": 999}},
            {"tenant_id": str(uuid4())},
            {"classification_result": {"confidence": 1}},
        ):
            assert (
                c.post(f"{base}/classifications", json={**request(f), **extra}).status_code == 422
            )
    unauthorized = RepositoryContext.user(f["tenant"], "other", {"classification:read"})
    with client(unauthorized) as c:
        assert c.get(f"/api/v1/classifications/{ident}").status_code == 404


def test_admin_rule_version_validate_and_scheme_version_interfaces(foundation):
    f = foundation
    with client(f["writer"]) as c:
        detail = c.get(f"/api/v1/admin/classification-schemes/{f['scheme_version']}")
        assert detail.status_code == 200
        membership = detail.json()["applicability"]
        version = c.post(
            f"/api/v1/admin/classification-schemes/{f['scheme']}/versions",
            json={"payload": {"applicability": membership}},
        )
        assert version.status_code == 200, version.text
        assert version.json()["version_no"] == 2
        response = c.post(
            f"/api/v1/admin/rules/{f['rule']}/versions", json={"payload": payload(f["contract"])}
        )
        assert response.status_code == 200, response.text
        ident = response.json()["version_id"]
        assert c.post(f"/api/v1/admin/rules/{ident}/validate").json()["status"] == "PASS"
        assert c.get(f"/api/v1/admin/rules/{ident}").json()["runtime_contract"]["dsl_version"] == 1
        assert (
            c.post(
                f"/api/v1/admin/rules/{uuid4()}/versions", json={"payload": payload(f["contract"])}
            ).status_code
            == 404
        )
