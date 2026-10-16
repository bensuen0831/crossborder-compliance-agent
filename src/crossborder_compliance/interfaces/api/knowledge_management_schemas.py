"""Public management projections; persisted raw configuration is not leaked."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from crossborder_compliance.domain.knowledge import KnowledgeBinding, KnowledgeQualityResult
from crossborder_compliance.domain.knowledge_management import (
    KnowledgeDocumentMetadata,
    TaxonomyKind,
)
from crossborder_compliance.domain.localized_metadata import ResolvedDisplayMetadata
from crossborder_compliance.domain.retrieval import KnowledgeRuntimeReadinessResult


class Projection(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxonomyVersionView(Projection):
    version_id: UUID
    definition_id: UUID
    version_no: int
    lifecycle_status: str
    record_version: int
    payload: dict
    created_by: str
    approved_by: str | None


class TaxonomyView(Projection):
    definition_id: UUID
    canonical_object_id: UUID | None
    kind: TaxonomyKind
    code: str
    display_name: str
    display: ResolvedDisplayMetadata
    record_version: int
    active_version_id: UUID | None
    version_id: UUID | None
    lifecycle: str
    enabled: bool
    payload: dict
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None


class TaxonomyPage(Projection):
    total: int
    page: int
    page_size: int
    items: list[TaxonomyView]


class TaxonomyTreeNode(Projection):
    definition_id: UUID
    version_id: UUID
    parent_definition_id: UUID | None
    kind: TaxonomyKind
    code: str
    display_name: str
    child_count: int


class TaxonomyTreePage(Projection):
    parent_definition_id: UUID | None
    total: int
    page: int
    page_size: int
    items: list[TaxonomyTreeNode]


class TaxonomyAliases(Projection):
    source_definition_id: UUID
    display_only: bool
    historical_rebinding: bool
    targets: list[TaxonomyView]


class TaxonomyDetail(TaxonomyView):
    versions: list[TaxonomyVersionView]


class TaxonomyImpact(Projection):
    definition_id: UUID
    references: dict[str, int]
    protected_version_history: bool
    eligible_draft: bool


class TaxonomyMutationResult(Projection):
    definition_id: UUID
    receipt_id: UUID
    operation: str
    version_id: UUID | None = None
    version_no: int | None = None
    lifecycle_status: str | None = None
    record_version: int | None = None
    payload: dict | None = None
    created_by: str | None = None
    approved_by: str | None = None
    canonical_object_id: UUID | None = None
    deleted: bool = False
    impact: TaxonomyImpact | None = None
    effect: str | None = None


class KnowledgeHoldView(Projection):
    hold_id: UUID
    resource_type: str
    resource_id: UUID
    reason: str
    created_by: str
    created_at: datetime
    released_by: str | None
    released_at: datetime | None
    record_version: int


class KnowledgeHoldMutation(KnowledgeHoldView):
    receipt_id: UUID
    operation: str


class KnowledgeAuditItem(Projection):
    receipt_id: UUID
    operation: str
    reason: str
    actor_id: str
    created_at: datetime
    resource_id: UUID
    resource_kind: str


class KnowledgeAuditPage(Projection):
    total: int
    page: int
    page_size: int
    items: list[KnowledgeAuditItem]


class ManagedKnowledgeVersionView(Projection):
    knowledge_version_id: UUID
    document_id: UUID
    version: int
    record_version: int
    lifecycle: str
    language: str
    effective_from: date | None
    effective_to: date | None
    metadata: KnowledgeDocumentMetadata
    content_hash: str | None
    file_available: bool
    binary_upload_session_id: UUID | None = None


class KnowledgeScopeOption(Projection):
    object_id: UUID
    display_name: str
    code: str


class KnowledgeScopeOptions(Projection):
    dimension: str
    total: int
    page: int
    page_size: int
    items: list[KnowledgeScopeOption]


class ManagedKnowledgeBindings(Projection):
    knowledge_version_id: UUID
    bindings: list[KnowledgeBinding]
    quality: KnowledgeQualityResult | None = None
    runtime_readiness: KnowledgeRuntimeReadinessResult | None = None


class ManagedKnowledgeBindingMutation(Projection):
    knowledge_version_id: UUID
    record_version: int
    binding: KnowledgeBinding
    receipt_id: UUID
    operation: str


class ManagedKnowledgeDocumentView(Projection):
    document_id: UUID
    source_id: UUID
    display_name: str
    record_version: int
    status: str
    created_at: datetime
    updated_at: datetime


class ManagedKnowledgeDocumentDetail(ManagedKnowledgeDocumentView):
    versions: list[ManagedKnowledgeVersionView]


class ManagedKnowledgeDocumentPage(Projection):
    total: int
    page: int
    page_size: int
    items: list[ManagedKnowledgeDocumentView]


class ManagedKnowledgeDocumentImpact(Projection):
    document_id: UUID
    references: dict[str, int]
    protected_version_history: bool
    eligible_draft: bool


class ManagedKnowledgeVersionMutation(ManagedKnowledgeVersionView):
    receipt_id: UUID
    operation: str


class ManagedKnowledgeDocumentDeletion(Projection):
    document_id: UUID
    deleted: bool
    impact: ManagedKnowledgeDocumentImpact
    receipt_id: UUID
    operation: str


KnowledgeLifecycle = Literal[
    "DRAFT",
    "INGESTED",
    "VALIDATED",
    "PENDING_REVIEW",
    "APPROVED",
    "ACTIVE",
    "SUPERSEDED",
    "EXPIRED",
    "ARCHIVED",
]


class KnowledgeStatisticsGroup(Projection):
    key: str
    documents: int


class KnowledgeClassificationCount(Projection):
    kind: str
    definition_id: UUID
    code: str
    documents: int


class KnowledgeStatisticsScope(Projection):
    label_ids: list[UUID] = []
    query: str
    label_id: UUID | None
    lifecycle: KnowledgeLifecycle | None
    language: str | None


class KnowledgeImportInventory(Projection):
    scope: Literal["TENANT_OPERATIONAL_UNFILTERED"]
    manifest_records: int
    missing_manifest_files: int
    verified_uploads: int
    verified_upload_bytes: int


class KnowledgeCrossTabCell(Projection):
    jurisdiction_id: UUID
    jurisdiction_code: str
    value: str
    documents: int


class KnowledgeCrossTabView(Projection):
    as_of: datetime
    dimension: Literal["category", "topic", "language", "format", "status", "source"]
    total: int
    page: int
    page_size: int
    items: list[KnowledgeCrossTabCell]
    scope: KnowledgeStatisticsScope
    missing_dimension_values_excluded: Literal[True]
    group_totals_are_not_global_totals: Literal[True]


class KnowledgeStatisticsView(Projection):
    version_lifecycle_counts: dict[str, int]
    import_inventory: KnowledgeImportInventory | None
    by_format: list[KnowledgeStatisticsGroup]
    as_of: datetime
    documents: int
    versions: int
    attached_originals: int
    attached_bytes: int
    parse_status: dict[str, int]
    by_lifecycle: list[KnowledgeStatisticsGroup]
    by_language: list[KnowledgeStatisticsGroup]
    by_classification: list[KnowledgeClassificationCount]
    classification_groups_truncated: bool
    representative_version: Literal["ACTIVE_ELSE_LATEST_MATCHING_LIST"]
    many_to_many_group_totals_are_not_global_totals: Literal[True]
    scope: KnowledgeStatisticsScope


class KnowledgeManagementCapabilities(Projection):
    operations: list[str]
    publication_requires_independent_review: Literal[True] = True


class KnowledgePreviewNode(Projection):
    structure_node_id: UUID
    parent_node_id: UUID | None
    node_type: str
    sequence: int
    canonical_locator: str
    official_number: str | None
    heading: str
    original_excerpt: str
    normalized_excerpt: str
    excerpt_truncated: bool
    language: str
    citation_id: UUID


class KnowledgeDocumentPreview(Projection):
    knowledge_version_id: UUID
    total: int
    page: int
    page_size: int
    items: list[KnowledgePreviewNode]


class TranslationAlignmentPairView(Projection):
    source_node_id: UUID
    target_node_id: UUID
    source_citation_id: UUID
    target_citation_id: UUID
    source_locator: str
    target_locator: str
    source_text_sha256: str
    target_text_sha256: str


class TranslationAlignmentView(Projection):
    translation_id: UUID
    source_version_id: UUID
    target_version_id: UUID
    source_language: str
    target_language: str
    source_content_hash: str
    target_content_hash: str
    pairs: list[TranslationAlignmentPairView]
    translation_method: Literal["HUMAN"]
    review_status: Literal["PENDING", "APPROVED", "REJECTED"]
    record_version: int
    submitted_by: str
    submitted_at: datetime
    reviewer: str | None
    reviewed_at: datetime | None
    reason: str
    review_reason: str | None
    official_evidence: Literal[False]


class TranslationAlignmentPage(Projection):
    total: int
    page: int
    page_size: int
    items: list[TranslationAlignmentView]


class KnowledgeSourceOption(Projection):
    source_id: UUID
    code: str
    source_type: str
    collection_id: UUID
    collection_name: str


class KnowledgeSourceOptionPage(Projection):
    total: int
    page: int
    page_size: int
    items: list[KnowledgeSourceOption]


class KnowledgeCollectionVersionOption(Projection):
    collection_version_id: UUID
    collection_id: UUID
    version_no: int
    display_name: str


class KnowledgeCollectionVersionOptions(Projection):
    items: list[KnowledgeCollectionVersionOption]
