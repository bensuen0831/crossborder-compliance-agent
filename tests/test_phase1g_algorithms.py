from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from crossborder_compliance.application.retrieval_algorithms import (
    FallbackGuidanceService,
    HybridMergeStrategy,
    KnowledgeSufficiencyService,
    RerankService,
    RetrievalScopeValidator,
)
from crossborder_compliance.domain.knowledge import KnowledgeFilterSpec, KnowledgeScope
from crossborder_compliance.domain.retrieval import (
    EvidencePack,
    EvidencePackItem,
    KnowledgeRetrievalPolicy,
    KnowledgeSufficiencyPolicy,
    LexicalRetrievalResult,
    RetrievalCandidate,
    VectorRetrievalResult,
)


def policy(**changes):
    return KnowledgeRetrievalPolicy.model_validate(
        dict(
            dict(
                policy_id="policy",
                policy_version_id="policy-v1",
                version=1,
                vector_weight=0,
                lexical_weight=1,
                sufficiency_policy_id="sufficiency",
            ),
            **changes,
        )
    )


def scoped():
    filters = KnowledgeFilterSpec(
        tenant_filter="tenant",
        permission_filter=("read:internal",),
        lifecycle_filter=("ACTIVE",),
        effective_date_filter=date.today(),
        jurisdiction_filter=("jurisdiction",),
        product_filter={"product": ("a",)},
        scenario_filter=(),
        industry_filter=(),
        data_category_filter=(),
        language_filter=(),
        scope_type_filter=("PRODUCT_SPECIFIC",),
        version_filter=("v1",),
        binding_filter=("b1",),
    )
    return KnowledgeScope(
        tenant_id="tenant",
        project_id="project",
        analysis_snapshot_id="snapshot",
        subject_type="PROJECT",
        subject_id="project",
        allowed_jurisdiction_ids=("jurisdiction",),
        allowed_product_ids=("a",),
        allowed_scope_types=("PRODUCT_SPECIFIC",),
        permission_filters=("read:internal",),
        lifecycle_filters=("ACTIVE",),
        effective_as_of=date.today(),
        excluded_bindings=(),
        unresolved_scopes=(),
        reason_codes=(),
        review_required=False,
        version=1,
        filter_spec=filters,
    )


def evidence(**changes):
    data = dict(
        evidence_item_id="item",
        knowledge_document_id="document",
        knowledge_version_id="v1",
        structure_node_id="node",
        chunk_id="chunk",
        citation_id="citation",
        source_id="source",
        source_url="https://approved.example.test/knowledge",
        source_authority="authority-ref",
        source_tier="T1_PRIMARY_OFFICIAL",
        jurisdiction_id="jurisdiction",
        jurisdiction_specific=True,
        canonical_locator="ARTICLE/1",
        language="en",
        effective_from=date.today() - timedelta(days=1),
        evidence_quality=1,
        content_hash="a" * 64,
        retrieval_run_id="run",
        analysis_snapshot_id="snapshot",
        knowledge_index_version="index",
        retrieval_policy_version="policy-v1",
        original_text="Generic authoritative evidence",
        provenance={"approved": True},
    )
    return EvidencePackItem.model_validate(dict(data, **changes))


def assess(items, **changes):
    p = KnowledgeSufficiencyPolicy(
        policy_id="sufficiency", policy_version_id="suff-v1", version=1, **changes
    )
    pack = EvidencePack(
        evidence_pack_id="pack",
        retrieval_run_id="run",
        analysis_snapshot_id="snapshot",
        items=items,
        manifest={},
    )
    return KnowledgeSufficiencyService().assess(pack, scoped(), p), p


@pytest.mark.parametrize("strategy", ["WEIGHTED_SCORE", "RECIPROCAL_RANK_FUSION"])
def test_hybrid_deduplicates_stably_and_preserves_individual_scores(strategy):
    a = RetrievalCandidate(
        chunk_id="a", knowledge_version_id="v1", index_version_id="i1", lexical_score=0.2
    )
    b = RetrievalCandidate(
        chunk_id="b", knowledge_version_id="v1", index_version_id="i1", lexical_score=0.1
    )
    v = a.model_copy(update={"lexical_score": None, "vector_score": 0.8})
    lexical = LexicalRetrievalResult(candidates=(a, b, a))
    vv = VectorRetrievalResult(candidates=(v,))
    p = policy(hybrid_strategy=strategy)
    one = HybridMergeStrategy().merge(lexical, vv, p)
    assert one == HybridMergeStrategy().merge(lexical, vv, p)
    assert len(one.candidates) == 2
    aa = next(c for c in one.candidates if c.chunk_id == "a")
    assert aa.lexical_score == 0.2 and aa.vector_score == 0.8
    assert aa.hybrid_score > 0 and aa.channels == ("LEXICAL", "VECTOR")


