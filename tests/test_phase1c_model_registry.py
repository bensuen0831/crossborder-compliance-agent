from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    ModelProviderVersionEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresModelRegistryRepository,
)
from crossborder_compliance.infrastructure.persistence.models import TenantEntity
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresModelAdminRepository,
)
from crossborder_compliance.infrastructure.registry import ModelRegistry


pytestmark = pytest.mark.runtime_smoke


def _sf():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    return build_session_factory(settings.database_url)[1]


def _seed_tenant(sf, tenant):
    with sf() as session, session.begin():
        session.add(TenantEntity(tenant_id=str(tenant), name=f"Model-{tenant}"))


def _ctx(tenant):
    return RepositoryContext.user(
        tenant,
        "model-admin",
        scopes={"metadata:admin", "metadata:review", "metadata:publish"},
    )


def _publish_model(sf, tenant, *, code: str, provider_type: str, secret_ref: str):
    context = _ctx(tenant)
    repo = PostgresModelAdminRepository(sf, context)
    draft = repo.create_draft(
        code=code,
        display_name=f"Model {code}",
        payload={
            "provider_type": provider_type,
            "model_id": code,
            "deployment_ref": f"deployment-{code}",
            "endpoint_config": {"url": "https://models.example.invalid/v1"},
            "base_url_ref": f"endpoint-ref:{code}",
            "auth_type": "BEARER_SECRET_REF",
            "secret_ref": secret_ref,
            "deployment_type": "API",
            "trust_level": "ENTERPRISE",
            "data_boundary": "TENANT",
            "capabilities": ["TEXT", "STRUCTURED_OUTPUT"],
            "context_window": 32000,
            "max_output_tokens": 4096,
            "timeout_policy": {"seconds": 30},
            "retry_policy": {"max_attempts": 2},
            "cost_metadata": {"unit": "CONFIG_ONLY"},
            "enabled": True,
        },
    )
    pending = repo.transition(
        UUID(str(draft["version_id"])),
        target_status="PENDING_REVIEW",
        expected_record_version=1,
    )
    approved = repo.transition(
        UUID(str(draft["version_id"])),
        target_status="APPROVED",
        expected_record_version=int(pending["record_version"]),
    )
    active = repo.transition(
        UUID(str(draft["version_id"])),
        target_status="ACTIVE",
        expected_record_version=int(approved["record_version"]),
    )
    return repo, draft, active


def test_model_registry_provider_types_capability_disable_and_secret_boundary() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)

    _, draft_a, _ = _publish_model(
        sf,
        tenant,
        code=f"model-a-{uuid4().hex[:6]}",
        provider_type="OPENAI_COMPATIBLE",
        secret_ref="secret://tenant/model-a",
    )
    runtime_repo = PostgresModelRegistryRepository(
        sf, RepositoryContext.user(tenant, "runtime-model", scopes=set())
    )
    registry = ModelRegistry(runtime_repo)
    registry.refresh()
    resolved = registry.resolve(capability="TEXT")
    assert resolved is not None
    assert resolved["model_definition_id"] == draft_a["definition_id"]
    assert resolved["provider_type"] == "OPENAI_COMPATIBLE"
    assert "secret_ref" not in resolved
    assert "api_key" not in resolved
    assert "access_token" not in resolved

    with sf() as session:
        provider_version = session.get(
            ModelProviderVersionEntity, str(draft_a["provider_version_id"])
        )
        assert provider_version is not None
        assert provider_version.secret_ref == "secret://tenant/model-a"

    runtime_repo.set_provider_enabled(UUID(str(draft_a["provider_id"])), False)
    registry.refresh()
    assert registry.resolve(capability="TEXT") is None

    runtime_repo.set_provider_enabled(UUID(str(draft_a["provider_id"])), True)
    runtime_repo.set_model_enabled(UUID(str(draft_a["definition_id"])), False)
    registry.refresh()
    assert registry.resolve(capability="TEXT") is None

    runtime_repo.set_model_enabled(UUID(str(draft_a["definition_id"])), True)
    registry.refresh()
    assert registry.resolve(capability="STRUCTURED_OUTPUT") is not None


def test_switch_model_a_to_model_b_requires_only_registry_metadata_change() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)

    _, draft_a, _ = _publish_model(
        sf,
        tenant,
        code=f"route-a-{uuid4().hex[:6]}",
        provider_type="OPENAI_COMPATIBLE",
        secret_ref="secret://tenant/route-a",
    )
    runtime_repo = PostgresModelRegistryRepository(
        sf, RepositoryContext.user(tenant, "runtime", scopes=set())
    )
    registry = ModelRegistry(runtime_repo)
    registry.refresh()
    first = registry.resolve(capability="TEXT")
    assert first is not None
    assert first["model_definition_id"] == draft_a["definition_id"]

    _, draft_b, _ = _publish_model(
        sf,
        tenant,
        code=f"route-b-{uuid4().hex[:6]}",
        provider_type="INTERNAL_API",
        secret_ref="secret://tenant/route-b",
    )
    runtime_repo.set_model_enabled(UUID(str(draft_a["definition_id"])), False)
    registry.refresh()
    second = registry.resolve(capability="TEXT")
    assert second is not None
    assert second["model_definition_id"] == draft_b["definition_id"]
    assert second["provider_type"] == "INTERNAL_API"

    # The registry/metadata changed; no Agent/Skill/LangGraph object participates in switching.
    assert registry.health()["source_of_truth"] is False


def test_disabled_deployment_is_excluded_from_model_registry() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)
    _, draft, _ = _publish_model(
        sf,
        tenant,
        code=f"disabled-{uuid4().hex[:6]}",
        provider_type="GENERIC_REST",
        secret_ref="secret://tenant/disabled",
    )
    runtime_repo = PostgresModelRegistryRepository(
        sf, RepositoryContext.user(tenant, "runtime", scopes=set())
    )
    runtime_repo.set_deployment_enabled(UUID(str(draft["version_id"])), False)
    registry = ModelRegistry(runtime_repo)
    registry.refresh()
    assert registry.list() == []
