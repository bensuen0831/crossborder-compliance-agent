"""Real-PG composition/authentication evidence, never real-law or live-model PASS."""

import ast
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from scripts.kb01.business import save
from scripts.kb01.business_host import (
    create_app, high_cvss_findings, native_safety, password_record, profile, verified_native_database,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.models import TenantEntity

pytestmark = pytest.mark.runtime_smoke
PASSWORD = "non-production-focused-test-password"


@pytest.fixture
def business(tmp_path):
    url = get_settings().database_url
    assert url.startswith("postgresql"), "Real PostgreSQL is mandatory; do not skip"
    engine, sf = build_session_factory(url)
    tenant = str(uuid4())
    with sf() as s, s.begin():
        s.add(TenantEntity(tenant_id=tenant, name="Isolated authentication engineering test"))
    path = tmp_path / "accounts.json"
    data = {"schema_version": "STAGE1_LOCAL_ACCEPTANCE_V1", "tenant_id": tenant,
            "technical_worker_actor_id": str(uuid4()),
            "tenant_label": "Engineering test, not legal acceptance", "users": {
                "author": {"actor_id": str(uuid4()), "display_name": "Author", "role": "business",
                           "scopes": ["project:create", "project:read"], **password_record(PASSWORD)}}}
    save(path, data)
    app = create_app(path, sf, secret_factory=None)
    client = TestClient(app, base_url="http://127.0.0.1:18011")
    yield client, app, path, data
    client.close()
    engine.dispose()


def login(client):
    return client.post("/api/v1/login", json={"username": "author", "password": PASSWORD})


def test_anonymous_session_and_canonical_intake_are_not_granted(business):
    client, app, _, _ = business
    assert client.get("/api/v1/session").status_code == 401
    assert client.get("/api/v1/acceptance-readiness").status_code == 401
    assert client.post("/api/v1/projects", json={}).status_code == 401
    assert not app.dependency_overrides


def test_login_has_http_only_cookie_without_demo_or_fabricated_context(business):
    client, _, _, _ = business
    response = login(client)
    assert response.status_code == 200
    assert response.json()["demo"] is False and response.json()["contexts"] == []
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert PASSWORD not in response.text
    assert client.get("/api/v1/session").status_code == 200
    assert client.post("/api/v1/logout").status_code == 200
    assert client.get("/api/v1/session").status_code == 401


def test_credential_failure_and_validation_never_echo_password(business):
    client, _, _, _ = business
    response = client.post("/api/v1/login", json={"username": "author", "password": PASSWORD + "bad"})
    assert response.status_code == 401 and PASSWORD not in response.text
    response = client.post("/api/v1/login", json={"username": "author", "password": PASSWORD, "actor_id": "spoof"})
    assert response.status_code == 422 and PASSWORD not in response.text and "spoof" not in response.text


@pytest.mark.parametrize("headers", [{"Origin": "https://other.example"}, {"Host": "evil.example:18011"}])
def test_browser_origin_and_dns_rebinding_are_refused(business, headers):
    client, _, _, _ = business
    assert client.post("/api/v1/login", json={"username": "author", "password": PASSWORD}, headers=headers).status_code == 403


def test_profile_role_revocation_invalidates_existing_session(business):
    client, _, path, data = business
    assert login(client).status_code == 200
    data["users"]["author"]["scopes"] = []
    save(path, data)
    assert client.get("/api/v1/session").status_code == 401


def test_unreadable_identity_fails_closed_without_server_error_or_secrets(business):
    client, _, path, _ = business
    assert login(client).status_code == 200
    path.chmod(0o644)
    response = client.get("/api/v1/session")
    assert response.status_code == 503
    assert response.json() == {"detail": "ACCEPTANCE_IDENTITY_CONFIGURATION_UNAVAILABLE"}
    assert PASSWORD not in response.text


def test_client_headers_cannot_choose_tenant_actor_or_admin_authority(business):
    client, _, _, _ = business
    assert login(client).status_code == 200
    response = client.get("/api/v1/admin/model-providers", headers={
        "X-Tenant-ID": str(uuid4()), "X-Actor-ID": "admin", "X-Permissions": "metadata:admin"})
    assert response.status_code in {403, 404}
    assert client.get("/api/v1/session").json()["permissions"] == ["project:create", "project:read"]


def test_empty_tenant_does_not_fabricate_model_or_legal_acceptance(business):
    client, app, _, _ = business
    assert login(client).status_code == 200
    data = client.get("/api/v1/acceptance-readiness").json()
    assert data["model_configuration"] == {"providers": 0, "active_deployments": 0, "health_check_is_not_workflow_evidence": True}
    assert data["user_e2e_test_readiness"] == "BLOCKED"
    assert data["legal_accuracy_execution"] == "NOT_EXECUTED" and not data["stage2_started"]
    assert app.state.document_file_policy is None
    assert app.state.knowledge_management_worker is None


def test_profile_has_all_canonical_channels_without_demo_routes(business):
    _, app, _, _ = business
    paths = set(app.openapi()["paths"])
    for path in ("/api/v1/projects", "/api/v1/reviews", "/api/v1/admin/model-providers",
                 "/api/v1/projects/{project_id}/candidate-preparation",
                 "/api/v1/admin/knowledge-management/upload-sessions"):
        assert path in paths
    assert "/m0-demo/login" not in paths


def test_private_profile_and_password_requirements(business):
    _, _, path, data = business
    with pytest.raises(ValueError):
        password_record("short")
    path.chmod(0o644)
    with pytest.raises(ValueError, match="PERMISSIONS"):
        profile(path)
    path.chmod(0o600)
    data["users"]["author"]["scopes"].append("system")
    save(path, data)
    with pytest.raises(ValueError, match="AUTHORITY"):
        profile(path)


def test_missing_or_invalid_tool_evidence_never_enables_processing(tmp_path):
    assert native_safety(None)["status"] == "BLOCKED"
    path = tmp_path / "invalid-tool.json"
    path.write_text("{}")
    assert native_safety(path)["reason"] == "NATIVE_TOOL_EVIDENCE_INVALID"


@pytest.mark.parametrize("severity,score", [("MEDIUM", 7.1), ("LOW", 7.8), ("HIGH", 9.8)])
def test_vendor_severity_cannot_hide_remaining_high_cvss(severity, score):
    findings = high_cvss_findings({"Results": [{"Vulnerabilities": [{
        "VulnerabilityID": "SYNTHETIC_SECURITY_REGRESSION", "PkgName": "package",
        "Severity": severity, "CVSS": {"vendor": {"V3Score": score}},
    }]}]})
    assert len(findings) == 1 and findings[0]["score"] == score


@pytest.mark.parametrize("verification,image", [("UNVERIFIED", "a" * 64), ("PASS", "b" * 64)])
def test_unverified_or_wrong_image_signature_manifest_is_refused(tmp_path, verification, image):
    # Negative manifest validation only; no fabricated genuine CVD acceptance.
    save(tmp_path / "official-signatures.json", {
        "signature_verification": verification, "image_id": "sha256:" + image,
        "files": {name: {} for name in ("main.cvd", "daily.cvd", "bytecode.cvd")},
    })
    with pytest.raises(ValueError, match="OFFICIAL_DATABASE_PROVENANCE_REQUIRED"):
        verified_native_database(tmp_path, "sha256:" + "a" * 64)


def test_business_composition_has_no_fixture_seed_or_system_context():
    for file in ("business.py", "business_host.py"):
        source = (Path(__file__).parents[1] / "scripts/kb01" / file).read_text()
        tree = ast.parse(source)
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(name.startswith(("tests", "test_", "stage1_business_fixtures", "scripts.m0_preview")) for name in imports)
        assert "RepositoryContext.system(" not in source
        assert "dependency_overrides[" not in source
