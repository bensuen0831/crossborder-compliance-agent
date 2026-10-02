"""Scope-first cases over actual canonical indexes, including immutable history."""

from uuid import uuid4

import pytest
from phase1g_fixtures import publish
from sqlalchemy import func, select
from test_phase1f_postgres import (
    FakeEmbedding,
    binding,
    context,
    embedding_config,
    item,
    scope,
    step,
)
from test_phase1f_postgres import (
    fixture as fixture,
)
from test_phase1g_external_postgres import external_setup
from test_phase1g_persistence_postgres import policies, query, service

from crossborder_compliance.application.knowledge_services import EmbeddingFoundationService
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.retrieval_test_adapters import DeterministicTestEmbedding

pytestmark = pytest.mark.runtime_smoke


def test_historical_snapshot_retrieval_and_expired_fresh_exclusion(fixture):
    f = fixture
    old = publish(f)
    f["repo"].build_index(old["knowledge_version_id"])
    r, p, _ = policies(f)
    frozen = service(f, r).retrieve(query(f, p))["rag_context_pack"]["evidence_pack"]
    new = publish(f, doc=old["document_id"])
    f["repo"].build_index(new["knowledge_version_id"])
    repeat = service(f, r).retrieve(query(f, p))["rag_context_pack"]["evidence_pack"]
    assert {i["knowledge_version_id"] for i in repeat["items"]} == {old["knowledge_version_id"]}
    assert {i["content_hash"] for i in frozen["items"]} == {
        i["content_hash"] for i in repeat["items"]
    }
    # Explicit expiration removes a version from new scopes; historical pins remain approved.
    step(f, new, "expire")
    assert new["knowledge_version_id"] not in scope(f).filter_spec.version_filter


def test_multi_product_minimal_subject_scope(fixture):
    f = fixture
    run = context(f, [f["a"], f["b"]], [f["a"], f["b"]])
    a = publish(f)
    bb = publish(f, [binding(f, dimensions={"product": [f["b"]]})])
    for v in (a, bb):
        f["repo"].build_index(v["knowledge_version_id"])
    ia = item(f, f["a"], run["version"])
    ib = item(f, f["b"], run["version"])
    r, p, _ = policies(f)
    for ident, version in ((ia, a), (ib, bb)):
        result = service(f, r).retrieve(query(f, p, subject_type="DATA_ITEM", subject_id=ident))
        assert {
            i["knowledge_version_id"] for i in result["rag_context_pack"]["evidence_pack"]["items"]
        } == {version["knowledge_version_id"]}


def test_product_conflict_no_internal_or_external_product_broadening(fixture):
    f = fixture
    context(f, [f["a"]], [f["b"]])
    v = publish(f)
    f["repo"].build_index(v["knowledge_version_id"])
    r, p, _, downloader, external = external_setup(f)
    result = service(f, r, external=external).retrieve(query(f, p))["rag_context_pack"]
    assert result["scope"]["review_required"]
    assert not result["evidence_pack"]["items"] and downloader.calls == 0
    assert result["fallback_guidance_context"]["finalization_requires_verification"]


@pytest.mark.parametrize("dimension", ["jurisdiction", "scenario", "industry", "data_category"])
def test_incompatible_dimensions_cannot_enter_candidates(fixture, dimension):
    from test_phase1f_postgres import metadata

    from crossborder_compliance.infrastructure.persistence import models as b

    f = fixture
    if dimension == "jurisdiction":
        foreign = str(uuid4())
        with f["sf"]() as s, s.begin():
            s.add(
                b.JurisdictionEntity(
                    tenant_id=f["tenant"],
                    jurisdiction_id=foreign,
                    code=foreign,
                    name="Generic Other",
                )
            )
    else:
        foreign = metadata(f["sf"], f["tenant"], dimension.upper())
    v = publish(f, [binding(f, dimensions={"product": [f["a"]], dimension: [foreign]})])
    f["repo"].build_index(v["knowledge_version_id"])
    r, p, _ = policies(f)
    response = service(f, r).retrieve(query(f, p))
    assert response["statistics"]["lexical_count"] == 0
    assert not response["rag_context_pack"]["evidence_pack"]["items"]


def test_query_embedding_uses_registry_and_real_pgvector(fixture):
    f = fixture
    config = embedding_config(f)
    r, p, _ = policies(f, vector_weight=0.5, embedding_config_id=config)
    v = publish(f)
    EmbeddingFoundationService(f["repo"], FakeEmbedding()).build(v["knowledge_version_id"], config)
    result = service(f, r, embedding=DeterministicTestEmbedding()).retrieve(query(f, p))
    assert result["statistics"]["vector_count"] == 2
    assert len({i["chunk_id"] for i in result["rag_context_pack"]["evidence_pack"]["items"]}) == 2
    assert all(
        i["vector_score"] is not None and i["lexical_score"] is not None
        for i in result["rag_context_pack"]["evidence_pack"]["items"]
    )


def test_failed_provider_run_retained_without_partial_pack(fixture):
    f = fixture
    config = embedding_config(f)
    r, p, _ = policies(f, vector_weight=0.5, embedding_config_id=config)
    v = publish(f)
    EmbeddingFoundationService(f["repo"], FakeEmbedding()).build(v["knowledge_version_id"], config)
    with pytest.raises(ValueError, match="EMBEDDING_PORT_NOT_CONFIGURED"):
        service(f, r).retrieve(query(f, p))
    with f["sf"]() as s:
        run = s.scalar(
            select(g.RetrievalRunEntity).where(g.RetrievalRunEntity.tenant_id == f["tenant"])
        )
        assert run.status == "FAILED"
        assert (
            s.scalar(
                select(func.count())
                .select_from(g.EvidencePackEntity)
                .where(g.EvidencePackEntity.tenant_id == f["tenant"])
            )
            == 0
        )