def test_reranker_injected_candidate_dropped_with_audit_and_scope_checked_again():
    a = RetrievalCandidate(
        chunk_id="a",
        knowledge_version_id="v1",
        index_version_id="i1",
        lexical_score=0.2,
        hybrid_score=0.1,
    )

    class Injection:
        def rerank(self, text, candidates, *, model_config_id):
            assert candidates == (a,)
            return (("forbidden", 1), ("a", 0.5))

    result = RerankService(Injection()).rerank("query", (a,), policy(rerank_enabled=True))
    assert [c.chunk_id for c in result.candidates] == ["a"]
    assert result.dropped[0]["reason_code"] == "RERANK_OUTSIDE_ALLOWED_SET"
    assert result.candidates[0].lexical_score == 0.2

    class Revocation:
        def eligible_chunk_ids(self, plan, ids):
            return ()

    final = RetrievalScopeValidator(Revocation()).validate(result.candidates, None)
    assert final.status == "NARROWED" and not final.allowed_chunk_ids and final.dropped


def test_verified_jurisdiction_effective_evidence_is_sufficient():
    result, p = assess((evidence(),))
    assert result.status == "SUFFICIENT" and all(result.jurisdiction_coverage.values())
    assert FallbackGuidanceService().build(result, p) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"jurisdiction_specific": False},
        {"source_tier": "T3_APPROVED_SECONDARY"},
        {"effective_to": date.today() - timedelta(days=1)},
        {"source_authority": None},
    ],
)
def test_generic_supporting_expired_or_unattributed_evidence_not_sufficient(changes):
    result, _ = assess((evidence(**changes),))
    assert result.status == "INSUFFICIENT"


def test_missing_topics_partial_and_similarity_does_not_create_coverage():
    result, _ = assess(
        (evidence(hybrid_score=1, rerank_score=1),), required_topic_refs=("missing-topic",)
    )
    assert result.status == "PARTIALLY_SUFFICIENT" and result.missing_topics == ("missing-topic",)


def test_conflicting_approved_claims_preserved_and_guidance_nonempty():
    a = evidence(conflict_key="generic-claim", claim_hash="a" * 64)
    b = evidence(evidence_item_id="other", conflict_key="generic-claim", claim_hash="b" * 64)
    result, p = assess((a, b))
    assert result.status == "CONFLICTED" and result.conflicting_evidence_count == 2
    guidance = FallbackGuidanceService().build(result, p)
    assert guidance.operational_next_steps and guidance.unresolved_legal_questions
    assert not guidance.compliance_path and guidance.finalization_requires_verification
    assert not guidance.verified_requirements


def test_no_evidence_still_yields_actions_without_unsupported_legal_claims():
    result, p = assess(())
    g = FallbackGuidanceService().build(result, p)
    assert result.status == "INSUFFICIENT"
    assert g.conservative_controls and g.evidence_acquisition_steps
    assert g.jurisdiction_verification_steps and g.operational_next_steps
    assert "UNSUPPORTED_LEGAL_APPLICABILITY" in g.prohibited_assertions
    assert not g.verified_requirements and not g.compliance_path


def test_policy_and_evidence_contracts_prevent_unbounded_or_unverified_sources():
    with pytest.raises(ValidationError):
        policy(vector_weight=1, embedding_config_id=None)
    with pytest.raises(ValidationError):
        evidence(source_tier="T4_LLM_DISCOVERY_ONLY")
    with pytest.raises(ValidationError):
        evidence(external_evidence_id="external-and-internal")


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@approved.example/knowledge",
        "https://approved.example/knowledge?token=secret",
        "http://approved.example/knowledge",
        "https://approved.example/knowledge#fragment",
    ],
)
def test_trusted_redirect_policy_cannot_expose_credentials(url):
    from crossborder_compliance.domain.retrieval import TrustedSourceRule

    with pytest.raises(ValidationError):
        TrustedSourceRule(
            source_id="source",
            authority_ref="authority",
            source_tier="T1_PRIMARY_OFFICIAL",
            jurisdiction_ids=("jurisdiction",),
            permission_scopes=(),
            scope_type="GLOBAL",
            approved_redirect_urls=(url,),
        )
