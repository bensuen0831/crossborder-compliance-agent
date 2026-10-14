"""Real PostgreSQL canonical taxonomy operations; test host context is not production auth."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from crossborder_compliance.application.knowledge_taxonomy import (
    OPERATIONS,
    KnowledgeTaxonomyService,
)
from crossborder_compliance.application.metadata_services import MetadataLifecycleService
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.knowledge_management import (
    CreateKnowledgeHold,
    CreateTaxonomy,
    EditTaxonomy,
    KnowledgeManagementPermissionError,
    KnowledgeManagementPolicy,
    MergeTaxonomy,
    MutateTaxonomy,
    TaxonomyPayload,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
    AdminOperationReceiptEntity,
    KnowledgeManagementHoldEntity,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementCapabilityError,
    KnowledgeManagementConflict,
    PostgresKnowledgeTaxonomyRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.interfaces.api.routes.knowledge_management import router

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def env():
    url = get_settings().database_url
    assert url.startswith("postgresql")
    sf = build_session_factory(url)[1]
    tenant = uuid4()
    with sf() as s, s.begin():
        s.add(b.TenantEntity(tenant_id=str(tenant), name="KB01 technical test tenant"))
    scopes = {"knowledge:taxonomy:read", *["knowledge:" + v for v in OPERATIONS.values()]}

    def context(actor="author", grants=None):
        return RepositoryContext.user(tenant, actor, scopes if grants is None else grants)

    def service(actor="author", grants=None):
        c = context(actor, grants)
        return KnowledgeTaxonomyService(PostgresKnowledgeTaxonomyRepository(sf, c), c)

    return sf, tenant, context, service


def create(service, kind="REGULATION_CATEGORY", payload=None):
    if payload is None:
        payload = (
            TaxonomyPayload(jurisdiction_type="COUNTRY")
            if kind == "JURISDICTION_CONFIG"
            else TaxonomyPayload()
        )
    return service.mutate(
        "CREATE",
        None,
        CreateTaxonomy(
            kind=kind,
            code="KB-" + str(uuid4()),
            display_name="Technical taxonomy label",
            payload=payload,
            idempotency_key=str(uuid4()),
        ),
    )


def mutation(version=1):
    return MutateTaxonomy(
        expected_record_version=version,
        idempotency_key=str(uuid4()),
        reason="Technical governance test",
    )


def publish(env, created):
    _, _, _, service = env
    vid = UUID(created["version_id"])
    submit = service().mutate("SUBMIT_REVIEW", vid, mutation(created["record_version"]))
    approve = service("reviewer").mutate("APPROVE", vid, mutation(submit["record_version"]))
    return service("publisher").mutate("PUBLISH", vid, mutation(approve["record_version"]))


def deletion_policy(env):
    sf, tenant, _, _ = env

    def owner(actor, scopes):
        ctx = RepositoryContext.user(tenant, actor, scopes)
        return MetadataLifecycleService(PostgresAdminMetadataRepository(sf, ctx), ctx)

    author = owner("policy-author", {"metadata:admin"})
    draft = author.create_draft(
        kind="KNOWLEDGE_MANAGEMENT_POLICY",
        code="DELETE-POLICY",
        display_name="Technical management policy",
        payload=KnowledgeManagementPolicy(
            draft_delete_allowed=True, draft_retention_seconds=0
        ).model_dump(mode="json"),
    )
    ident = UUID(draft["version_id"])
    submitted = author.submit_review(ident, expected_record_version=draft["record_version"])
    reviewer = owner("policy-reviewer", {"metadata:review"})
    approved = reviewer.approve(ident, expected_record_version=submitted["record_version"])
    return owner("policy-publisher", {"metadata:publish"}).publish(
        ident, expected_record_version=approved["record_version"]
    )


@pytest.mark.parametrize(
    "kind",
    [
        "JURISDICTION_CONFIG",
        "REGULATION_CATEGORY",
        "RESEARCH_TOPIC",
        "LANGUAGE",
        "ISSUING_AUTHORITY",
        "KNOWLEDGE_SOURCE_TYPE",
        "LEGAL_EFFECT",
    ],
)
def test_creation_uses_existing_authority_and_exact_scoped_rows(env, kind):
    sf, tenant, _, service = env
    result = create(service(), kind)
    with sf() as s:
        row = s.get(m.MetadataDefinitionEntity, result["definition_id"])
        assert row.tenant_id == str(tenant) and row.kind == kind
        if kind == "JURISDICTION_CONFIG":
            assert s.get(b.JurisdictionEntity, result["canonical_object_id"]).status == "DRAFT"
        assert s.get(m.MetadataVersionEntity, result["version_id"]).lifecycle_status == "DRAFT"


def test_no_client_actor_tenant_or_arbitrary_legal_kind(env):
    with pytest.raises(ValidationError):
        CreateTaxonomy(
            kind="REGULATION_CATEGORY",
            code="X",
            display_name="X",
            idempotency_key="X",
            actor_id="forged",
        )
    with pytest.raises(ValidationError):
        CreateTaxonomy(kind="OBLIGATION_POLICY", code="X", display_name="X", idempotency_key="X")
    _, _, _, service = env
    with pytest.raises(KnowledgeManagementPermissionError):
        create(service(grants={"knowledge:admin"}))


def test_create_idempotency_and_different_payload_conflict(env):
    sf, _, _, service = env
    request = CreateTaxonomy(
        kind="REGULATION_CATEGORY", code="IDEMP", display_name="First", idempotency_key="one"
    )
    first = service().mutate("CREATE", None, request)
    assert service().mutate("CREATE", None, request) == first
    with pytest.raises(KnowledgeManagementConflict, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        service().mutate("CREATE", None, request.model_copy(update={"display_name": "Other"}))
    with sf() as s:
        assert (
            len(
                s.scalars(
                    select(AdminOperationReceiptEntity).where(
                        AdminOperationReceiptEntity.resource_id == first["definition_id"]
                    )
                ).all()
            )
            == 1
        )


def test_current_scope_revocation_blocks_cached_idempotent_result(env):
    _, _, _, service = env
    request = CreateTaxonomy(
        kind="LANGUAGE", code="ROLE", display_name="Role", idempotency_key="role"
    )
    service().mutate("CREATE", None, request)
    with pytest.raises(KnowledgeManagementPermissionError):
        service(grants=set()).mutate("CREATE", None, request)


def test_cross_tenant_list_detail_and_impact_fail_closed(env):
    sf, _, _, service = env
    created = create(service())
    other = RepositoryContext.user(uuid4(), "other", {"knowledge:taxonomy:read"})
    outsider = PostgresKnowledgeTaxonomyRepository(sf, other)
    assert outsider.list()["total"] == 0
    with pytest.raises(LookupError):
        outsider.detail(UUID(created["definition_id"]))
    with pytest.raises(LookupError):
        outsider.impact(UUID(created["definition_id"]))


def test_draft_edit_cas_and_parent_cycle_are_rejected(env):
    _, _, _, service = env
    row = create(service())
    edited = service().mutate(
        "EDIT_DRAFT",
        UUID(row["version_id"]),
        EditTaxonomy(**mutation().model_dump(), payload=TaxonomyPayload(description="Updated")),
    )
    assert edited["record_version"] == 2
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_VERSION_CONFLICT"):
        service().mutate(
            "EDIT_DRAFT",
            UUID(row["version_id"]),
            EditTaxonomy(**mutation().model_dump(), payload=TaxonomyPayload(description="Stale")),
        )
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_PARENT_CYCLE"):
        service().mutate(
            "EDIT_DRAFT",
            UUID(row["version_id"]),
            EditTaxonomy(
                **mutation(2).model_dump(),
                payload=TaxonomyPayload(parent_definition_id=UUID(row["definition_id"])),
            ),
        )


def test_independent_review_cannot_use_self_review_override(env):
    _, _, context, service = env
    row = create(service())
    submitted = service().mutate("SUBMIT_REVIEW", UUID(row["version_id"]), mutation())
    grants = set(context().permission.scopes) | {"metadata:self-review"}
    with pytest.raises(KnowledgeManagementConflict, match="INDEPENDENT_HUMAN_REVIEW_REQUIRED"):
        service(grants=grants).mutate(
            "APPROVE", UUID(row["version_id"]), mutation(submitted["record_version"])
        )
    assert publish_after_submission(env, row, submitted)["lifecycle_status"] == "ACTIVE"


def publish_after_submission(env, row, submitted):
    _, _, _, service = env
    approved = service("reviewer").mutate(
        "APPROVE", UUID(row["version_id"]), mutation(submitted["record_version"])
    )
    return service("publisher").mutate(
        "PUBLISH", UUID(row["version_id"]), mutation(approved["record_version"])
    )


def test_two_reviewers_have_one_canonical_winner(env):
    _, _, _, service = env
    row = create(service())
    submitted = service().mutate("SUBMIT_REVIEW", UUID(row["version_id"]), mutation())

    def vote(actor):
        try:
            service(actor).mutate(
                "APPROVE", UUID(row["version_id"]), mutation(submitted["record_version"])
            )
            return "accepted"
        except KnowledgeManagementConflict:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(vote, ["reviewer-one", "reviewer-two"])) == ["accepted", "stale"]


def test_new_version_and_locale_preserve_old_payload_identity(env):
    sf, _, _, service = env
    row = create(
        service(),
        payload=TaxonomyPayload(
            localized_display={
                "localized_display_names": {
                    "zh-CN": "技术分类",
                    "zh-HK": "技術分類",
                    "en-US": "Technical category",
                }
            }
        ),
    )
    publish(env, row)
    with sf() as s:
        before = json.dumps(
            s.get(m.MetadataVersionEntity, row["version_id"]).payload_json, sort_keys=True
        )
    detail = service().detail(UUID(row["definition_id"]))
    newer = service().mutate(
        "NEW_VERSION",
        UUID(row["definition_id"]),
        EditTaxonomy(
            **mutation(detail["record_version"]).model_dump(),
            payload=TaxonomyPayload(description="Future"),
        ),
    )
    publish(env, newer)
    with sf() as s:
        old = s.get(m.MetadataVersionEntity, row["version_id"])
        assert (
            old.version_id == row["version_id"]
            and json.dumps(old.payload_json, sort_keys=True) == before
        )
        assert old.lifecycle_status == "SUPERSEDED"


def test_versioned_deactivate_reactivate_does_not_rewrite_jurisdiction_identity(env):
    sf, _, _, service = env
    row = create(service(), "JURISDICTION_CONFIG")
    publish(env, row)
    detail = service().detail(UUID(row["definition_id"]))
    proposal = service().mutate(
        "DEACTIVATE", UUID(row["definition_id"]), mutation(detail["record_version"])
    )
    assert service().detail(UUID(row["definition_id"]))["enabled"]
    publish(env, proposal)
    assert service().list(enabled=False)["total"] == 1
    with sf() as s:
        assert s.get(b.JurisdictionEntity, row["canonical_object_id"]).status == "ACTIVE"
    detail = service().detail(UUID(row["definition_id"]))
    proposal = service().mutate(
        "REACTIVATE", UUID(row["definition_id"]), mutation(detail["record_version"])
    )
    publish(env, proposal)
    assert service().list(enabled=True)["total"] == 1


def test_draft_delete_requires_real_governed_retention_policy_and_preserves_audit(env):
    sf, _, _, service = env
    row = create(service())
    detail = service().detail(UUID(row["definition_id"]))
    request = mutation(detail["record_version"])
    with pytest.raises(KnowledgeManagementCapabilityError):
        service().mutate("DELETE_DRAFT", UUID(row["definition_id"]), request)
    deletion_policy(env)
    result = service().mutate("DELETE_DRAFT", UUID(row["definition_id"]), request)
    assert result["deleted"]
    assert service().mutate("DELETE_DRAFT", UUID(row["definition_id"]), request) == result
    with sf() as s:
        assert s.get(m.MetadataDefinitionEntity, row["definition_id"]) is None
        receipt = s.get(AdminOperationReceiptEntity, result["receipt_id"])
        assert s.get(m.AdminChangeSetEntity, receipt.change_set_id).actor_id == "author"


def test_published_or_referenced_draft_cannot_be_deleted(env):
    _, _, _, service = env
    deletion_policy(env)
    parent = create(service())
    create(service(), payload=TaxonomyPayload(parent_definition_id=UUID(parent["definition_id"])))
    detail = service().detail(UUID(parent["definition_id"]))
    assert service().impact(UUID(parent["definition_id"]))["references"]
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_DELETE_PROTECTED"):
        service().mutate(
            "DELETE_DRAFT", UUID(parent["definition_id"]), mutation(detail["record_version"])
        )
    published = create(service())
    publish(env, published)
    detail = service().detail(UUID(published["definition_id"]))
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_DELETE_PROTECTED"):
        service().mutate(
            "DELETE_DRAFT", UUID(published["definition_id"]), mutation(detail["record_version"])
        )


def test_merge_is_governed_alias_without_historical_rebinding(env):
    sf, tenant, _, service = env
    source, target = create(service()), create(service())
    a, bview = (
        service().detail(UUID(source["definition_id"])),
        service().detail(UUID(target["definition_id"])),
    )
    proposal = service().mutate(
        "MERGE_PROPOSAL",
        UUID(source["definition_id"]),
        MergeTaxonomy(
            **mutation(a["record_version"]).model_dump(),
            target_definition_id=UUID(target["definition_id"]),
            expected_target_record_version=bview["record_version"],
        ),
    )
    publish(env, proposal)
    with sf() as s:
        binding = s.scalar(
            select(m.MetadataBindingEntity).where(
                m.MetadataBindingEntity.tenant_id == str(tenant),
                m.MetadataBindingEntity.binding_type == "KB_TAXONOMY_ALIAS",
            )
        )
        assert binding.source_definition_id == source["definition_id"]
        assert binding.target_definition_id == target["definition_id"]
        assert binding.scope_json["historical_rebinding"] is False
        assert s.get(m.MetadataDefinitionEntity, source["definition_id"]) is not None


def test_receipt_cannot_be_mutated_in_postgres(env):
    sf, _, _, service = env
    row = create(service())
    with pytest.raises(DBAPIError, match="KB01_ADMIN_AUDIT_IMMUTABLE"):
        with sf() as s, s.begin():
            receipt = s.get(AdminOperationReceiptEntity, row["receipt_id"])
            receipt.reason = "tampered"
            s.flush()


def test_http_contract_denies_untrusted_context_and_spoofed_actor(env):
    sf, _, context, _ = env
    app = FastAPI()
    app.include_router(router)
    app.state.knowledge_session_factory = sf
    client = TestClient(app)
    assert client.get("/api/v1/admin/knowledge-management/taxonomy").status_code == 401
    app = FastAPI()
    app.include_router(router)
    app.state.knowledge_session_factory = sf

    @app.middleware("http")
    async def trusted_test_host(request, call_next):
        request.state.repository_context = context()
        return await call_next(request)

    client = TestClient(app)
    body = CreateTaxonomy(
        kind="REGULATION_CATEGORY", code="HTTP", display_name="HTTP", idempotency_key="http"
    ).model_dump(mode="json")
    response = client.post("/api/v1/admin/knowledge-management/taxonomy", json=body)
    assert response.status_code == 201, response.text
    body["actor_id"] = "forged"
    assert client.post("/api/v1/admin/knowledge-management/taxonomy", json=body).status_code == 422


def test_partial_edit_preserves_aliases_and_advances_root_cas(env):
    _, _, _, service = env
    row = create(service(), payload=TaxonomyPayload(aliases=("Original alias",)))
    before = service().detail(UUID(row["definition_id"]))
    edited = service().mutate(
        "EDIT_DRAFT",
        UUID(row["version_id"]),
        EditTaxonomy(
            **mutation().model_dump(), payload=TaxonomyPayload(description="Only description")
        ),
    )
    assert edited["payload"]["aliases"] == ["Original alias"]
    after = service().detail(UUID(row["definition_id"]))
    assert after["record_version"] == before["record_version"] + 1
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_DEFINITION_CONFLICT"):
        service().mutate(
            "NEW_VERSION",
            UUID(row["definition_id"]),
            EditTaxonomy(
                **mutation(before["record_version"]).model_dump(),
                payload=TaxonomyPayload(description="Stale"),
            ),
        )


def test_generic_metadata_channel_cannot_bypass_taxonomy_references(env):
    sf, _, context, service = env
    row = create(service())
    repository = PostgresAdminMetadataRepository(sf, context(grants={"metadata:write"}))
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_PARENT_CYCLE"):
        repository.update_draft(
            UUID(row["version_id"]),
            payload={**row["payload"], "parent_definition_id": row["definition_id"]},
            expected_record_version=1,
        )
    foreign = uuid4()
    with pytest.raises(LookupError):
        repository.update_draft(
            UUID(row["version_id"]),
            payload={**row["payload"], "parent_definition_id": str(foreign)},
            expected_record_version=1,
        )


def test_deactivation_hides_new_discovery_without_rewriting_identity(env):
    from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
        PostgresRegistrySourceRepository,
    )

    sf, _, context, service = env
    row = create(service(), "JURISDICTION_CONFIG")
    publish(env, row)
    original = service().detail(UUID(row["definition_id"]))
    deactivated = service().mutate(
        "DEACTIVATE", UUID(row["definition_id"]), mutation(original["record_version"])
    )
    publish(env, deactivated)
    assert not any(
        x["definition_id"] == row["canonical_object_id"]
        for x in PostgresRegistrySourceRepository(sf, context()).load_jurisdictions()
    )
    with sf() as s:
        assert s.get(b.JurisdictionEntity, row["canonical_object_id"]).status == "ACTIVE"
        assert s.get(m.MetadataVersionEntity, row["version_id"]).payload_json == row["payload"]


def test_hold_is_audited_releasable_once_and_protects_history(env):
    sf, _, context, service = env
    row = create(service())
    grants = {
        "knowledge:hold:create",
        "knowledge:hold:read",
        "knowledge:hold:release",
        "knowledge:audit:read",
    }
    manager = service("retention-officer", grants=grants)
    command = CreateKnowledgeHold(
        resource_type="TAXONOMY",
        resource_id=UUID(row["definition_id"]),
        expected_record_version=service().detail(UUID(row["definition_id"]))["record_version"],
        reason="Preserve governance evidence",
        idempotency_key=str(uuid4()),
    )
    hold = manager.create_hold(command)
    assert manager.create_hold(command) == hold
    assert hold["created_by"] == "retention-officer"
    assert (
        service().impact(UUID(row["definition_id"]))["references"]["knowledge_management_holds"]
        == 1
    )
    released = manager.release_hold(UUID(hold["hold_id"]), mutation())
    assert released["released_by"] == "retention-officer"
    assert len(manager.list_holds("TAXONOMY", UUID(row["definition_id"]))) == 1
    history = manager.audit_history(UUID(row["definition_id"]))
    assert {x["operation"] for x in history["items"]} >= {"HOLD_CREATE", "HOLD_RELEASE"}
    with pytest.raises(KnowledgeManagementConflict, match="KNOWLEDGE_HOLD_VERSION_CONFLICT"):
        manager.release_hold(UUID(hold["hold_id"]), mutation(2))
    with pytest.raises(DBAPIError, match="KB01_HOLD_HISTORY_IMMUTABLE"):
        with sf() as s, s.begin():
            s.get(KnowledgeManagementHoldEntity, hold["hold_id"]).reason = "Rewrite history"
    with pytest.raises(KnowledgeManagementPermissionError):
        service().create_hold(command)


def test_hold_cross_tenant_and_stale_resource_are_rejected(env):
    sf, _, _, service = env
    row = create(service())
    manager = service(grants={"knowledge:hold:create"})
    with pytest.raises(KnowledgeManagementConflict):
        manager.create_hold(
            CreateKnowledgeHold(
                resource_type="TAXONOMY",
                resource_id=UUID(row["definition_id"]),
                expected_record_version=1,
                reason="Stale",
                idempotency_key=str(uuid4()),
            )
        )
    other = RepositoryContext.user(uuid4(), "outsider", {"knowledge:hold:create"})
    with pytest.raises(LookupError):
        PostgresKnowledgeTaxonomyRepository(sf, other).create_hold(
            CreateKnowledgeHold(
                resource_type="TAXONOMY",
                resource_id=UUID(row["definition_id"]),
                expected_record_version=2,
                reason="Foreign",
                idempotency_key=str(uuid4()),
            )
        )


def test_alias_and_localized_names_search_use_tenant_scoped_sql(env):
    from crossborder_compliance.domain.localized_metadata import LocalizedDisplayMetadata

    _, _, _, service = env
    row = create(
        service(),
        payload=TaxonomyPayload(
            aliases=("Unique alias?",),
            localized_display=LocalizedDisplayMetadata(
                localized_display_names={
                    "zh-CN": "独立检索名称",
                    "zh-HK": "獨立檢索名稱",
                    "en-US": "Independent search label",
                }
            ),
        ),
    )
    for phrase in ["Unique alias?", "独立检索", "獨立檢索", "Independent search"]:
        page = service().list(query=phrase)
        assert page["total"] == 1 and page["items"][0]["definition_id"] == row["definition_id"]
    assert service().list(query="Unique alias?", enabled=True)["total"] == 1
    assert service().list(query="Unique alias?", enabled=False)["total"] == 0


def test_alias_merge_cycle_and_competing_target_are_rejected(env):
    _, _, _, service = env
    source, target, competing = (create(service()) for _ in range(3))
    proposed = service().mutate(
        "MERGE_PROPOSAL",
        UUID(source["definition_id"]),
        MergeTaxonomy(
            **mutation(
                service().detail(UUID(source["definition_id"]))["record_version"]
            ).model_dump(),
            target_definition_id=UUID(target["definition_id"]),
            expected_target_record_version=service().detail(UUID(target["definition_id"]))[
                "record_version"
            ],
        ),
    )
    publish(env, proposed)
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_ALIAS_CYCLE"):
        service().mutate(
            "MERGE_PROPOSAL",
            UUID(target["definition_id"]),
            MergeTaxonomy(
                **mutation(
                    service().detail(UUID(target["definition_id"]))["record_version"]
                ).model_dump(),
                target_definition_id=UUID(source["definition_id"]),
                expected_target_record_version=service().detail(UUID(source["definition_id"]))[
                    "record_version"
                ],
            ),
        )
    with pytest.raises(KnowledgeManagementConflict, match="TAXONOMY_ALIAS_AMBIGUOUS"):
        service().mutate(
            "MERGE_PROPOSAL",
            UUID(source["definition_id"]),
            MergeTaxonomy(
                **mutation(
                    service().detail(UUID(source["definition_id"]))["record_version"]
                ).model_dump(),
                target_definition_id=UUID(competing["definition_id"]),
                expected_target_record_version=service().detail(UUID(competing["definition_id"]))[
                    "record_version"
                ],
            ),
        )
