"""Transport-neutral import progress, without credentials or provider payloads."""

from typing import Literal
from uuid import UUID

from crossborder_compliance.domain.knowledge_management import ManagementRequest


class KnowledgeBatchItemView(ManagementRequest):
    attempts: int
    technical_retry_available: bool
    item_id: UUID
    upload_session_id: UUID
    relative_path: str
    knowledge_version_id: UUID | None
    status: Literal["UNMAPPED", "READY", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"]
    record_version: int
    error_code: str | None


class KnowledgeBatchView(ManagementRequest):
    batch_id: UUID
    archive_upload_session_id: UUID | None
    created_by: str
    status: Literal[
        "PENDING",
        "EXTRACTING",
        "PREVIEW",
        "CONFIRMED",
        "PROCESSING",
        "COMPLETED",
        "PARTIAL_FAILURE",
        "FAILED",
        "CANCELLING",
        "CANCELLED",
    ]
    record_version: int
    manifest_digest: str | None
    attempts: int
    error_code: str | None
    receipt_id: UUID | None = None
    operation: str | None = None
    counts: dict[str, int] | None = None
    total: int | None = None
    page: int | None = None
    page_size: int | None = None
    items: list[KnowledgeBatchItemView] | None = None


class KnowledgeBatchFailure(ManagementRequest):
    item_id: UUID
    relative_path: str
    status: Literal["FAILED"]
    error_code: str | None
    record_version: int
    attempts: int
    technical_retry_available: bool


class KnowledgeBatchFailurePage(ManagementRequest):
    batch_id: UUID
    total: int
    page: int
    page_size: int
    items: list[KnowledgeBatchFailure]
