from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from crossborder_compliance.application.metadata_services import (
    AdminAuthorizationError,
    MetadataLifecycleService,
    RegistrySyncService,
    SnapshotPinService,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.metadata import GovernanceStatus
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.config_admin_repositories import (
    PostgresGovernedArtifactAdminRepository,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_models import (
    MetadataDefinitionEntity,
    ModelProviderEntity,
    RegistrySyncEventEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    MetadataLifecycleError,
    MetadataOptimisticConcurrencyError,
    PostgresAdminMetadataRepository,
    PostgresConfigRegistrySourceRepository,
    PostgresModelRegistryRepository,
    PostgresRegistrySourceRepository,
    PostgresRegistrySyncEventRepository,
    PostgresSnapshotRegistryPinRepository,
)
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    TenantEntity,
)
from crossborder_compliance.infrastructure.persistence.special_admin_repositories import (
    PostgresClassificationAdminRepository,
    PostgresJurisdictionAdminRepository,
    PostgresModelAdminRepository,
)
from crossborder_compliance.infrastructure.registry import (
    ClassificationRegistry,
    KnowledgeRegistry,
    ModelRegistry,
    PromptRegistry,
    RuleRegistry,
    ScenarioRegistry,
    TemplateRegistry,
)


def _sf():
    settings = get_settings()
    if not settings.database_url.startswith("postgresql"):
        pytest.skip("Phase 1C integration requires real PostgreSQL")
    return build_session_factory(settings.database_url)[1]


def _seed_tenant(sf, tenant_id: UUID) -> None:
    with sf() as session, session.begin():
        session.add(TenantEntity(tenant_id=str(tenant_id), name=f"Tenant-{tenant_id}"))


def _ctx(tenant: UUID, actor: str, *scopes: str) -> RepositoryContext:
    return RepositoryContext.user(tenant, actor, scopes=set(scopes))


def _publish_generic(
    sf,
    tenant: UUID,
    *,
    kind: str,
    code: str,
    payload: dict[str, object],
):
    author_ctx = _ctx(tenant, "author", "metadata:admin", "metadata:review")
    reviewer_ctx = _ctx(tenant, "reviewer", "metadata:review")
    publisher_ctx = _ctx(tenant, "publisher", "metadata:publish")

    author_repo = PostgresAdminMetadataRepository(sf, author_ctx)
    author = MetadataLifecycleService(author_repo, author_ctx)
    draft = author.create_draft(
        kind=kind, code=code, display_name=code, payload=payload
    )
    submitted = author.submit_review(
        UUID(str(draft["version_id"])), expected_record_version=1
    )

    # Reviewer separation is enforced when self-review override is absent.
    with pytest.raises(MetadataLifecycleError):
        author.approve(
            UUID(str(draft["version_id"])),
            expected_record_version=int(submitted["record_version"]),
        )

    reviewer = MetadataLifecycleService(
        PostgresAdminMetadataRepository(sf, reviewer_ctx), reviewer_ctx
    )
    approved = reviewer.approve(
        UUID(str(draft["version_id"])),
        expected_record_version=int(submitted["record_version"]),
    )
    publisher = MetadataLifecycleService(
        PostgresAdminMetadataRepository(sf, publisher_ctx), publisher_ctx
    )
    active = publisher.publish(
        UUID(str(draft["version_id"])),
        expected_record_version=int(approved["record_version"]),
    )
    return draft, active, author_repo, author, reviewer, publisher


class _FailingRegistry:
    def refresh(self):
        raise RuntimeError("simulated cache refresh failure")


@pytest.mark.runtime_smoke
def test_metadata_lifecycle_outbox_registry_retry_versioning_effective_date_and_tenant_isolation():
    sf = _sf()
    tenant_a, tenant_b = uuid4(), uuid4()
    _seed_tenant(sf, tenant_a)
    _seed_tenant(sf, tenant_b)

    read_ctx_a = _ctx(tenant_a, "reader")
    source_a = PostgresRegistrySourceRepository(sf, read_ctx_a)
    registry = ScenarioRegistry(source_a)
    registry.refresh()
    assert registry.list() == []

    draft, active_v1, author_repo, author, reviewer, publisher = _publish_generic(
        sf,
        tenant_a,
        kind="SCENARIO",
        code=f"scenario-{uuid4().hex[:8]}",
        payload={"label": "V1"},
    )

    # Cache is stale until outbox sync is consumed.
    assert registry.list() == []

    event_repo = PostgresRegistrySyncEventRepository(
        sf, _ctx(tenant_a, "sync-worker")
    )
    failed = RegistrySyncService(event_repo, {"SCENARIO": _FailingRegistry()})
    failed_result = failed.run_once()
    assert failed_result["retried"] == 1
    pending_after_failure = event_repo.pending()
    assert pending_after_failure and pending_after_failure[0]["attempts"] == 1

    sync = RegistrySyncService(event_repo, {"SCENARIO": registry})
    applied = sync.run_once()
    assert applied["applied"] == 1
    assert sync.run_once()["applied"] == 0  # duplicate delivery is idempotent

    resolved_v1 = registry.resolve(code=str(source_a.load_active("SCENARIO")[0]["code"]))
    assert resolved_v1 is not None
    assert resolved_v1["version_id"] == str(active_v1["version_id"])

    # Cross-tenant UUID guessing/listing does not reveal metadata.
    source_b = PostgresRegistrySourceRepository(sf, _ctx(tenant_b, "reader-b"))
    assert source_b.load_active("SCENARIO") == []

    # Optimistic concurrency rejects stale draft writes.
    definition_id = UUID(str(draft["definition_id"]))
    v2 = author_repo.create_version(
        definition_id=definition_id,
        payload={"label": "V2"},
    )
    with pytest.raises(MetadataOptimisticConcurrencyError):
        author.update_draft(
            UUID(str(v2["version_id"])),
            payload={"label": "bad"},
            expected_record_version=99,
        )

    submitted2 = author.submit_review(UUID(str(v2["version_id"])), expected_record_version=1)
    approved2 = reviewer.approve(
        UUID(str(v2["version_id"])),
        expected_record_version=int(submitted2["record_version"]),
    )
    active_v2 = publisher.publish(
        UUID(str(v2["version_id"])),
        expected_record_version=int(approved2["record_version"]),
    )
    # still V1 before sync
    assert registry.resolve(code=str(resolved_v1["code"]))["version_id"] == str(active_v1["version_id"])
    assert RegistrySyncService(event_repo, {"SCENARIO": registry}).run_once()["applied"] == 1
    assert registry.resolve(code=str(resolved_v1["code"]))["version_id"] == str(active_v2["version_id"])

    # Future-effective ACTIVE metadata is excluded from runtime.
    future_definition = author_repo.create_definition(
        kind="SCENARIO",
        code=f"future-{uuid4().hex[:8]}",
        display_name="Future Scenario",
    )
    future_version = author_repo.create_version(
        definition_id=UUID(str(future_definition["definition_id"])),
        payload={"label": "future"},
        effective_from=date.today() + timedelta(days=10),
    )
    future_submitted = author.submit_review(
        UUID(str(future_version["version_id"])), expected_record_version=1
    )
    future_approved = reviewer.approve(
        UUID(str(future_version["version_id"])),
        expected_record_version=int(future_submitted["record_version"]),
    )
    publisher.publish(
        UUID(str(future_version["version_id"])),
        expected_record_version=int(future_approved["record_version"]),
    )
    RegistrySyncService(event_repo, {"SCENARIO": registry}).run_once()
    assert registry.resolve(code=str(future_definition["code"])) is None

    # Unique constraint failure rolls back cleanly.
    with pytest.raises(IntegrityError):
        author_repo.create_definition(
            kind="SCENARIO",
            code=str(resolved_v1["code"]),
            display_name="Duplicate",
        )
    with sf() as session:
        count = session.scalar(
            select(func.count())
            .select_from(MetadataDefinitionEntity)
            .where(
                MetadataDefinitionEntity.tenant_id == str(tenant_a),
                MetadataDefinitionEntity.kind == "SCENARIO",
                MetadataDefinitionEntity.code == str(resolved_v1["code"]),
            )
        )
        assert count == 1


@pytest.mark.runtime_smoke
def test_snapshot_pinning_old_workflow_retains_old_version_new_workflow_gets_new_version():
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)

    draft, active_v1, author_repo, author, reviewer, publisher = _publish_generic(
        sf,
        tenant,
        kind="SCENARIO",
        code=f"pin-{uuid4().hex[:8]}",
        payload={"revision": 1},
    )
    definition_id = UUID(str(draft["definition_id"]))
    snapshot1, snapshot2 = uuid4(), uuid4()
    with sf() as session, session.begin():
        for sid in (snapshot1, snapshot2):
            session.add(
                AnalysisSnapshotEntity(
                    analysis_snapshot_id=str(sid),
                    tenant_id=str(tenant),
                    project_version_id=str(uuid4()),
                    snapshot_version="1.0",
                    analysis_as_of_date=date.today(),
                    provenance_json={"phase": "1c-test"},
                )
            )

    pin_repo = PostgresSnapshotRegistryPinRepository(sf, _ctx(tenant, "pin-worker"))
    pins = SnapshotPinService(pin_repo)
    pins.pin_resolved(
        analysis_snapshot_id=snapshot1,
        pin_type="SCENARIO_CONFIG",
        logical_key=str(definition_id),
        resolved={
            "definition_id": str(definition_id),
            "version_id": str(active_v1["version_id"]),
            "version_no": int(active_v1["version_no"]),
        },
    )

    v2 = author_repo.create_version(definition_id=definition_id, payload={"revision": 2})
    s2 = author.submit_review(UUID(str(v2["version_id"])), expected_record_version=1)
    a2 = reviewer.approve(
        UUID(str(v2["version_id"])), expected_record_version=int(s2["record_version"])
    )
    active_v2 = publisher.publish(
        UUID(str(v2["version_id"])), expected_record_version=int(a2["record_version"])
    )

    frozen1 = pins.frozen_context(snapshot1)
    assert next(iter(frozen1.values()))["version_id"] == str(active_v1["version_id"])

    pins.pin_resolved(
        analysis_snapshot_id=snapshot2,
        pin_type="SCENARIO_CONFIG",
        logical_key=str(definition_id),
        resolved={
            "definition_id": str(definition_id),
            "version_id": str(active_v2["version_id"]),
            "version_no": int(active_v2["version_no"]),
        },
    )
    frozen2 = pins.frozen_context(snapshot2)
    assert next(iter(frozen2.values()))["version_id"] == str(active_v2["version_id"])

    with pytest.raises(MetadataLifecycleError):
        pins.pin_resolved(
            analysis_snapshot_id=snapshot1,
            pin_type="SCENARIO_CONFIG",
            logical_key=str(definition_id),
            resolved={
                "definition_id": str(definition_id),
                "version_id": str(active_v2["version_id"]),
                "version_no": int(active_v2["version_no"]),
            },
        )

    # FK enforcement: unknown snapshot cannot be pinned.
    with pytest.raises(IntegrityError):
        pin_repo.add_pin(
            analysis_snapshot_id=uuid4(),
            pin_type="SCENARIO_CONFIG",
            logical_key="missing",
            object_id=definition_id,
            version_id=UUID(str(active_v2["version_id"])),
            version_no=int(active_v2["version_no"]),
        )


