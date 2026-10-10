# ruff: noqa: F401,F811 -- imported canonical PostgreSQL fixture graph
"""Public contract isolation and transport-only SDK acceptance over real HTTP."""

import importlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import ValidationError
from test_m2e_http import credential, gateway  # noqa: F401

from crossborder_compliance.interfaces.api.external_openapi import external_openapi

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.runtime_smoke
@pytest.mark.parametrize(
    "path", ["/api/v1/admin/integration-clients", "/api/v1/admin/integration-clients/options"]
)
def test_production_specific_integration_routes_precede_generic_metadata(path, gateway):
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.dependencies import get_repository_context
    from crossborder_compliance.interfaces.api.workflow_app import app

    source, _, _ = gateway
    previous_factory = getattr(app.state, "knowledge_session_factory", None)
    app.state.knowledge_session_factory = source.state.knowledge_session_factory
    app.dependency_overrides[get_repository_context] = source.dependency_overrides[
        get_repository_context
    ]
    try:
        response = TestClient(app).get(path)
        assert response.status_code == 200
        if path.endswith("/options"):
            assert "scopes" in response.json()
    finally:
        app.dependency_overrides.pop(get_repository_context, None)
        if previous_factory is None:
            del app.state.knowledge_session_factory
        else:
            app.state.knowledge_session_factory = previous_factory


def test_external_only_openapi_strict_authority_security_errors():
    spec = external_openapi()
    assert spec["openapi"].startswith("3.") and spec["info"]["version"] == "1.0.0"
    assert all(path.startswith("/api/v1/external/") for path in spec["paths"])
    assert not any("/admin/" in path or "debug" in path for path in spec["paths"])
    assert "IntegrationBearer" in spec["components"]["securitySchemes"]
    assert "secret_ref" not in json.dumps(spec) and "provider_credentials" not in json.dumps(spec)
    for schema in [
        "ExternalProjectCreate",
        "ExternalIntakeUpdate",
        "WorkflowStart",
        "EmptyCommand",
        "WebhookCreate",
    ]:
        assert spec["components"]["schemas"][schema]["additionalProperties"] is False
        assert not {
            "tenant_id",
            "actor_id",
            "permission",
            "checkpoint",
            "provider_api_key",
            "base_url",
        } & set(spec["components"]["schemas"][schema].get("properties", {}))
    for path, methods in spec["paths"].items():
        for _method, operation in methods.items():
            assert operation["responses"]["422"]["content"]["application/json"]["schema"][
                "$ref"
            ].endswith("/GatewayError")
            if not path.endswith("/oauth/token"):
                assert operation["security"] == [{"IntegrationBearer": []}]
    assert spec["x-websocket"]["payload"]["$ref"].endswith("/ExternalWorkflowEvent")


@pytest.mark.runtime_smoke
def test_python_sdk_real_http_auth_intake_cas_no_authority_injection(gateway):
    _, http, _ = gateway
    sys.path.insert(0, str(ROOT / "sdk/python/src"))
    try:
        sdk = importlib.import_module("crossborder_agent")
        made = credential(http)
        api = sdk.AgentClient(str(http.base_url), client=http)
        api.authenticate(made["client"]["client_id"], made["credential"])
        body = {"name": uuid4().hex, "facts": {"analysis_as_of_date": "2026-10-09"}}
        key = uuid4().hex
        one = api.create_project(body, key)
        assert api.create_project(body, key) == one
        assert api.get_intake(one["project_id"]) == one
        two = api.update_intake(
            one["project_id"], {"expected_version": 1, "facts": body["facts"]}, uuid4().hex
        )
        assert two["version"] == 2
        with pytest.raises(sdk.GatewayError) as err:
            api.update_intake(
                one["project_id"], {"expected_version": 1, "facts": body["facts"]}, uuid4().hex
            )
        assert err.value.code == "VERSION_CONFLICT"
        with pytest.raises(ValidationError):
            api.create_project({**body, "tenant_id": str(uuid4())}, uuid4().hex)
    finally:
        sys.path.remove(str(ROOT / "sdk/python/src"))
