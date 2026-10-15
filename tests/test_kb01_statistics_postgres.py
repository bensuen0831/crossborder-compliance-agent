"""Actual SQL counts reconcile with authorized list filters and canonical mutations."""

from uuid import UUID

import pytest
from test_kb01_document_management_postgres import knowledge as knowledge
from test_kb01_document_management_postgres import make, published_label, service

from crossborder_compliance.domain.knowledge_management import (
    KnowledgeDocumentMetadata,
    KnowledgeManagementPermissionError,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.knowledge_statistics import (
    PostgresKnowledgeStatistics,
)

pytestmark = pytest.mark.runtime_smoke


def statistics(f, scopes=None):
    return PostgresKnowledgeStatistics(
        f["sf"],
        RepositoryContext.user(
            UUID(f["tenant"]),
            "statistics-reader",
            {"knowledge:statistics:read", "knowledge:document:read"} if scopes is None else scopes,
        ),
    )


def test_sql_statistics_reconciles_list_scope_and_many_to_many_labels(knowledge):
    f = knowledge
    labels = (published_label(f), published_label(f, "RESEARCH_TOPIC"))
    make(f, KnowledgeDocumentMetadata(title="Scoped source one", labels=labels))
    make(f, KnowledgeDocumentMetadata(title="Scoped source two", labels=(labels[0],)))
    make(f, KnowledgeDocumentMetadata(title="Other source"))
    for filters in [
        {},
        {"query": "Scoped"},
        {"label_id": labels[1].definition_id},
        {"language": "ar"},
        {"lifecycle": "DRAFT"},
    ]:
        actual = statistics(f).summary(**filters)
        listed = service(f).list(**filters)
        assert actual["documents"] == listed["total"]
    actual = statistics(f).summary(query="Scoped")
    assert actual["documents"] == 2
    assert sum(group["documents"] for group in actual["by_classification"]) == 3
    assert actual["many_to_many_group_totals_are_not_global_totals"] is True
    assert actual["attached_bytes"] == 0 and actual["attached_originals"] == 0


def test_statistics_requires_current_read_and_statistics_grants(knowledge):
    f = knowledge
    make(f)
    for grants in [set(), {"knowledge:document:read"}, {"knowledge:statistics:read"}]:
        with pytest.raises(KnowledgeManagementPermissionError):
            statistics(f, grants).summary()


def test_statistics_does_not_include_another_tenant(knowledge):
    f = knowledge
    make(f)
    before = statistics(f).summary()
    from test_phase1f_postgres import fixture

    foreign = fixture.__wrapped__()
    for _ in range(3):
        make(foreign)
    after = statistics(f).summary()
    assert after["documents"] == before["documents"]
    assert after["versions"] == before["versions"]


def test_clause_preview_uses_exact_version_and_preserves_source_identity(knowledge):
    from test_phase1f_postgres import draft, ingest, inputs

    from crossborder_compliance.infrastructure.persistence.knowledge_document_management import (
        PostgresKnowledgeDocumentManagement,
    )

    f = knowledge
    original = "<script>not executable</script> Article 7. " + "來源" * 3000
    version = draft(f)
    ingest(
        f,
        version,
        inputs(
            f,
            nodes=[
                {
                    "node_type": "ARTICLE",
                    "canonical_locator": "article/7",
                    "original_text": original,
                    "official_number": "7",
                }
            ],
        ),
    )
    owner = PostgresKnowledgeDocumentManagement(f["sf"], statistics(f).context)
    page = owner.preview(version["knowledge_version_id"], page=1, page_size=1)
    assert page["total"] == 1
    row = page["items"][0]
    assert row["original_excerpt"] == original[:4000]
    assert row["official_number"] == "7" and row["canonical_locator"] == "article/7"
    assert row["excerpt_truncated"] is True and row["citation_id"]
    assert owner.preview(version["knowledge_version_id"], page=2, page_size=1)["items"] == []
    from sqlalchemy import select

    from crossborder_compliance.infrastructure.persistence import knowledge_models as k

    with f["sf"]() as session:
        stored = session.scalar(
            select(k.KnowledgeStructureNodeEntity).where(
                k.KnowledgeStructureNodeEntity.structure_node_id == row["structure_node_id"]
            )
        )
        assert stored.original_text == original
    from test_phase1f_postgres import fixture

    foreign = fixture.__wrapped__()
    with pytest.raises(LookupError):
        PostgresKnowledgeDocumentManagement(foreign["sf"], statistics(foreign).context).preview(
            version["knowledge_version_id"]
        )


def test_statistics_and_capabilities_http_trust_server_context_only(knowledge):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.routes.knowledge_management import (
        router as management,
    )
    from crossborder_compliance.interfaces.api.routes.knowledge_statistics import router

    f = knowledge
    make(f)
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)
    app.include_router(management)
    prefix = "/api/v1/admin/knowledge-management"
    with TestClient(app) as client:
        assert client.get(prefix + "/statistics").status_code == 401
        assert client.get(prefix + "/capabilities").status_code == 401

    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.include_router(router)
    app.include_router(management)

    @app.middleware("http")
    async def trusted_host(request, call_next):
        request.state.repository_context = statistics(f).context
        return await call_next(request)

    with TestClient(app) as client:
        reply = client.get(prefix + "/capabilities", headers={"X-Scopes": "knowledge:admin"})
        assert reply.status_code == 200
        assert reply.json()["operations"] == ["document:read", "statistics:read"]
        assert client.get(prefix + "/statistics").json()["documents"] == 1
        assert client.get(prefix + "/statistics?lifecycle=MADE_UP").status_code == 422
