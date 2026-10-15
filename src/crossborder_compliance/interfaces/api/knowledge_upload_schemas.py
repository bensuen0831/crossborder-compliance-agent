"""Safe upload projections; no storage keys, credential or multipart identity."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from crossborder_compliance.domain.knowledge_management import ManagementRequest
from crossborder_compliance.domain.knowledge_upload import KnowledgeBinaryFormat


class KnowledgeScannerView(ManagementRequest):
    clean: bool
    engine: str = Field(max_length=80)
    database_identity: str = Field(max_length=250)
    image_id: str = Field(max_length=80)


class KnowledgeScanView(ManagementRequest):
    byte_size: int | None = None
    content_sha256: str | None = None
    detected_format: KnowledgeBinaryFormat | None = None
    scanner: KnowledgeScannerView | None = None


class KnowledgeReceivedPart(ManagementRequest):
    part_number: int
    byte_size: int
    content_sha256: str


class KnowledgeUploadView(ManagementRequest):
    upload_session_id: UUID
    knowledge_version_id: UUID | None
    relative_path: str
    declared_format: KnowledgeBinaryFormat
    declared_bytes: int
    content_sha256: str
    part_bytes: int
    part_count: int
    status: Literal[
        "CREATING",
        "UPLOADING",
        "FINALIZING",
        "QUEUED_SCAN",
        "SCANNING",
        "VERIFIED",
        "QUARANTINED",
        "FAILED",
        "CANCELLING",
        "CANCELLED",
        "EXPIRED",
    ]
    record_version: int
    expires_at: datetime
    created_by: str
    attempts: int
    error_code: str | None
    scan: KnowledgeScanView
    receipt_id: UUID | None = None
    operation: str | None = None
    received_parts: list[KnowledgeReceivedPart] | None = None
    received_bytes: int | None = None


class KnowledgeSignedPart(ManagementRequest):
    # Ephemeral signed URLs are deliberately never stored in evidence or audit receipts.
    url: str
    headers: dict[str, str]
    byte_size: int