def _publish_special(repo, draft: dict[str, object]) -> dict[str, object]:
    version_id = UUID(str(draft["version_id"]))
    r = repo.transition(version_id, target_status=GovernanceStatus.PENDING_REVIEW.value, expected_record_version=1)
    r = repo.transition(version_id, target_status=GovernanceStatus.APPROVED.value, expected_record_version=int(r["record_version"]))
    return repo.transition(version_id, target_status=GovernanceStatus.ACTIVE.value, expected_record_version=int(r["record_version"]))


@pytest.mark.runtime_smoke
def test_model_registry_provider_types_secret_boundary_disable_and_metadata_only_switch():
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)
    scopes = ("metadata:admin", "metadata:review", "metadata:publish", "metadata:self-review")
    ctx = _ctx(tenant, "model-admin", *scopes)
    admin = PostgresModelAdminRepository(sf, ctx)

    a = admin.create_draft(
        code=f"model-a-{uuid4().hex[:6]}",
        display_name="Model A",
        payload={
            "provider_type": "OPENAI_COMPATIBLE",
            "model_id": "model-a",
            "endpoint_config": {"url": "https://gateway.example/v1"},
            "secret_ref": "secret://models/a",
            "capabilities": ["TEXT", "STRUCTURED_OUTPUT"],
        },
    )
    _publish_special(admin, a)

    b = admin.create_draft(
        code=f"model-b-{uuid4().hex[:6]}",
        display_name="Model B",
        payload={
            "provider_type": "INTERNAL_API",
            "model_id": "model-b",
            "endpoint_config": {"url": "internal://private-model/b"},
            "secret_ref": "secret://models/b",
            "capabilities": ["TEXT"],
        },
    )
    _publish_special(admin, b)

    source = PostgresModelRegistryRepository(sf, _ctx(tenant, "runtime"))
    registry = ModelRegistry(source)
    registry.refresh()
    rows = registry.list()
    assert {row["provider_type"] for row in rows} == {"OPENAI_COMPATIBLE", "INTERNAL_API"}
    assert all("secret_ref" not in row for row in rows)
    assert "secret_ref" not in admin.get_version(UUID(str(a["version_id"])))

    resolved_a = registry.resolve(model_definition_id=UUID(str(a["definition_id"])))
    assert resolved_a is not None and resolved_a["model_id"] == "model-a"

    # Disable Model A: routing moves to Model B after registry refresh; no Agent/Graph code changes.
    source.set_model_enabled(UUID(str(a["definition_id"])), False)
    registry.refresh()
    resolved = registry.resolve(capability="TEXT")
    assert resolved is not None and resolved["model_id"] == "model-b"

    # Disable Model B provider: no eligible TEXT model remains.
    with sf() as session, session.begin():
        session.execute(
            update(ModelProviderEntity)
            .where(
                ModelProviderEntity.provider_id == str(b["provider_id"]),
                ModelProviderEntity.tenant_id == str(tenant),
            )
            .values(enabled=False)
        )
    registry.refresh()
    assert registry.resolve(capability="TEXT") is None


