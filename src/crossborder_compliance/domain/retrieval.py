"""Phase 1G derived retrieval, evidence and governance contracts; no legal decisions."""

from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from crossborder_compliance.domain.knowledge import (
    SOURCE_TYPES,
    Contract,
    FormalContext,
    KnowledgeFilterSpec,
    KnowledgeScope,
)

SourceTier = Literal[
    "T1_PRIMARY_OFFICIAL",
    "T2_OFFICIAL_GUIDANCE",
    "T3_INTERGOVERNMENTAL",
    "T3_APPROVED_SECONDARY",
    "T4_UNVERIFIED_WEB",
    "T4_LLM_DISCOVERY_ONLY",
]
SufficiencyStatus = Literal["SUFFICIENT", "PARTIALLY_SUFFICIENT", "INSUFFICIENT", "CONFLICTED"]


class RetrievalContract(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class KnowledgeRetrievalQuery(RetrievalContract):
    project_id: str
    analysis_snapshot_id: str
    policy_id: str
    query_text: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=120)
    subject_type: Literal["PROJECT", "DATA_ITEM", "DATA_FLOW"] = "PROJECT"
    subject_id: str | None = None
    languages: tuple[str, ...] = ()


class KnowledgeRetrievalPolicy(RetrievalContract):
    policy_id: str
    policy_version_id: str
    version: int = Field(ge=1)
    allowed_knowledge_types: tuple[str, ...] = SOURCE_TYPES
    allowed_statuses: tuple[str, ...] = ("ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED")
    language_strategy: Literal["EXACT", "CONFIGURED_CROSS_LANGUAGE"] = "EXACT"
    allowed_languages: tuple[str, ...] = ()
    top_k: int = Field(default=10, ge=1, le=100)
    candidate_limit: int = Field(default=40, ge=1, le=1000)
    lexical_weight: float = Field(default=0.5, ge=0, le=1)
    vector_weight: float = Field(default=0.5, ge=0, le=1)
    hybrid_strategy: Literal["WEIGHTED_SCORE", "RECIPROCAL_RANK_FUSION"] = "RECIPROCAL_RANK_FUSION"
    rrf_constant: int = Field(default=60, ge=1, le=10000)
    embedding_config_id: str | None = None
    rerank_enabled: bool = False
    rerank_config_id: str | None = None
    graph_expansion_enabled: bool = False
    graph_expansion_limit: int = Field(default=10, ge=1, le=100)
    evidence_threshold: float = Field(default=0, ge=0, le=1)
    cross_language_enabled: bool = False
    external_augmentation_enabled: bool = False
    external_evidence_threshold: float = Field(default=0.8, ge=0, le=1)
    sufficiency_policy_id: str
    trusted_source_policy_id: str | None = None

    @model_validator(mode="after")
    def bounded(self):
        if self.lexical_weight + self.vector_weight <= 0:
            raise ValueError("positive retrieval weight required")
        if self.vector_weight and not self.embedding_config_id:
            raise ValueError("embedding config required for vector retrieval")
        if self.candidate_limit < self.top_k:
            raise ValueError("candidate limit smaller than top_k")
        if self.language_strategy == "CONFIGURED_CROSS_LANGUAGE" and (
            not self.cross_language_enabled or not self.allowed_languages
        ):
            raise ValueError("cross-language requires configured languages")
        if self.external_augmentation_enabled and not self.trusted_source_policy_id:
            raise ValueError("trusted source policy required")
        if not set(self.allowed_knowledge_types) <= set(SOURCE_TYPES):
            raise ValueError("canonical source types only")
        return self


class RetrievalCandidate(RetrievalContract):
    chunk_id: str
    knowledge_version_id: str
    index_version_id: str
    lexical_score: float | None = None
    vector_score: float | None = None
    hybrid_score: float = 0
    rerank_score: float | None = None
    channels: tuple[str, ...] = ()


class LexicalRetrievalResult(RetrievalContract):
    candidates: tuple[RetrievalCandidate, ...]


class VectorRetrievalResult(LexicalRetrievalResult):
    pass


class HybridRetrievalResult(LexicalRetrievalResult):
    pass


class RerankResult(RetrievalContract):
    candidates: tuple[RetrievalCandidate, ...]
    dropped: tuple[dict, ...] = ()


