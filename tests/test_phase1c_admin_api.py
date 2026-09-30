from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.models import TenantEntity
from crossborder_compliance.interfaces.api.dependencies import get_repository_context
from crossborder_compliance.interfaces.api.main import app


pytestmark = pytest.mark.runtime_smoke


def _sf():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    return build_session_factory(settings.database_url)[1]


def _seed_tenant(sf, tenant):
    with sf() as session, session.begin():
        session.add(TenantEntity(tenant_id=str(tenant), name=f"API-{tenant}"))


def _client_with_context(context: RepositoryContext) -> TestClient:
    app.dependency_overrides[get_repository_context] = lambda: context
    return TestClient(app)


def test_project_user_cannot_publish_but_can_read_active_runtime_metadata() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)

    admin = RepositoryContext.user(
        tenant,
        "metadata-admin",
        scopes={
            "metadata:admin",
            "metadata:review",
            "metadata:publish",
            "metadata:self-review",
        },
    )
    try:
        client = _client_with_context(admin)
        create = client.post(
            "/api/v1/admin/scenarios",
            json={
                "code": f"api-scenario-{uuid4().hex[:6]}",
                "display_name": "API Scenario",
                "payload": {"visible": True},
            },
        )
        assert create.status_code == 200, create.text
        draft = create.json()
        version_id = draft["version_id"]

        submit = client.post(
            f"/api/v1/admin/scenarios/{version_id}/submit-review",
            json={"expected_record_version": draft["record_version"]},
        )
        assert submit.status_code == 200, submit.text
        approve = client.post(
            f"/api/v1/admin/scenarios/{version_id}/approve",
            json={"expected_record_version": submit.json()["record_version"]},
        )
        assert approve.status_code == 200, approve.text
        publish = client.post(
            f"/api/v1/admin/scenarios/{version_id}/publish",
            json={"expected_record_version": approve.json()["record_version"]},
        )
        assert publish.status_code == 200, publish.text

        project_user = RepositoryContext.user(
            tenant, "project-user", scopes={"project:read"}
        )
        client = _client_with_context(project_user)
        forbidden = client.post(
            f"/api/v1/admin/scenarios/{version_id}/archive",
            json={"expected_record_version": publish.json()["record_version"]},
        )
        assert forbidden.status_code == 403

        runtime = client.get("/api/v1/metadata/scenarios")
        assert runtime.status_code == 200, runtime.text
        body = runtime.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["version_id"] == version_id
        assert body["health"]["source_of_truth"] is False
    finally:
        app.dependency_overrides.pop(get_repository_context, None)


def test_model_admin_response_never_returns_secret_and_unsafe_url_rejected() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)
    admin = RepositoryContext.user(
        tenant,
        "model-admin",
        scopes={
            "metadata:admin",
            "metadata:review",
            "metadata:publish",
            "metadata:self-review",
        },
    )
    try:
        client = _client_with_context(admin)
        response = client.post(
            "/api/v1/admin/models",
            json={
                "code": f"api-model-{uuid4().hex[:6]}",
                "display_name": "API Model",
                "payload": {
                    "provider_type": "INTERNAL_API",
                    "model_id": "configurable-model",
                    "deployment_ref": "private-deployment",
                    "endpoint_config": {"url": "https://models.example.invalid/v1"},
                    "secret_ref": "secret://tenant/model-api",
                    "capabilities": ["TEXT"],
                },
            },
        )
        assert response.status_code == 200, response.text
        text = response.text.lower()
        assert "secret_ref" not in text
        assert "secret://tenant/model-api" not in text

        unsafe = client.post(
            "/api/v1/admin/models",
            json={
                "code": f"unsafe-model-{uuid4().hex[:6]}",
                "display_name": "Unsafe Model",
                "payload": {
                    "provider_type": "GENERIC_REST",
                    "model_id": "unsafe",
                    "endpoint_config": {"url": "file:///etc/passwd"},
                    "secret_ref": "secret://tenant/unsafe",
                },
            },
        )
        assert unsafe.status_code == 422
    finally:
        app.dependency_overrides.pop(get_repository_context, None)
