"""Actual PostgreSQL FTS/pgvector filters, not an in-memory search simulation."""

from uuid import uuid4

import pytest
from phase1g_fixtures import publish
from sqlalchemy import select, text
from test_phase1f_postgres import (
    FakeEmbedding,
    binding,
    embedding_config,
    scope,
)
from test_phase1f_postgres import (
    fixture as fixture,
)

from crossborder_compliance.application.knowledge_services import EmbeddingFoundationService
from crossborder_compliance.domain.retrieval import KnowledgeRetrievalPolicy, RetrievalSearchPlan
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.retrieval_search import (
    PgvectorRetrieverAdapter,
    PostgresFTSRetrieverAdapter,
)

pytestmark = pytest.mark.runtime_smoke


def search_fixture(f):
    config = embedding_config(f)
    from test_phase1g_persistence_postgres import policies

    policies(f, vector_weight=0.5, embedding_config_id=config)
    versions = [
        publish(f, [binding(f, permissions=["read:internal"])]),
        publish(f, [binding(f, dimensions={"product": [f["b"]]})]),
        publish(f, [binding(f, permissions=["secret:read"])]),
    ]
    indexes = {}
    for v in versions:
        index = EmbeddingFoundationService(f["repo"], FakeEmbedding()).build(
            v["knowledge_version_id"], config
        )
        indexes[v["knowledge_version_id"]] = index["index_version_id"]
    resolved = scope(f, snapshot_id=f["snapshot"])
    with f["sf"]() as s:
        records = tuple(
            s.scalars(
                select(k.EmbeddingRecordEntity.embedding_record_id).where(
                    k.EmbeddingRecordEntity.tenant_id == f["tenant"]
                )
            )
        )
        # Secret and unrelated items have identical similarity, but cannot enter candidates.
        s.execute(
            text(
                "UPDATE embedding_records SET embedding_vector=CAST(:v AS vector) "
                "WHERE tenant_id=:t"
            ),
            {"v": "[1,0,0,0]", "t": f["tenant"]},
        )
        s.commit()
    allowed = set(resolved.filter_spec.version_filter)
    p = KnowledgeRetrievalPolicy(
        policy_id=str(uuid4()),
        policy_version_id=str(uuid4()),
        version=1,
        sufficiency_policy_id=str(uuid4()),
        embedding_config_id=config,
    )
    plan = RetrievalSearchPlan(
        scope=resolved,
        filter_spec=resolved.filter_spec,
        policy=p,
        index_versions={v: i for v, i in indexes.items() if v in allowed},
        embedding_record_ids=records,
        languages=("en",),
    )
    return plan, versions


def test_real_fts_vector_filter_before_ranking(fixture):
    f = fixture
    plan, versions = search_fixture(f)
    lexical = PostgresFTSRetrieverAdapter(f["sf"], f["ctx"]).retrieve("Generic", plan)
    vector = PgvectorRetrieverAdapter(f["sf"], f["ctx"]).retrieve((1, 0, 0, 0), plan)
    assert lexical.candidates and vector.candidates
    assert {c.knowledge_version_id for c in lexical.candidates} == {
        versions[0]["knowledge_version_id"]
    }
    assert {c.knowledge_version_id for c in vector.candidates} == {
        versions[0]["knowledge_version_id"]
    }
    assert all(c.vector_score == 1 for c in vector.candidates)
    assert len(vector.candidates) == len(lexical.candidates) == 2
    assert all(c.lexical_score > 0 for c in lexical.candidates)


def test_actual_search_current_permission_revocation_and_tenant(fixture):
    f = fixture
    plan, _ = search_fixture(f)
    revoked = RepositoryContext.user(f["ctx"].tenant_id, "author")
    assert not PostgresFTSRetrieverAdapter(f["sf"], revoked).retrieve("Generic", plan).candidates
    assert not PgvectorRetrieverAdapter(f["sf"], revoked).retrieve((1, 0, 0, 0), plan).candidates
    outsider = RepositoryContext.user(uuid4(), "other", {"read:internal"})
    with pytest.raises(PermissionError):
        PostgresFTSRetrieverAdapter(f["sf"], outsider).retrieve("Generic", plan)


def test_search_snapshot_never_adds_new_index_and_languages_narrow(fixture):
    f = fixture
    plan, _ = search_fixture(f)
    later = publish(f)
    f["repo"].build_index(later["knowledge_version_id"])
    assert later["knowledge_version_id"] not in plan.index_versions
    empty = plan.model_copy(update={"languages": ("generic-other",)})
    assert not PostgresFTSRetrieverAdapter(f["sf"], f["ctx"]).retrieve("Generic", empty).candidates
    with pytest.raises(ValueError):
        PgvectorRetrieverAdapter(f["sf"], f["ctx"]).retrieve((0, 0, 0, 0), plan)