class ScopeValidationResult(RetrievalContract):
    allowed_chunk_ids: tuple[str, ...]
    dropped: tuple[dict, ...] = ()
    status: Literal["PASS", "NARROWED"]


class RetrievalSearchPlan(RetrievalContract):
    scope: KnowledgeScope
    filter_spec: KnowledgeFilterSpec
    policy: KnowledgeRetrievalPolicy
    index_versions: dict[str, str]
    embedding_record_ids: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()


class EvidencePackItem(RetrievalContract):
    evidence_item_id: str
    knowledge_document_id: str | None = None
    knowledge_version_id: str | None = None
    external_evidence_id: str | None = None
    structure_node_id: str
    chunk_id: str
    citation_id: str
    source_id: str
    source_url: str
    source_authority: str | None = None
    source_tier: SourceTier
    jurisdiction_id: str | None = None
    jurisdiction_specific: bool = False
    canonical_locator: str
    language: str
    effective_from: date | None = None
    effective_to: date | None = None
    lexical_score: float | None = None
    vector_score: float | None = None
    hybrid_score: float = 0
    rerank_score: float | None = None
    scope_validation_status: Literal["VALIDATED"] = "VALIDATED"
    evidence_quality: float = Field(ge=0, le=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_run_id: str
    analysis_snapshot_id: str
    knowledge_index_version: str | None = None
    retrieval_policy_version: str
    original_text: str
    topic_refs: tuple[str, ...] = ()
    regulation_refs: tuple[str, ...] = ()
    conflict_key: str | None = None
    claim_hash: str | None = None
    provenance: dict
    derived: Literal[True] = True
    legal_decision: Literal[False] = False

    @model_validator(mode="after")
    def source_chain(self):
        internal = bool(self.knowledge_document_id and self.knowledge_version_id)
        if internal == bool(self.external_evidence_id):
            raise ValueError("exactly one canonical or runtime external source chain")
        if internal and not self.knowledge_index_version:
            raise ValueError("internal evidence requires an index version")
        if self.source_tier.startswith("T4"):
            raise ValueError("discovery-only source cannot enter evidence")
        return self


class RetrievalEvidence(EvidencePackItem):
    pass


class EvidencePack(RetrievalContract):
    evidence_pack_id: str
    retrieval_run_id: str
    analysis_snapshot_id: str
    items: tuple[EvidencePackItem, ...]
    manifest: dict
    derived: Literal[True] = True
    legal_source_of_truth: Literal[False] = False


class KnowledgeSufficiencyPolicy(RetrievalContract):
    policy_id: str
    policy_version_id: str
    version: int = Field(ge=1)
    required_topic_refs: tuple[str, ...] = ()
    required_regulation_refs: tuple[str, ...] = ()
    minimum_authoritative_evidence_count: int = Field(default=1, ge=1, le=1000)
    minimum_evidence_quality: float = Field(default=0.8, ge=0, le=1)
    authoritative_tiers: tuple[SourceTier, ...] = ("T1_PRIMARY_OFFICIAL", "T2_OFFICIAL_GUIDANCE")
    require_explicit_jurisdiction_binding: Literal[True] = True
    guidance_actions: dict[str, str] = Field(
        default_factory=lambda: {
            "evidence_acquisition": "ACQUIRE_APPROVED_EVIDENCE_FOR_MISSING_COVERAGE",
            "jurisdiction_verification": "VERIFY_SOURCE_JURISDICTION_AND_EFFECTIVE_DATES",
            "operational_next_step": "PRESERVE_CONTEXT_AND_EVIDENCE_PROVENANCE",
            "conservative_control": "KEEP_UNVERIFIED_LEGAL_ASSERTIONS_OUT_OF_FINALIZATION",
        }
    )

    @model_validator(mode="after")
    def official_and_actionable(self):
        if not self.authoritative_tiers or not set(self.authoritative_tiers) <= {
            "T1_PRIMARY_OFFICIAL",
            "T2_OFFICIAL_GUIDANCE",
        }:
            raise ValueError("only verified official tiers satisfy jurisdiction sufficiency")
        if not all(
            self.guidance_actions.get(k)
            for k in (
                "evidence_acquisition",
                "jurisdiction_verification",
                "operational_next_step",
                "conservative_control",
            )
        ):
            raise ValueError("non-empty configured guidance actions required")
        return self


class KnowledgeSufficiencyResult(RetrievalContract):
    sufficiency_result_id: str
    tenant_id: str
    project_id: str
    analysis_snapshot_id: str
    subject_type: str
    subject_id: str
    jurisdiction_ids: tuple[str, ...]
    retrieval_run_id: str
    evidence_pack_id: str
    jurisdiction_coverage: dict[str, bool]
    regulation_coverage: dict[str, bool]
    official_source_coverage: float = Field(ge=0, le=1)
    effective_date_coverage: float = Field(ge=0, le=1)
    evidence_quality: float = Field(ge=0, le=1)
    evidence_count: int = Field(ge=0)
    conflicting_evidence_count: int = Field(ge=0)
    missing_topics: tuple[str, ...]
    reason_codes: tuple[str, ...]
    confidence: float = Field(ge=0, le=1)
    review_required: bool
    status: SufficiencyStatus
    policy_version: str


class GuidanceAction(RetrievalContract):
    action_code: str
    jurisdiction_ids: tuple[str, ...] = ()
    topic_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


class ActionableFallbackGuidanceContext(RetrievalContract):
    verified_requirements: tuple[str, ...] = ()
    verified_controls: tuple[str, ...] = ()
    conservative_controls: tuple[GuidanceAction, ...]
    evidence_acquisition_steps: tuple[GuidanceAction, ...]
    jurisdiction_verification_steps: tuple[GuidanceAction, ...]
    unresolved_legal_questions: tuple[str, ...]
    operational_next_steps: tuple[GuidanceAction, ...]
    prohibited_assertions: tuple[str, ...]
    evidence_status: SufficiencyStatus
    confidence: float = Field(ge=0, le=1)
    review_recommended: bool = True
    finalization_requires_verification: Literal[True] = True
    compliance_path: Literal[False] = False


class TrustedSourceRule(RetrievalContract):
    source_id: str
    authority_ref: str
    source_tier: SourceTier
    jurisdiction_ids: tuple[str, ...]
    permission_scopes: tuple[str, ...]
    scope_type: Literal["PRODUCT_SPECIFIC", "DOMAIN_SHARED", "CROSS_PRODUCT", "GLOBAL"]
    dimensions: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    approved_redirect_urls: tuple[str, ...] = ()

    @model_validator(mode="after")
    def credential_free_redirects(self):
        from urllib.parse import parse_qsl, urlsplit

        for url in self.approved_redirect_urls:
            parts = urlsplit(url)
            if (
                parts.scheme != "https"
                or not parts.hostname
                or parts.port not in (None, 443)
                or parts.username
                or parts.password
                or parts.fragment
                or "\\" in url
                or any(ord(c) < 33 for c in url)
                or any(
                    key.lower()
                    in {"token", "access_token", "api_key", "password", "secret", "signature"}
                    for key, value in parse_qsl(parts.query)
                )
            ):
                raise ValueError("redirect must be credential-free approved HTTPS")
        return self


class TrustedSourcePolicy(RetrievalContract):
    policy_id: str
    policy_version_id: str
    version: int = Field(ge=1)
    source_rules: tuple[TrustedSourceRule, ...]
    maximum_sources: int = Field(default=5, ge=1, le=20)
    timeout_seconds: int = Field(default=15, ge=1, le=60)
    max_file_size: int = Field(default=10000000, ge=1, le=10000000)
    redirect_limit: int = Field(default=3, ge=0, le=5)


class ExternalEvidenceCandidate(RetrievalContract):
    candidate_id: str
    source_id: str
    source_url: str
    discovery_origin: Literal["REGISTRY", "ADAPTER", "LLM_DISCOVERY_ONLY"] = "REGISTRY"
    suggested_authority: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)


