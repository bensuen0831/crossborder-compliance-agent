"""Canonical knowledge contracts; indexes and registry projections are derived."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DIMENSIONS = (
    "jurisdiction",
    "jurisdiction_group",
    "product_domain",
    "product_category",
    "product_family",
    "product",
    "product_tag",
    "scenario",
    "industry",
    "data_category",
)
PRODUCT_DIMENSIONS = (
    "product_domain",
    "product_category",
    "product_family",
    "product",
    "product_tag",
)
LIFECYCLES = (
    "DRAFT",
    "INGESTED",
    "VALIDATED",
    "PENDING_REVIEW",
    "APPROVED",
    "ACTIVE",
    "SUPERSEDED",
    "EXPIRED",
    "ARCHIVED",
)
SOURCE_TYPES = (
    "OFFICIAL_REGULATOR",
    "OFFICIAL_LEGISLATION",
    "APPROVED_INTERNAL",
    "ENTERPRISE_POLICY",
    "APPROVED_RESEARCH",
    "USER_APPROVED_REFERENCE",
    "CONTROLLED_EXTERNAL_SOURCE",
)
SCOPE_TYPES = ("PRODUCT_SPECIFIC", "DOMAIN_SHARED", "CROSS_PRODUCT", "GLOBAL")
NODE_TYPES = (
    "ACT",
    "REGULATION",
    "PART",
    "CHAPTER",
    "SECTION",
    "ARTICLE",
    "PARAGRAPH",
    "ANNEX",
    "SCHEDULE",
    "GUIDANCE_SECTION",
    "OTHER",
    "TABLE",
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeSource(Contract):
    source_id: str
    tenant_id: str
    collection_id: str
    code: str
    source_type: str
    authority_ref: str | None = None
    canonical_url: str | None = None
    jurisdiction_refs: tuple[str, ...] = ()
    trust_level: str
    language: str
    refresh_policy: dict = Field(default_factory=dict)
    enabled: bool = True
    validation_status: str = "PENDING"
    source_hash: str
    provenance: dict
    record_version: int = 1

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_type not in SOURCE_TYPES or not self.provenance:
            raise ValueError("invalid source or missing provenance")
        return self


class KnowledgeDocument(Contract):
    document_id: str
    source_id: str
    display_name: str


class KnowledgeDocumentVersion(Contract):
    knowledge_version_id: str
    document_id: str
    collection_version_id: str
    version: int
    lifecycle: str
    language: str
    effective_from: date | None = None
    effective_to: date | None = None
    content_hash: str | None = None
    original_artifact_ref: str | None = None
    provenance: dict
    record_version: int


class KnowledgeStructureNode(Contract):
    structure_node_id: str
    knowledge_version_id: str
    node_type: str
    parent_node_id: str | None = None
    sequence: int
    canonical_locator: str
    official_number: str | None = None
    heading: str = ""
    original_text: str
    normalized_text: str
    language: str
    effective_date: date | None = None
    source_trace: dict
    provenance: dict
    citation_id: str

    @model_validator(mode="after")
    def validate_structure(self):
        if (
            self.node_type not in NODE_TYPES
            or not self.original_text.strip()
            or not self.canonical_locator
        ):
            raise ValueError("invalid canonical structure")
        return self


class RegulatoryStructureNode(KnowledgeStructureNode):
    jurisdiction_id: str


class KnowledgeChunk(Contract):
    chunk_id: str
    knowledge_version_id: str
    structure_node_ids: tuple[str, ...]
    chunk_type: str
    original_text: str
    normalized_text: str
    token_count: int
    language: str
    sequence: int
    canonical_locator: str
    citation_refs: tuple[str, ...]
    content_hash: str
    chunking_strategy_version: str


class KnowledgeBinding(Contract):
    binding_id: str
    tenant_id: str
    knowledge_version_id: str
    scope_type: str
    dimensions: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    permission_scopes: tuple[str, ...] = ()
    effective_from: date | None = None
    effective_to: date | None = None
    provenance: dict
    review_status: str = "PENDING"
    version: int = 1

    @model_validator(mode="after")
    def validate_binding(self):
        product = any(self.dimensions.get(d) for d in PRODUCT_DIMENSIONS)
        if (
            self.scope_type not in SCOPE_TYPES
            or set(self.dimensions) - set(DIMENSIONS)
            or not self.provenance
        ):
            raise ValueError("invalid binding")
        if (
            any(not v for v in self.dimensions.values())
            or (self.scope_type == "GLOBAL" and product)
            or (self.scope_type != "GLOBAL" and not product)
        ):
            raise ValueError("binding must have bounded scope")
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValueError("invalid binding dates")
        return self


class KnowledgeQualityResult(Contract):
    knowledge_version_id: str
    status: Literal["PASS", "WARNING", "REVIEW_REQUIRED", "FAILED"]
    checks: dict[str, bool]
    reason_codes: tuple[str, ...]


class KnowledgeIngestionRun(Contract):
    ingestion_run_id: str
    knowledge_version_id: str
    idempotency_key: str
    status: str
    error_code: str | None = None


class KnowledgeTranslation(Contract):
    translation_id: str
    knowledge_version_id: str
    source_language: str
    target_language: str
    translated_text_ref: str
    translation_method: Literal["AI", "HUMAN", "OFFICIAL"]
    model_config_id: str | None = None
    reviewer: str | None = None
    review_status: str = "PENDING"
    provenance: dict
    version: int = 1


class KnowledgeIndexVersion(Contract):
    index_version_id: str
    knowledge_version_ids: tuple[str, ...]
    chunking_strategy_version: str
    embedding_config_id: str | None = None
    fts_config_version: str
    build_status: str
    built_at: datetime
    content_hash: str
    derived: bool = True


class EmbeddingRecord(Contract):
    embedding_record_id: str
    chunk_id: str
    model_config_id: str
    embedding_dimension: int
    embedding_version: str
    vector_hash: str
    generated_at: datetime
    status: str


class EmbeddingJob(Contract):
    embedding_job_id: str
    knowledge_version_id: str
    model_config_id: str
    status: str


class KnowledgeChangeEvent(Contract):
    event_id: str
    knowledge_version_id: str
    event_type: str
    provenance: dict


class KnowledgeVersionDiff(Contract):
    diff_id: str
    old_version_id: str
    new_version_id: str
    changes: dict


class FormalContext(Contract):
    project_id: str
    subject_type: Literal["PROJECT", "DATA_ITEM", "DATA_FLOW"]
    subject_id: str
    context_version: int
    dimensions: dict[str, tuple[str, ...]]
    product_unresolved: bool
    reason_codes: tuple[str, ...] = ()
    system_ids: tuple[str, ...] = ()
    party_ids: tuple[str, ...] = ()


class KnowledgeFilterSpec(Contract):
    tenant_filter: str
    permission_filter: tuple[str, ...]
    lifecycle_filter: tuple[str, ...]
    effective_date_filter: date
    jurisdiction_filter: tuple[str, ...]
    product_filter: dict[str, tuple[str, ...]]
    scenario_filter: tuple[str, ...]
    industry_filter: tuple[str, ...]
    data_category_filter: tuple[str, ...]
    language_filter: tuple[str, ...]
    scope_type_filter: tuple[str, ...]
    version_filter: tuple[str, ...]
    binding_filter: tuple[str, ...]
    filter_order: tuple[str, ...] = (
        "tenant",
        "permission",
        "lifecycle",
        "version",
        "effective_date",
        "product",
        "jurisdiction",
        "scenario",
        "industry",
        "data_category",
        "language",
    )


class KnowledgeScope(Contract):
    tenant_id: str
    project_id: str
    analysis_snapshot_id: str | None = None
    subject_type: str
    subject_id: str
    allowed_jurisdiction_ids: tuple[str, ...] = ()
    allowed_product_domain_ids: tuple[str, ...] = ()
    allowed_product_category_ids: tuple[str, ...] = ()
    allowed_product_family_ids: tuple[str, ...] = ()
    allowed_product_ids: tuple[str, ...] = ()
    allowed_product_tag_ids: tuple[str, ...] = ()
    allowed_scenario_ids: tuple[str, ...] = ()
    allowed_industry_refs: tuple[str, ...] = ()
    allowed_data_category_refs: tuple[str, ...] = ()
    allowed_scope_types: tuple[str, ...]
    permission_filters: tuple[str, ...]
    lifecycle_filters: tuple[str, ...]
    effective_as_of: date
    excluded_bindings: tuple[dict, ...]
    unresolved_scopes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    review_required: bool
    version: int
    filter_spec: KnowledgeFilterSpec


class KnowledgeScopeResolution(Contract):
    resolution_id: str
    scope: KnowledgeScope
    formal_context: FormalContext
