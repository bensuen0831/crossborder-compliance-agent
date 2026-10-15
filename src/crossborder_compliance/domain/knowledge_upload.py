"""Technical binary transport contracts, separate from knowledge publication."""

import re
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from crossborder_compliance.domain.knowledge_management import ManagementRequest
from crossborder_compliance.domain.knowledge_paths import safe_relative_path

KnowledgeBinaryFormat = Literal["DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML", "RAR", "ZIP"]
DOCUMENT_FORMATS = frozenset({"DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML"})
ARCHIVE_FORMATS = frozenset({"RAR", "ZIP"})
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class StartKnowledgeUpload(ManagementRequest):
    knowledge_version_id: UUID | None = None
    expected_record_version: int | None = Field(default=None, ge=1)
    relative_path: str = Field(min_length=1, max_length=1024)
    declared_format: KnowledgeBinaryFormat
    declared_bytes: int = Field(gt=0, le=5 * 1024**4)
    content_sha256: str
    idempotency_key: str = Field(min_length=1, max_length=128)

    _path = field_validator("relative_path")(safe_relative_path)

    @field_validator("content_sha256")
    @classmethod
    def valid_digest(cls, value):
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("INVALID_CONTENT_SHA256")
        return value

    @model_validator(mode="after")
    def target_contract(self):
        if (self.knowledge_version_id is None) != (self.expected_record_version is None):
            raise ValueError("KNOWLEDGE_UPLOAD_TARGET_CAS_REQUIRED")
        if self.declared_format in ARCHIVE_FORMATS and self.knowledge_version_id is not None:
            raise ValueError("ARCHIVE_IS_NOT_A_KNOWLEDGE_DOCUMENT_VERSION")
        suffix = PurePosixPath(self.relative_path).suffix.lower()
        if suffix != "." + self.declared_format.lower():
            raise ValueError("KNOWLEDGE_FILENAME_FORMAT_MISMATCH")
        return self


class KnowledgeUploadMutation(ManagementRequest):
    expected_record_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


class KnowledgeUploadPartRequest(ManagementRequest):
    part_number: int = Field(ge=1, le=10000)
    content_sha256: str

    _digest = field_validator("content_sha256")(StartKnowledgeUpload.valid_digest.__func__)


class KnowledgeUploadPartReceipt(KnowledgeUploadMutation, KnowledgeUploadPartRequest):
    pass


class AttachKnowledgeUpload(ManagementRequest):
    knowledge_version_id: UUID
    expected_record_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


class VerifiedKnowledgeBinary(ManagementRequest):
    storage_ref: str
    object_version: str
    content_sha256: str
    byte_size: int = Field(gt=0)
    detected_format: KnowledgeBinaryFormat


class KnowledgeUploadPolicy(ManagementRequest):
    """Bounded deployment limits supplement the governed management policy."""

    tenant_storage_quota_bytes: int = Field(default=100 * 1024**3, gt=0)
    max_active_sessions: int = Field(default=64, ge=1, le=10000)
    signed_part_expiry_seconds: int = Field(default=900, ge=60, le=3600)
    scanner_timeout_seconds: int = Field(default=3600, ge=1, le=14400)
    verification_chunk_bytes: int = Field(default=8 * 1024**2, ge=65536, le=32 * 1024**2)