@pytest.mark.runtime_smoke
def test_prompt_rule_template_knowledge_classification_and_jurisdiction_registries():
    sf = _sf()
    tenant = uuid4()
    _seed_tenant(sf, tenant)
    scopes = ("metadata:admin", "metadata:review", "metadata:publish", "metadata:self-review")
    ctx = _ctx(tenant, "config-admin", *scopes)

    # Jurisdiction uses canonical identity + versioned config overlay.
    jurisdiction_admin = PostgresJurisdictionAdminRepository(sf, ctx)
    j = jurisdiction_admin.create_draft(
        code=f"J-{uuid4().hex[:6]}", display_name="Test Jurisdiction", payload={"region": "TEST"}
    )
    _publish_special(jurisdiction_admin, j)
    jreg = ScenarioRegistry(PostgresRegistrySourceRepository(sf, ctx))
    # Use generic projection directly for the JURISDICTION kind.
    from crossborder_compliance.infrastructure.registry import JurisdictionRegistry
    jr = JurisdictionRegistry(PostgresRegistrySourceRepository(sf, ctx))
    jr.refresh()
    assert jr.get(UUID(str(j["definition_id"]))) is not None

    # Classification registry foundation: active version is discoverable without country rules.
    classification_admin = PostgresClassificationAdminRepository(sf, ctx)
    c = classification_admin.create_draft(
        code=f"CLS-{uuid4().hex[:6]}",
        display_name="Generic Classification",
        payload={"applicability": {"industry": "ANY"}},
    )
    _publish_special(classification_admin, c)
    cr = ClassificationRegistry(PostgresConfigRegistrySourceRepository(sf, ctx))
    cr.refresh()
    assert any(row["definition_id"] == str(c["definition_id"]) for row in cr.list())

    config_source = PostgresConfigRegistrySourceRepository(sf, ctx)

    prompt_admin = PostgresGovernedArtifactAdminRepository(sf, ctx, "prompts")
    p = prompt_admin.create_draft(
        code=f"prompt-{uuid4().hex[:6]}",
        display_name="Generic Prompt",
        payload={
            "template_text": "Return a structured response using supplied variables.",
            "capability_requirement": ["STRUCTURED_OUTPUT"],
        },
    )
    _publish_special(prompt_admin, p)
    preg = PromptRegistry(config_source)
    preg.refresh()
    assert any(row["definition_id"] == str(p["definition_id"]) for row in preg.list())

    rule_admin = PostgresGovernedArtifactAdminRepository(sf, ctx, "rules")
    r = rule_admin.create_draft(
        code=f"rule-{uuid4().hex[:6]}",
        display_name="Generic Rule",
        payload={
            "safe_dsl": {"op": "equals", "left": {"fact": "x"}, "right": True},
            "scope": {"scenario": "GENERIC"},
            "priority": 100,
        },
    )
    _publish_special(rule_admin, r)
    rreg = RuleRegistry(config_source)
    rreg.refresh()
    assert any(row["definition_id"] == str(r["definition_id"]) for row in rreg.list())

    template_admin = PostgresGovernedArtifactAdminRepository(sf, ctx, "templates")
    enterprise = template_admin.create_draft(
        code=f"tpl-e-{uuid4().hex[:6]}",
        display_name="Enterprise Template",
        payload={"template_type": "ENTERPRISE_TEMPLATE", "field_schema": {}},
    )
    _publish_special(template_admin, enterprise)
    regulatory = template_admin.create_draft(
        code=f"tpl-r-{uuid4().hex[:6]}",
        display_name="Regulatory Template",
        payload={"template_type": "REGULATORY_TEMPLATE", "field_schema": {}},
    )
    _publish_special(template_admin, regulatory)
    treg = TemplateRegistry(config_source)
    treg.refresh()
    selected = treg.resolve()
    assert selected is not None and selected["template_type"] == "REGULATORY_TEMPLATE"

    knowledge_admin = PostgresGovernedArtifactAdminRepository(sf, ctx, "knowledge-collections")
    k = knowledge_admin.create_draft(
        code=f"knowledge-{uuid4().hex[:6]}",
        display_name="Knowledge Collection",
        payload={"scope": "GLOBAL", "sources": []},
    )
    _publish_special(knowledge_admin, k)
    kreg = KnowledgeRegistry(config_source)
    kreg.refresh()
    assert any(row["definition_id"] == str(k["definition_id"]) for row in kreg.list())

    with sf() as session:
        kinds = set(
            session.scalars(
                select(RegistrySyncEventEntity.object_kind).where(
                    RegistrySyncEventEntity.tenant_id == str(tenant)
                )
            )
        )
    assert {"JURISDICTION", "CLASSIFICATION", "PROMPT", "RULE", "TEMPLATE", "KNOWLEDGE"} <= kinds
