"""Transactional derived retrieval and immutable policy pins on real PostgreSQL."""

from uuid import uuid4

import pytest
from phase1g_fixtures import publish
from sqlalchemy import func, select
from test_phase1f_postgres import binding
from test_phase1f_postgres import fixture as fixture

from crossborder_compliance.application.retrieval_services import KnowledgeRetrievalService
from crossborder_compliance.domain.retrieval import KnowledgeRetrievalQuery
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)
from crossborder_compliance.infrastructure.retrieval_search import (
    PgvectorRetrieverAdapter,
    PostgresFTSRetrieverAdapter,
)

pytestmark = pytest.mark.runtime_smoke


def policies(f, **changes):
    r = PostgresRetrievalRepository(f["sf"], f["ctx"])
    suff = r.create_policy("sufficiency", {})
    r.publish_policy("sufficiency", suff["policy_version_id"], 1)
    p = r.create_policy(
        "retrieval",
        dict(
            dict(vector_weight=0, lexical_weight=1, sufficiency_policy_id=suff["policy_id"]),
            **changes,
        ),
    )
    r.publish_policy("retrieval", p["policy_version_id"], 1)
    return r, p, suff


def query(f, p, **changes):
    return KnowledgeRetrievalQuery.model_validate(
        dict(
            dict(
                project_id=f["project"],
                analysis_snapshot_id=f["snapshot"],
                policy_id=p["policy_id"],
                query_text="Generic",
                idempotency_key=str(uuid4()),
            ),
            **changes,
        )
    )


def service(f, r, **ports):
    return KnowledgeRetrievalService(
        r,
        f["ctx"],
        PostgresFTSRetrieverAdapter(f["sf"], f["ctx"]),
        PgvectorRetrieverAdapter(f["sf"], f["ctx"]),
        **ports,
    )


def test_run_pack_sufficiency_idempotency_and_reproducibility(fixture):
    f = fixture
    v = publish(f, [binding(f, permissions=["read:internal"])])
    f["repo"].build_index(v["knowledge_version_id"])
    r, p, _ = policies(f)
    q = query(f, p)
    response = service(f, r).retrieve(q)
    rag = response["rag_context_pack"]
    assert response["status"] == "COMPLETED" and len(rag["evidence_pack"]["items"]) == 2
    assert rag["knowledge_sufficiency"]["status"] == "INSUFFICIENT"
    assert rag["fallback_guidance_context"]["operational_next_steps"]
    repeat = service(f, r).retrieve(q)
    assert repeat["retrieval_run_id"] == response["retrieval_run_id"]
    assert repeat["rag_context_pack"]["evidence_pack"] == rag["evidence_pack"]
    with pytest.raises(OptimisticConcurrencyError):
        service(f, r).retrieve(q.model_copy(update={"query_text": "changed"}))
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(g.RetrievalRunEntity)
                .where(g.RetrievalRunEntity.tenant_id == f["tenant"])
            )
            == 1
        )
    # Revocation prevents cached evidence leaks.
    f["repo"].update_source(f["source"], {"enabled": False}, 1)
    narrowed = r.scoped_saved_response(response["retrieval_run_id"])
    assert not narrowed["rag_context_pack"]["evidence_pack"]["items"]


def test_policy_snapshot_pin_optimistic_and_empty_guidance(fixture):
    f = fixture
    r, p, suff = policies(f)
    old = r.resolve_policy("retrieval", p["policy_id"], f["snapshot"])
    new = r.create_policy(
        "retrieval",
        dict(vector_weight=0, lexical_weight=1, top_k=2, sufficiency_policy_id=suff["policy_id"]),
        p["policy_id"],
    )
    with pytest.raises(OptimisticConcurrencyError):
        r.publish_policy("retrieval", new["policy_version_id"], 9)
    r.publish_policy("retrieval", new["policy_version_id"], 1)
    assert r.resolve_policy("retrieval", p["policy_id"], f["snapshot"]) == old
    response = service(f, r).retrieve(query(f, p))
    assert not response["rag_context_pack"]["evidence_pack"]["items"]
    assert response["rag_context_pack"]["fallback_guidance_context"]["evidence_acquisition_steps"]


def test_rerank_injection_is_audited_and_no_scope_extension(fixture):
    f = fixture
    a = publish(f)
    b = publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    for v in (a, b):
        f["repo"].build_index(v["knowledge_version_id"])
    r, p, _ = policies(f, rerank_enabled=True)

    class Bad:
        def rerank(self, q, candidates, **kw):
            return ((str(uuid4()), 999),) + tuple((c.chunk_id, 1) for c in candidates)

    result = service(f, r, reranker=Bad()).retrieve(query(f, p))
    assert all(
        i["knowledge_version_id"] == a["knowledge_version_id"]
        for i in result["rag_context_pack"]["evidence_pack"]["items"]
    )
    assert result["statistics"]["dropped_count"] == 1
    assert result["traces"][1]["details"]["dropped"]


def test_pack_commit_fk_failure_rolls_back_without_parallel_result(fixture, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    f = fixture
    v = publish(f)
    f["repo"].build_index(v["knowledge_version_id"])
    r, p, _ = policies(f)
    original = r.internal_evidence

    def invalid(*args):
        items = original(*args)
        return (items[0].model_copy(update={"citation_id": str(uuid4())}),)

    monkeypatch.setattr(r, "internal_evidence", invalid)
    with pytest.raises(IntegrityError):
        service(f, r).retrieve(query(f, p))
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(g.EvidencePackEntity)
                .where(g.EvidencePackEntity.tenant_id == f["tenant"])
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(g.EvidencePackItemEntity)
                .where(g.EvidencePackItemEntity.tenant_id == f["tenant"])
            )
            == 0
        )
        assert (
            s.scalar(
                select(g.RetrievalRunEntity).where(g.RetrievalRunEntity.tenant_id == f["tenant"])
            ).status
            == "FAILED"
        )
