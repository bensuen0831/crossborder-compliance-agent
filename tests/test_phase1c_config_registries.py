from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    ClassificationBindingEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresConfigRegistrySourceRepository,
)
from crossborder_compliance.infrastructure.persistence.models import (
    JurisdictionEntity,
    TenantEntity,
)
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresClassificationAdminRepository,
)
from crossborder_compliance.infrastructure.registry import (
    ClassificationRegistry,
    KnowledgeRegistry,
    PromptRegistry,
    RuleRegistry,
    TemplateRegistry,
)


pytestmark = pytest.mark.runtime_smoke


def _sf():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    return build_session_factory(settings.database_url)[1]


def _seed_tenant(sf, tenant):
    with sf() as session, session.begin():
        session.add(TenantEntity(tenant_id=str(tenant), name=f"Config-{tenant}"))


def _context(tenant):
    return RepositoryContext.user(
        tenant,
        "config-admin",
        scopes={"metadata:admin", "metadata:review", "metadata:publish"},
    )


def _publish_artifact(sf, tenant, resource: str, code: str, payload: dict[str, object]):
    repo = PostgresGovernedArtifactAdminRepository(sf, _context(tenant), resource)
    draft = repo.create_draft(code=code, display_name=code, payload=payload)
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


def test_prompt_rule_template_knowledge_registries_read_active_versions_only() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)

    _publish_artifact(
        sf,
        tenant,
        "prompts",
        f"prompt-{uuid4().hex[:6]}",
        {
            "template_text": "Return a structured response using the supplied typed context.",
            "capability_requirement": ["STRUCTURED_OUTPUT"],
        },
    )
    _publish_artifact(
        sf,
        tenant,
        "rules",
        f"rule-{uuid4().hex[:6]}",
        {
            "safe_dsl": {"op": "exists", "fact": "input.value"},
            "scope": {"scenario": "CONFIG_ONLY"},
            "priority": 100,
        },
    )
    _publish_artifact(
        sf,
        tenant,
        "templates",
        f"enterprise-template-{uuid4().hex[:6]}",
        {
            "template_type": "ENTERPRISE_TEMPLATE",
            "field_schema": {"type": "object"},
            "content_ref": "template://enterprise/generic",
        },
    )
    _publish_artifact(
        sf,
        tenant,
        "templates",
        f"regulatory-template-{uuid4().hex[:6]}",
        {
            "template_type": "REGULATORY_TEMPLATE",
            "field_schema": {"type": "object"},
            "content_ref": "template://regulatory/generic",
        },
    )
    _publish_artifact(
        sf,
        tenant,
        "knowledge-collections",
        f"knowledge-{uuid4().hex[:6]}",
        {"scope": "GLOBAL", "retrieval_enabled": False},
    )

    # A draft prompt is deliberately left unpublished and must remain runtime-invisible.
    prompt_repo = PostgresGovernedArtifactAdminRepository(
        sf, _context(tenant), "prompts"
    )
    prompt_repo.create_draft(
        code=f"draft-prompt-{uuid4().hex[:6]}",
        display_name="Draft Prompt",
        payload={"template_text": "draft only"},
    )

    source = PostgresConfigRegistrySourceRepository(
        sf, RepositoryContext.user(tenant, "runtime-config", scopes=set())
    )
    prompt_registry = PromptRegistry(source)
    rule_registry = RuleRegistry(source)
    template_registry = TemplateRegistry(source)
    knowledge_registry = KnowledgeRegistry(source)

    for registry in (
        prompt_registry,
        rule_registry,
        template_registry,
        knowledge_registry,
    ):
        registry.refresh()
        assert registry.list()

    assert len(prompt_registry.list()) == 1
    prompt = prompt_registry.list()[0]
    assert prompt["capability_requirement"] == ["STRUCTURED_OUTPUT"]
    assert "country" not in prompt["template_text"].lower()

    rule = rule_registry.list()[0]
    assert rule["safe_dsl"]["op"] == "exists"
    assert "eval" not in str(rule["safe_dsl"]).lower()

    selected_template = template_registry.resolve()
    assert selected_template is not None
    assert selected_template["template_type"] == "REGULATORY_TEMPLATE"

    knowledge = knowledge_registry.list()[0]
    assert knowledge["payload"]["retrieval_enabled"] is False


def test_classification_registry_resolves_versioned_binding_without_country_rule_code() -> None:
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)
    jurisdiction_id = uuid4()
    with sf() as session, session.begin():
        session.add(
            JurisdictionEntity(
                jurisdiction_id=str(jurisdiction_id),
                tenant_id=str(tenant),
                code=f"J-{uuid4().hex[:6]}",
                name="Configurable Jurisdiction",
                metadata_json={},
                status="ACTIVE",
            )
        )

    admin = PostgresClassificationAdminRepository(sf, _context(tenant))
    draft = admin.create_draft(
        code=f"scheme-{uuid4().hex[:6]}",
        display_name="Generic Classification Scheme",
        payload={"applicability": {"source": "metadata"}},
    )
    pending = admin.transition(
        UUID(str(draft["version_id"])),
        target_status="PENDING_REVIEW",
        expected_record_version=1,
    )
    approved = admin.transition(
        UUID(str(draft["version_id"])),
        target_status="APPROVED",
        expected_record_version=int(pending["record_version"]),
    )
    admin.transition(
        UUID(str(draft["version_id"])),
        target_status="ACTIVE",
        expected_record_version=int(approved["record_version"]),
    )

    with sf() as session, session.begin():
        session.add(
            ClassificationBindingEntity(
                classification_binding_id=str(uuid4()),
                tenant_id=str(tenant),
                scheme_version_id=str(draft["version_id"]),
                jurisdiction_id=str(jurisdiction_id),
                industry_ref="GENERIC_INDUSTRY",
                scenario_definition_id=None,
                priority=10,
                status="ACTIVE",
            )
        )

    source = PostgresConfigRegistrySourceRepository(
        sf, RepositoryContext.user(tenant, "classification-runtime", scopes=set())
    )
    registry = ClassificationRegistry(source)
    registry.refresh()
    resolved = registry.resolve(
        jurisdiction_id=jurisdiction_id,
        industry_ref="GENERIC_INDUSTRY",
    )
    assert resolved is not None
    assert resolved["version_id"] == str(draft["version_id"])
    assert resolved["applicability"]["source"] == "metadata"

    inactive = admin.create_draft(
        code=f"draft-scheme-{uuid4().hex[:6]}",
        display_name="Draft Classification Scheme",
        payload={"applicability": {}},
    )
    registry.refresh()
    assert all(
        row["version_id"] != str(inactive["version_id"])
        for row in registry.list()
    )
