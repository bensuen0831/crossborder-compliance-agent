"""Safe, paged catalogue proposals; transport internals and credentials remain private."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from crossborder_compliance.domain.knowledge_management import (
    KnowledgeDocumentLabel,
    ManagementRequest,
)


class KnowledgeManifestView(ManagementRequest):
    manifest_id: UUID
    batch_id: UUID
    upload_session_id: UUID
    inventory_digest: str
    content_sha256: str
    status: Literal["COMPLETED", "FAILED"]
    error_code: str | None
    record_count: int
    created_by: str
    created_at: datetime
    proposal_only: Literal[True] = True
    receipt_id: UUID | None = None
    operation: str | None = None


class KnowledgeManifestIssue(ManagementRequest):
    row: int
    field: str
    code: str


class KnowledgeManifestRecordView(ManagementRequest):
    manifest_record_id: UUID
    row_number: int
    canonical_path: str | None
    matched_item_id: UUID | None
    status: Literal["MAPPING_REQUIRED", "FILE_MATCHED", "FILE_MISSING"]
    proposed_values: dict[str, str]
    metadata_refs: dict[str, list[KnowledgeDocumentLabel]]
    issues: list[KnowledgeManifestIssue]


class KnowledgeManifestPage(ManagementRequest):
    total: int
    page: int
    page_size: int
    items: list[KnowledgeManifestView]


class KnowledgeManifestDetail(KnowledgeManifestView):
    total: int
    page: int
    page_size: int
    items: list[KnowledgeManifestRecordView]


class UnlistedKnowledgeFile(ManagementRequest):
    item_id: UUID
    relative_path: str


class KnowledgeManifestMissingFiles(ManagementRequest):
    manifest_id: UUID
    total: int
    page: int
    page_size: int
    items: list[KnowledgeManifestRecordView]
    unlisted_total: int
    unlisted_files: list[UnlistedKnowledgeFile]