class ExternalEvidenceValidationResult(RetrievalContract):
    candidate_id: str
    status: Literal["VERIFIED", "REJECTED", "DISCOVERY_ONLY"]
    reason_codes: tuple[str, ...]
    validation_checks: dict[str, bool]


class RuntimeVerifiedExternalEvidence(RetrievalContract):
    external_evidence_id: str
    analysis_snapshot_id: str
    source_id: str
    source_url: str
    canonical_url: str
    source_authority: str
    source_tier: SourceTier
    jurisdiction_ids: tuple[str, ...]
    retrieved_at: datetime
    publication_date: date | None = None
    effective_from: date
    effective_to: date | None = None
    language: str
    content_hash: str
    parsed_artifact_version: str
    parsed_structure: tuple[dict, ...]
    validation_result: ExternalEvidenceValidationResult
    retrieval_policy_version: str
    sufficiency_policy_version: str
    trusted_source_policy_version: str
    provenance: dict
    status: Literal["VERIFIED"] = "VERIFIED"
    active_knowledge: Literal[False] = False


class ExternalEvidencePack(RetrievalContract):
    records: tuple[RuntimeVerifiedExternalEvidence, ...] = ()
    validations: tuple[ExternalEvidenceValidationResult, ...] = ()
    reason_codes: tuple[str, ...] = ()


