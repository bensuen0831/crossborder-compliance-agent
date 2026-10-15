"""Canonical document metadata/version relations on genuine PostgreSQL."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from test_kb01_taxonomy_postgres import deletion_policy, mutation
from test_phase1f_postgres import fixture as base_knowledge_fixture
from test_phase1f_postgres import ingest, inputs

from crossborder_compliance.application.knowledge_document_management import (
    DOCUMENT_OPERATIONS,
    KnowledgeDocumentManagementService,
)
from crossborder_compliance.application.knowledge_taxonomy import OPERATIONS
from crossborder_compliance.domain.knowledge_management import (
    CreateKnowledgeHold,
    CreateManagedKnowledgeDocument,
    CreateManagedKnowledgeVersion,
    CreateTaxonomy,
    EditManagedKnowledgeVersion,
    KnowledgeDocumentLabel,
    KnowledgeDocumentMetadata,
    KnowledgeManagementPermissionError,
    TaxonomyPayload,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.knowledge_document_management import (
    PostgresKnowledgeDocumentManagement,
)
from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
    KnowledgeDocumentLabelEntity,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
    PostgresKnowledgeTaxonomyRepository,
)

pytestmark = pytest.mark.runtime_smoke


@pytest.fixture
def knowledge():
    # Reuse the original PostgreSQL setup, which has no fixture dependencies.
    return base_knowledge_fixture.__wrapped__()


def context(f, actor="document-author", grants=None):
    scopes = {
        "knowledge:document:read",
        *["knowledge:" + op for op in DOCUMENT_OPERATIONS.values()],
    }
    return RepositoryContext.user(UUID(f["tenant"]), actor, scopes if grants is None else grants)


def service(f, actor="document-author", grants=None):
    ctx = context(f, actor, grants)
    return KnowledgeDocumentManagementService(
        PostgresKnowledgeDocumentManagement(f["sf"], ctx), ctx
    )


def make(f, metadata=None):
    return service(f).mutate(
        "CREATE",
        None,
        CreateManagedKnowledgeDocument(
            source_id=UUID(f["source"]),
            collection_version_id=UUID(f["cv"]),
            language="en",
            metadata=metadata or KnowledgeDocumentMetadata(title="Technical document"),
            idempotency_key=str(uuid4()),
        ),
    )


def published_label(f, kind="REGULATION_CATEGORY"):
    def owner(actor):
        ctx = context(f, actor, {"knowledge:" + op for op in OPERATIONS.values()})
        return PostgresKnowledgeTaxonomyRepository(f["sf"], ctx)

    row = owner("label-author").mutate(
        "CREATE",
        None,
        CreateTaxonomy(
            kind=kind,
            code="LABEL-" + uuid4().hex,
            display_name="Technical classification label",
            payload=TaxonomyPayload(),
            idempotency_key=str(uuid4()),
        ),
    )
    for op, actor in [
        ("SUBMIT_REVIEW", "label-author"),
        ("APPROVE", "label-reviewer"),
        ("PUBLISH", "label-publisher"),
    ]:
        row = owner(actor).mutate(op, UUID(row["version_id"]), mutation(row["record_version"]))
    return KnowledgeDocumentLabel(
        kind=kind, definition_id=UUID(row["definition_id"]), version_id=UUID(row["version_id"])
    )


def test_document_has_canonical_identity_and_initial_draft_metadata(knowledge):
    f = knowledge
    label = published_label(f)
    metadata = KnowledgeDocumentMetadata(
        title="Typed document", description="Bounded metadata", labels=(label,)
    )
    made = make(f, metadata)
    assert made["lifecycle"] == "DRAFT"
    assert made["metadata"]["description"] == "Bounded metadata"
    with f["sf"]() as s:
        assert s.get(k.KnowledgeDocumentEntity, made["document_id"]).source_id == f["source"]
        pin = s.scalar(
            select(KnowledgeDocumentLabelEntity).where(
                KnowledgeDocumentLabelEntity.knowledge_version_id == made["knowledge_version_id"]
            )
        )
        assert pin.metadata_version_id == str(label.version_id)
    assert service(f).list(label_id=label.definition_id)["total"] == 1
    assert service(f).list(language="zh-CN")["total"] == 0


def test_document_creation_is_idempotent_and_cannot_spoof_actor(knowledge):
    f = knowledge
    body = CreateManagedKnowledgeDocument(
        source_id=UUID(f["source"]),
        collection_version_id=UUID(f["cv"]),
        language="en",
        metadata=KnowledgeDocumentMetadata(title="Idempotent"),
        idempotency_key="same-request",
    )
    first = service(f).mutate("CREATE", None, body)
    assert service(f).mutate("CREATE", None, body) == first
    with pytest.raises(KnowledgeManagementConflict, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        service(f).mutate(
            "CREATE",
            None,
            body.model_copy(update={"metadata": KnowledgeDocumentMetadata(title="Different")}),
        )
    with pytest.raises(ValidationError):
        CreateManagedKnowledgeDocument.model_validate(
            {**body.model_dump(mode="json"), "actor_id": "admin"}
        )
    with f["sf"]() as s:
        row = s.get(k.KnowledgeDocumentVersionEntity, first["knowledge_version_id"])
        assert row.provenance_json["created_by"] == "document-author"


def test_draft_document_edit_cas_and_classification_change(knowledge):
    f = knowledge
    made = make(f)
    label = published_label(f)
    request = EditManagedKnowledgeVersion(
        **mutation().model_dump(),
        metadata=KnowledgeDocumentMetadata(title="Reclassified", labels=(label,)),
    )
    result = service(f).mutate("EDIT_DRAFT", UUID(made["knowledge_version_id"]), request)
    assert result["metadata"]["labels"][0]["version_id"] == str(label.version_id)
    assert result["record_version"] == 2
    with pytest.raises(KnowledgeManagementConflict, match="KNOWLEDGE_VERSION_CONFLICT"):
        service(f).mutate(
            "EDIT_DRAFT",
            UUID(made["knowledge_version_id"]),
            request.model_copy(update={"idempotency_key": str(uuid4())}),
        )


def test_new_document_version_preserves_original_metadata_and_pins(knowledge):
    f = knowledge
    old_label, new_label = published_label(f), published_label(f)
    original = make(f, KnowledgeDocumentMetadata(title="Original", labels=(old_label,)))
    root = service(f).detail(UUID(original["document_id"]))
    new = service(f).mutate(
        "NEW_VERSION",
        UUID(original["document_id"]),
        CreateManagedKnowledgeVersion(
            **mutation(root["record_version"]).model_dump(),
            collection_version_id=UUID(f["cv"]),
            language="zh-CN",
            metadata=KnowledgeDocumentMetadata(title="Successor", labels=(new_label,)),
        ),
    )
    detail = service(f).detail(UUID(original["document_id"]))
    assert new["version"] == 2
    assert detail["versions"][1] == {
        k: v for k, v in original.items() if k not in {"receipt_id", "operation"}
    }
    assert service(f).list(label_id=old_label.definition_id)["total"] == 0
    assert service(f).list(label_id=new_label.definition_id)["total"] == 1


def test_wrong_kind_or_inactive_metadata_cannot_classify_document(knowledge):
    f = knowledge
    active = published_label(f)
    wrong = active.model_copy(update={"kind": "RESEARCH_TOPIC"})
    with pytest.raises(
        KnowledgeManagementConflict, match="DOCUMENT_CLASSIFICATION_NOT_ACTIVE_OR_MISMATCHED"
    ):
        make(f, KnowledgeDocumentMetadata(title="Rejected", labels=(wrong,)))
    assert service(f).list()["total"] == 0


def test_document_delete_needs_governed_policy_and_keeps_tombstone_audit(knowledge):
    f = knowledge
    made = make(f)
    root = service(f).detail(UUID(made["document_id"]))
    deletion_policy((f["sf"], UUID(f["tenant"]), None, None))
    command = mutation(root["record_version"])
    removed = service(f).mutate("DELETE_DRAFT", UUID(made["document_id"]), command)
    assert removed["deleted"]
    assert service(f).mutate("DELETE_DRAFT", UUID(made["document_id"]), command) == removed
    with pytest.raises(LookupError):
        service(f).detail(UUID(made["document_id"]))
    ctx = context(f, grants={"knowledge:audit:read"})
    audit = PostgresKnowledgeTaxonomyRepository(f["sf"], ctx).audit_history(
        UUID(made["document_id"])
    )
    assert {row["operation"] for row in audit["items"]} == {
        "DOCUMENT_CREATE",
        "DOCUMENT_DELETE_DRAFT",
    }


def test_ingested_content_and_hold_protect_physical_document_delete(knowledge):
    f = knowledge
    made = make(f)
    root = service(f).detail(UUID(made["document_id"]))
    deletion_policy((f["sf"], UUID(f["tenant"]), None, None))
    ctx = context(f, grants={"knowledge:hold:create"})
    PostgresKnowledgeTaxonomyRepository(f["sf"], ctx).create_hold(
        CreateKnowledgeHold(
            resource_type="KNOWLEDGE_DOCUMENT",
            resource_id=UUID(made["document_id"]),
            expected_record_version=root["record_version"],
            reason="Retain source",
            idempotency_key=str(uuid4()),
        )
    )
    assert (
        service(f).impact(UUID(made["document_id"]))["references"]["knowledge_management_holds"]
        == 1
    )
    with pytest.raises(KnowledgeManagementConflict, match="KNOWLEDGE_DOCUMENT_DELETE_PROTECTED"):
        service(f).mutate(
            "DELETE_DRAFT", UUID(made["document_id"]), mutation(root["record_version"])
        )
    ingest(f, made, inputs(f))
    assert service(f).impact(UUID(made["document_id"]))["protected_version_history"]


def test_ingested_or_published_labels_and_metadata_are_immutable(knowledge):
    f = knowledge
    label = published_label(f)
    made = make(f, KnowledgeDocumentMetadata(title="Immutable", labels=(label,)))
    ingest(f, made, inputs(f))
    with f["sf"]() as s:
        expected = s.get(
            k.KnowledgeDocumentVersionEntity, made["knowledge_version_id"]
        ).record_version
    with pytest.raises(KnowledgeManagementConflict, match="KNOWLEDGE_VERSION_IMMUTABLE"):
        service(f).mutate(
            "EDIT_DRAFT",
            UUID(made["knowledge_version_id"]),
            EditManagedKnowledgeVersion(
                **mutation(expected).model_dump(),
                metadata=KnowledgeDocumentMetadata(title="Rewrite"),
            ),
        )
    with pytest.raises(DBAPIError, match="KB01_PUBLISHED_LABEL_IMMUTABLE"):
        with f["sf"]() as s, s.begin():
            row = s.scalar(
                select(KnowledgeDocumentLabelEntity).where(
                    KnowledgeDocumentLabelEntity.knowledge_version_id
                    == made["knowledge_version_id"]
                )
            )
            s.delete(row)


def test_ingested_label_cannot_be_retargeted_to_a_new_draft(knowledge):
    f = knowledge
    label = published_label(f)
    original = make(f, KnowledgeDocumentMetadata(title="Original pinned source", labels=(label,)))
    replacement = make(f)
    ingest(f, original, inputs(f))
    with pytest.raises(DBAPIError, match="KB01_PUBLISHED_LABEL_IMMUTABLE"):
        with f["sf"]() as s, s.begin():
            row = s.scalar(
                select(KnowledgeDocumentLabelEntity).where(
                    KnowledgeDocumentLabelEntity.knowledge_version_id
                    == original["knowledge_version_id"]
                )
            )
            row.knowledge_version_id = replacement["knowledge_version_id"]


def test_document_cross_tenant_and_coarse_grant_fail_closed(knowledge):
    f = knowledge
    made = make(f)
    outsider = RepositoryContext.user(uuid4(), "outsider", {"knowledge:document:read"})
    repo = PostgresKnowledgeDocumentManagement(f["sf"], outsider)
    assert repo.list()["total"] == 0
    with pytest.raises(LookupError):
        repo.detail(UUID(made["document_id"]))
    with pytest.raises(KnowledgeManagementPermissionError):
        service(f, grants={"knowledge:admin"}).detail(UUID(made["document_id"]))


def test_document_official_source_metadata_rejects_credentials():
    with pytest.raises(ValidationError):
        KnowledgeDocumentMetadata(
            title="Unsafe", official_source_url="https://source.example/law?api_key=secret"
        )


def test_document_management_reuses_full_review_publication_and_hold_guard(knowledge):
    f = knowledge
    made = make(
        f, KnowledgeDocumentMetadata(title="Reviewed document", labels=(published_label(f),))
    )
    ingest(f, made, inputs(f))
    version_id = UUID(made["knowledge_version_id"])
    for operation, actor in [
        ("VALIDATE", "document-author"),
        ("SUBMIT_REVIEW", "document-author"),
        ("APPROVE", "independent-reviewer"),
        ("PUBLISH", "publisher"),
    ]:
        current = f["repo"].get_version(str(version_id))
        result = service(f, actor).mutate(
            operation, version_id, mutation(current["record_version"])
        )
    assert result["lifecycle"] == "ACTIVE"
    root = service(f).detail(UUID(made["document_id"]))
    manager = PostgresKnowledgeTaxonomyRepository(
        f["sf"],
        context(f, "retention-officer", {"knowledge:hold:create", "knowledge:hold:release"}),
    )
    hold = manager.create_hold(
        CreateKnowledgeHold(
            resource_type="KNOWLEDGE_DOCUMENT",
            resource_id=UUID(made["document_id"]),
            expected_record_version=root["record_version"],
            reason="Retain published source",
            idempotency_key=str(uuid4()),
        )
    )
    expired = service(f).mutate("EXPIRE", version_id, mutation(result["record_version"]))
    # The original channel uses the same guard; coarse administration cannot bypass it.
    with pytest.raises(ValueError, match="KNOWLEDGE_DOCUMENT_HAS_ACTIVE_HOLD"):
        f["repo"].governance(str(version_id), "archive", expired["record_version"])
    manager.release_hold(UUID(hold["hold_id"]), mutation())
    archived = service(f).mutate("ARCHIVE", version_id, mutation(expired["record_version"]))
    assert archived["lifecycle"] == "ARCHIVED"
    assert archived["metadata"]["labels"] == made["metadata"]["labels"]


@pytest.mark.parametrize("reviewer", ["document-author", "metadata-editor"])
def test_content_contributor_cannot_self_review_through_a_different_submitter(knowledge, reviewer):
    f = knowledge
    made = make(f)
    identity = UUID(made["knowledge_version_id"])
    if reviewer == "metadata-editor":
        service(f, reviewer).mutate(
            "EDIT_DRAFT",
            identity,
            EditManagedKnowledgeVersion(
                **mutation(made["record_version"]).model_dump(),
                metadata=KnowledgeDocumentMetadata(title="Contributed draft metadata"),
            ),
        )
    ingest(f, made, inputs(f))
    for operation in ("VALIDATE", "SUBMIT_REVIEW"):
        current = f["repo"].get_version(str(identity))
        service(f, "proxy-submitter").mutate(
            operation, identity, mutation(current["record_version"])
        )
    pending = f["repo"].get_version(str(identity))
    with pytest.raises(ValueError, match="independent human reviewer required"):
        service(f, reviewer).mutate("APPROVE", identity, mutation(pending["record_version"]))


def test_document_http_uses_trusted_context_and_public_typed_projection(knowledge):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.routes.knowledge_document_management import router

    f = knowledge
    body = CreateManagedKnowledgeDocument(
        source_id=UUID(f["source"]),
        collection_version_id=UUID(f["cv"]),
        language="en",
        metadata=KnowledgeDocumentMetadata(title="HTTP document"),
        idempotency_key=str(uuid4()),
    ).model_dump(mode="json")
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/admin/knowledge-management/documents", json=body).status_code
            == 401
        )
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)

    @app.middleware("http")
    async def host(request, call_next):
        request.state.repository_context = context(f)
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post("/api/v1/admin/knowledge-management/documents", json=body)
        assert response.status_code == 201, response.text
        document_id = response.json()["document_id"]
        detail = client.get("/api/v1/admin/knowledge-management/documents/" + document_id)
        assert detail.status_code == 200
        assert detail.json()["versions"][0]["metadata"]["title"] == "HTTP document"
        assert "provenance_json" not in response.json()
        assert (
            client.post(
                "/api/v1/admin/knowledge-management/documents",
                json={**body, "tenant_id": str(uuid4())},
            ).status_code
            == 422
        )
