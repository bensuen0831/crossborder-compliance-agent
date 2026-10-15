"""Public management projections; persisted raw configuration is not leaked."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from crossborder_compliance.domain.knowledge_management import (
    KnowledgeDocumentMetadata,
    TaxonomyKind,
)
from crossborder_compliance.domain.localized_metadata import ResolvedDisplayMetadata


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
    query: str
    label_id: UUID | None
    lifecycle: KnowledgeLifecycle | None
    language: str | None


class KnowledgeStatisticsView(Projection):
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