class RAGContextPack(RetrievalContract):
    structured_context: FormalContext
    scope: KnowledgeScope
    evidence_pack: EvidencePack
    knowledge_sufficiency: KnowledgeSufficiencyResult
    external_augmentation_metadata: dict
    fallback_guidance_context: ActionableFallbackGuidanceContext | None = None
    derived: Literal[True] = True
    legal_decision: Literal[False] = False


class RetrievalTrace(RetrievalContract):
    stage: str
    reason_code: str
    details: dict = Field(default_factory=dict)


class RetrievalStatistics(RetrievalContract):
    lexical_count: int = 0
    vector_count: int = 0
    deduplicated_count: int = 0
    reranked_count: int = 0
    dropped_count: int = 0
    internal_evidence_count: int = 0
    external_evidence_count: int = 0


class RetrievalRun(RetrievalContract):
    retrieval_run_id: str
    tenant_id: str
    owner_actor_id: str
    project_id: str
    analysis_snapshot_id: str
    policy_version_id: str
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    query: KnowledgeRetrievalQuery
    traces: tuple[RetrievalTrace, ...] = ()
    statistics: RetrievalStatistics = Field(default_factory=RetrievalStatistics)
    evidence_pack_id: str | None = None
    record_version: int = 1


class LLMWikiPage(RetrievalContract):
    wiki_page_id: str
    title: str
    active_version_id: str | None = None
    legal_basis: Literal[False] = False


class LLMWikiVersion(RetrievalContract):
    wiki_version_id: str
    wiki_page_id: str
    version: int
    content: str
    lifecycle: Literal["DRAFT", "VALIDATED", "PENDING_REVIEW", "APPROVED", "ACTIVE", "SUPERSEDED"]
    generated_by: str
    reviewed_by: str | None = None
    content_hash: str
    official_evidence: Literal[False] = False
    legal_basis: Literal[False] = False


class WikiSourceBinding(RetrievalContract):
    wiki_version_id: str
    knowledge_version_id: str


class WikiCitation(RetrievalContract):
    wiki_version_id: str
    citation_id: str


class WikiReview(RetrievalContract):
    wiki_version_id: str
    review_task_id: str
    reviewer: str | None = None
    status: str


class WikiPublishRecord(RetrievalContract):
    wiki_version_id: str
    published_by: str
    published_at: datetime


class GraphProvenance(RetrievalContract):
    source_knowledge_id: str
    source_knowledge_version_id: str
    source_evidence_id: str
    jurisdiction_id: str
    effective_from: date | None = None
    effective_to: date | None = None
    confidence: float = Field(ge=0, le=1)
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] = "DRAFT"
    generated_by: str
    reviewed_by: str | None = None
    version: int = Field(default=1, ge=1)
    derived: Literal[True] = True
    legal_applicability: Literal[False] = False


class KnowledgeGraphNode(GraphProvenance):
    graph_node_id: str
    node_type: str
    display_name: str


class KnowledgeGraphEdge(GraphProvenance):
    graph_edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type_ref: str
    inferred: bool = True


class KnowledgeRuntimeReadinessResult(RetrievalContract):
    knowledge_version_id: str
    tenant_id: str
    publication_event_id: str
    event_version: int = Field(ge=1)
    status: Literal["PENDING", "BUILDING", "READY", "FAILED"]
    index_version_id: str | None = None
    embedding_config_id: str | None = None
    registry_projection_version: str | None = None
    cache_generation: str | None = None
    checks: dict[str, bool] = Field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    assets: dict = Field(default_factory=dict)
    record_version: int = Field(ge=1)
    derived: Literal[True] = True
