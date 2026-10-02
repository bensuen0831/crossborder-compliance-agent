from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from crossborder_compliance.application.metadata_services import (
    AdminAuthorizationError,
    AdminActionPolicy,
    lifecycle_transition_allowed,
)
from crossborder_compliance.domain.metadata import (
    GovernanceStatus,
    ModelCapabilityCode,
    ModelProviderType,
    validate_endpoint_config,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.registry import ProjectionRegistry, TemplateRegistry
from crossborder_compliance.interfaces.api.main import app


def test_endpoint_config_blocks_dangerous_protocol_and_embedded_credentials() -> None:
    with pytest.raises(ValueError):
        validate_endpoint_config({"url": "file:///etc/passwd"})
    with pytest.raises(ValueError):
        validate_endpoint_config({"url": "https://user:password@example.invalid/model"})
    validate_endpoint_config({"url": "https://models.example.invalid/v1"})
    validate_endpoint_config({"url": "internal://private-model-service"})


def test_technical_model_codes_are_stable_not_business_metadata_enums() -> None:
    assert ModelProviderType.OPENAI_COMPATIBLE.value == "OPENAI_COMPATIBLE"
    assert ModelProviderType.INTERNAL_API.value == "INTERNAL_API"
    assert ModelCapabilityCode.STRUCTURED_OUTPUT.value == "STRUCTURED_OUTPUT"
    assert ModelCapabilityCode.EMBEDDING.value == "EMBEDDING"


def test_lifecycle_transition_contract() -> None:
    assert lifecycle_transition_allowed("DRAFT", "PENDING_REVIEW")
    assert lifecycle_transition_allowed("PENDING_REVIEW", "APPROVED")
    assert lifecycle_transition_allowed("APPROVED", "ACTIVE")
    assert lifecycle_transition_allowed("ACTIVE", "SUPERSEDED")
    assert not lifecycle_transition_allowed("DRAFT", "ACTIVE")
    assert not lifecycle_transition_allowed("ARCHIVED", "ACTIVE")


def test_admin_policy_rejects_ordinary_project_user() -> None:
    context = RepositoryContext.user(uuid4(), "project-user", scopes={"project:read"})
    with pytest.raises(AdminAuthorizationError):
        AdminActionPolicy().require(context, "metadata:publish")


def test_projection_registry_is_stale_until_explicit_refresh() -> None:
    state = [
        {
            "definition_id": str(uuid4()),
            "version_id": str(uuid4()),
            "version_no": 1,
            "code": "first",
        }
    ]
    registry = ProjectionRegistry(lambda: list(state))
    assert registry.list() == []
    registry.refresh()
    assert len(registry.list()) == 1
    first_version = registry.version()

    state.append(
        {
            "definition_id": str(uuid4()),
            "version_id": str(uuid4()),
            "version_no": 1,
            "code": "second",
        }
    )
    assert len(registry.list()) == 1
    assert registry.version() == first_version
    registry.refresh()
    assert len(registry.list()) == 2
    assert registry.version() != first_version
    assert registry.health()["source_of_truth"] is False


class _TemplateSource:
    def load_templates(self):
        return [
            {
                "definition_id": str(uuid4()),
                "version_id": str(uuid4()),
                "version_no": 1,
                "code": "enterprise",
                "display_name": "Enterprise",
                "template_type": "ENTERPRISE_TEMPLATE",
            },
            {
                "definition_id": str(uuid4()),
                "version_id": str(uuid4()),
                "version_no": 1,
                "code": "regulatory",
                "display_name": "Regulatory",
                "template_type": "REGULATORY_TEMPLATE",
            },
        ]


def test_regulatory_template_precedence_over_enterprise_projection() -> None:
    registry = TemplateRegistry(_TemplateSource())
    registry.refresh()
    resolved = registry.resolve()
    assert resolved is not None
    assert resolved["template_type"] == "REGULATORY_TEMPLATE"


def test_admin_api_requires_trusted_server_side_repository_context() -> None:
    client = TestClient(app)
    response = client.post(
        f"/api/v1/admin/scenarios/{uuid4()}/publish",
        json={"expected_record_version": 1},
    )
    assert response.status_code == 401


def test_admin_and_runtime_metadata_routes_are_explicitly_exposed() -> None:
    paths = set(app.openapi()["paths"])
    for resource in (
        "jurisdictions",
        "scenarios",
        "products",
        "classification-schemes",
        "models",
        "prompts",
        "rules",
        "templates",
        "knowledge-collections",
    ):
        assert f"/api/v1/admin/{resource}" in paths
    for path in (
        "/api/v1/metadata/jurisdictions",
        "/api/v1/metadata/scenarios",
        "/api/v1/metadata/products",
        "/api/v1/metadata/data-types",
        "/api/v1/metadata/data-flow-types",
        "/api/v1/metadata/classification-schemes",
        "/api/v1/metadata/model-capabilities",
    ):
        assert path in paths
