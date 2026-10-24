"""Real versioned clauses and independent review in the existing translation store."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_phase1f_postgres import fixture as fixture
from test_phase1f_postgres import ingest, inputs

from crossborder_compliance.domain.knowledge_translation_alignment import (
    CreateTranslationAlignment,
    ReviewTranslationAlignment,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)
from crossborder_compliance.infrastructure.persistence.knowledge_translation_alignment import (
    PostgresKnowledgeTranslationAlignment,
)

pytestmark = pytest.mark.runtime_smoke


def owner(f, actor="translator", scopes=None):
    return PostgresKnowledgeTranslationAlignment(
        f["sf"],
        RepositoryContext.user(
            UUID(f["tenant"]),
            actor,
            {
                "knowledge:translation:read",
                "knowledge:translation:write",
                "knowledge:translation:approve",
            }
            if scopes is None
            else scopes,
        ),
    )


def pair(f):
    versions = []
    for lang, text in [("en", "Synthetic article one."), ("ar", "المادة الأولى، نص تجريبي.")]:
        document = f["repo"].create_document(
            {
                "source_id": f["source"],
                "display_name": "Synthetic translation " + lang,
            }
        )
        version = f["repo"].create_version(
            document["document_id"],
            {
                "collection_version_id": f["cv"],
                "language": lang,
                "provenance": {"synthetic_engineering_only": True},
            },
        )
        ingest(
            f,
            version,
            inputs(
                f,
                nodes=[
                    {
                        "node_type": "ARTICLE",
                        "canonical_locator": "article/1",
                        "original_text": text,
                        "official_number": "1",
                    }
                ],
            ),
        )
        versions.append(f["repo"].get_version(version["knowledge_version_id"]))
    with f["sf"]() as s:
        nodes = [
            s.scalar(
                select(k.KnowledgeStructureNodeEntity).where(
                    k.KnowledgeStructureNodeEntity.knowledge_version_id
                    == version["knowledge_version_id"],
                )
            ).structure_node_id
            for version in versions
        ]
    request = CreateTranslationAlignment(
        source_version_id=versions[0]["knowledge_version_id"],
        target_version_id=versions[1]["knowledge_version_id"],
        expected_source_record_version=versions[0]["record_version"],
        expected_target_record_version=versions[1]["record_version"],
        pairs=({"source_node_id": nodes[0], "target_node_id": nodes[1]},),
        reason="Synthetic engineering alignment; not legal acceptance",
    )
    return request


def review(version=1, action="APPROVE"):
    return ReviewTranslationAlignment(
        expected_record_version=version,
        action=action,
        reason="Independent synthetic translation review",
    )


def test_exact_clause_alignment_preserves_original_and_never_promotes_evidence(fixture):
    f = fixture
    request = pair(f)
    with f["sf"]() as s:
        before = [
            (row.structure_node_id, row.original_text, row.citation_id)
            for row in s.scalars(
                select(k.KnowledgeStructureNodeEntity).where(
                    k.KnowledgeStructureNodeEntity.knowledge_version_id.in_(
                        [str(request.source_version_id), str(request.target_version_id)]
                    ),
                )
            )
        ]
    created = owner(f).create(request)
    assert created["source_language"] == "en" and created["target_language"] == "ar"
    assert created["review_status"] == "PENDING" and not created["official_evidence"]
    assert created["submitted_by"] == "translator" and created["submitted_at"]
    assert all(
        created["pairs"][0][key]
        for key in [
            "source_citation_id",
            "target_citation_id",
            "source_text_sha256",
            "target_text_sha256",
        ]
    )
    approved = owner(f, "independent-reviewer").review(created["translation_id"], review())
    assert approved["review_status"] == "APPROVED" and not approved["official_evidence"]
    assert approved["reviewer"] == "independent-reviewer" and approved["reviewed_at"]
    assert owner(f).list(request.source_version_id)["items"] == [approved]
    with f["sf"]() as s:
        assert before == [
            (row.structure_node_id, row.original_text, row.citation_id)
            for row in s.scalars(
                select(k.KnowledgeStructureNodeEntity).where(
                    k.KnowledgeStructureNodeEntity.knowledge_version_id.in_(
                        [str(request.source_version_id), str(request.target_version_id)]
                    ),
                )
            )
        ]
        assert s.get(
            k.KnowledgeTranslationEntity, created["translation_id"]
        ).translated_text_ref == ("knowledge-version://" + str(request.target_version_id))


def test_alignment_independent_reviewer_cas_and_terminal_history(fixture):
    f = fixture
    created = owner(f).create(pair(f))
    with pytest.raises(ValueError, match="USE_TYPED_TRANSLATION_ALIGNMENT_REVIEW"):
        f["reviewer"].approve_translation(created["translation_id"], 1)
    with pytest.raises(KnowledgeManagementConflict, match="INDEPENDENT"):
        owner(f).review(created["translation_id"], review())
    with pytest.raises(KnowledgeManagementConflict, match="VERSION_CONFLICT"):
        owner(f, "reviewer").review(created["translation_id"], review(2))
    rejected = owner(f, "reviewer").review(created["translation_id"], review(action="REJECT"))
    assert rejected["review_status"] == "REJECTED"
    with pytest.raises(KnowledgeManagementConflict, match="VERSION_CONFLICT"):
        owner(f, "reviewer").review(created["translation_id"], review(2))


def test_alignment_rejects_wrong_version_foreign_nodes_and_coarse_scope(fixture):
    f = fixture
    request = pair(f)
    with pytest.raises(ValueError, match="NODE_VERSION_MISMATCH"):
        owner(f).create(
            request.model_copy(
                update={
                    "pairs": (
                        request.pairs[0].model_copy(
                            update={"target_node_id": request.pairs[0].source_node_id}
                        ),
                    )
                }
            )
        )
    with pytest.raises(KnowledgeManagementConflict, match="VERSION_CONFLICT"):
        owner(f).create(request.model_copy(update={"expected_source_record_version": 999}))
    with pytest.raises(PermissionError):
        owner(f, scopes={"knowledge:admin"}).create(request)
    outsider = PostgresKnowledgeTranslationAlignment(
        f["sf"],
        RepositoryContext.user(
            uuid4(),
            "foreign",
            {"knowledge:translation:read", "knowledge:translation:write"},
        ),
    )
    with pytest.raises(LookupError):
        outsider.create(request)
    with pytest.raises(LookupError):
        outsider.list(request.source_version_id)


def test_alignment_http_caller_cannot_appoint_reviewer_or_official_authority(fixture):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.routes.knowledge_translation_alignment import router

    f = fixture
    request = pair(f)
    for extra in [{"submitted_by": "spoof"}, {"translation_method": "OFFICIAL"}]:
        with pytest.raises(ValidationError):
            CreateTranslationAlignment.model_validate({**request.model_dump(), **extra})
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)

    @app.middleware("http")
    async def host(request, call_next):
        request.state.repository_context = owner(f).context
        return await call_next(request)

    with TestClient(app) as client:
        prefix = "/api/v1/admin/knowledge-management"
        created = client.post(
            prefix + "/translation-alignments", json=request.model_dump(mode="json")
        )
        assert created.status_code == 201, created.text
        assert created.json()["submitted_by"] == "translator"
        listed = client.get(
            prefix + f"/documents/versions/{request.source_version_id}/translation-alignments"
        )
        assert listed.status_code == 200 and listed.json()["total"] == 1
