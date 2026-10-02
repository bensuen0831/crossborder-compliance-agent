from __future__ import annotations

from uuid import uuid4

import pytest

from crossborder_compliance.application.metadata_services import (
    AdminAuthorizationError,
    MetadataLifecycleService,
    lifecycle_transition_allowed,
)
from crossborder_compliance.domain.metadata import GovernanceStatus, validate_endpoint_config
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.interfaces.api.routes import admin_metadata, metadata


class _FakeAdminRepo:
    def __init__(self):
        self.called = False

    def create_definition(self, **kwargs):
        self.called = True
        return {"definition_id": str(uuid4())}

    def create_version(self, **kwargs):
        self.called = True
        return {"version_id": str(uuid4()), "record_version": 1}

    def update_draft(self, *args, **kwargs):
        self.called = True
        return {}

    def transition(self, *args, **kwargs):
        self.called = True
        return {}

    def history(self, *args, **kwargs):
        self.called = True
        return []

    def impact_preview(self, *args, **kwargs):
        self.called = True
        return {}


def test_admin_rbac_blocks_project_user_before_repository_call() -> None:
    tenant = uuid4()
    context = RepositoryContext.user(tenant, "project-user", scopes=set())
    repo = _FakeAdminRepo()
    service = MetadataLifecycleService(repo, context)

    with pytest.raises(AdminAuthorizationError):
        service.create_draft(
            kind="SCENARIO",
            code="scenario-x",
            display_name="Scenario X",
            payload={},
        )
    assert repo.called is False


def test_lifecycle_transition_contract() -> None:
    assert lifecycle_transition_allowed("DRAFT", "PENDING_REVIEW")
    assert lifecycle_transition_allowed("PENDING_REVIEW", "APPROVED")
    assert lifecycle_transition_allowed("APPROVED", "ACTIVE")
    assert lifecycle_transition_allowed("ACTIVE", "SUPERSEDED")
    assert not lifecycle_transition_allowed("DRAFT", "ACTIVE")
    assert not lifecycle_transition_allowed("ARCHIVED", "ACTIVE")


def test_model_endpoint_validation_blocks_dangerous_protocols_and_public_http() -> None:
    validate_endpoint_config({"url": "https://model-gateway.example/api"})
    validate_endpoint_config({"url": "http://127.0.0.1:8000/v1"})
    validate_endpoint_config({"url": "internal://private-model/service"})

    with pytest.raises(ValueError):
        validate_endpoint_config({"url": "file:///etc/passwd"})
    with pytest.raises(ValueError):
        validate_endpoint_config({"url": "http://public.example/v1"})
    with pytest.raises(ValueError):
        validate_endpoint_config({"url": "https://user:password@example.com/v1"})


def test_admin_api_has_all_required_resource_lifecycle_routes() -> None:
    paths = {route.path for route in admin_metadata.router.routes}
    resources = (
        "jurisdictions",
        "scenarios",
        "products",
        "classification-schemes",
        "models",
        "prompts",
        "rules",
        "templates",
        "knowledge-collections",
    )
    for resource in resources:
        base = f"/api/v1/admin/{resource}"
        assert base in paths
        assert f"{base}/{{version_id}}/draft" in paths
        for action in ("submit-review", "approve", "reject", "publish", "supersede", "archive"):
            assert f"{base}/{{version_id}}/{action}" in paths
        assert f"{base}/{{definition_id}}/versions" in paths
        assert f"{base}/{{definition_id}}/impact-preview" in paths


def test_runtime_metadata_api_has_required_dynamic_option_routes() -> None:
    paths = {route.path for route in metadata.router.routes}
    for resource in (
        "jurisdictions",
        "scenarios",
        "products",
        "data-types",
        "data-flow-types",
        "classification-schemes",
        "model-capabilities",
    ):
        assert f"/api/v1/metadata/{resource}" in paths


def test_stable_governance_status_is_technical_not_business_option_enum() -> None:
    assert GovernanceStatus.DRAFT.value == "DRAFT"
    assert GovernanceStatus.ACTIVE.value == "ACTIVE"
    assert "COUNTRY" not in {item.value for item in GovernanceStatus}
