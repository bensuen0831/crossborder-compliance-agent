"""Typed production upload boundary over the existing document ports."""

import hashlib
import io
import zipfile
from pathlib import PurePath
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from crossborder_compliance.application.document_services import normalize_filename


class DocumentCapabilityError(ValueError):
    pass


class FileTypePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    extension: str = Field(pattern=r"^\.[a-z0-9]+$")
    media_type: str
    signature: Literal["pdf", "docx", "xlsx", "pptx", "text", "png", "jpeg"]


class DocumentFilePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = Field(min_length=1, max_length=80)
    max_size_bytes: int = Field(gt=0, le=100 * 1024 * 1024)
    allowed_types: tuple[FileTypePolicy, ...] = Field(min_length=1, max_length=32)
    scan_required: bool = True
    max_archive_entries: int = Field(default=4096, ge=1, le=10000)
    max_expanded_bytes: int = Field(default=100 * 1024 * 1024, gt=0)

    @property
    def digest(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def validate_content(self, filename: str, claimed_media_type: str, content: bytes):
        safe = normalize_filename(filename)
        if not content or len(content) > self.max_size_bytes:
            raise ValueError("DOCUMENT_SIZE_POLICY_VIOLATION")
        ext = PurePath(safe).suffix.lower()
        choices = [t for t in self.allowed_types if t.extension == ext]
        if len(choices) != 1 or choices[0].media_type != claimed_media_type:
            raise ValueError("DOCUMENT_TYPE_POLICY_VIOLATION")
        kind = choices[0].signature
        valid = False
        if kind == "pdf":
            valid = content.startswith(b"%PDF-")
        elif kind == "png":
            valid = content.startswith(b"\x89PNG\r\n\x1a\n")
        elif kind == "jpeg":
            valid = content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9")
        elif kind == "text":
            try:
                value = content.decode("utf-8-sig")
                valid = "\x00" not in value and all(ord(c) >= 32 or c in "\n\r\t" for c in value)
            except UnicodeError:
                valid = False
        else:
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    entries = z.infolist()
                    marker = {"docx":"word/document.xml", "xlsx":"xl/workbook.xml", "pptx":"ppt/presentation.xml"}[kind]
                    valid = marker in z.namelist() and "[Content_Types].xml" in z.namelist()
                    valid = valid and len(entries) <= self.max_archive_entries
                    valid = valid and sum(e.file_size for e in entries) <= self.max_expanded_bytes
                    valid = valid and all(not e.flag_bits & 1 and not e.filename.startswith("/") and ".." not in PurePath(e.filename).parts for e in entries)
            except (ValueError, zipfile.BadZipFile):
                valid = False
        if not valid:
            raise ValueError("DOCUMENT_CONTENT_TYPE_MISMATCH")
        return safe, choices[0].media_type


class DraftDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


class DocumentInputView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID
    document_version_id: UUID
    document_version: int
    filename: str
    size_bytes: int
    media_type: str
    content_hash: str
    parse_status: Literal["STORED", "ACCEPTED", "RUNNING", "COMPLETED", "FAILED"]
    quality_status: Literal["PASS", "WARNING", "REVIEW_REQUIRED", "FAILED"] | None = None
    parse_run_id: UUID | None = None
    error_code: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)


class DocumentInputsView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    project_version_id: UUID
    intake_version: int
    intake_status: Literal["DRAFT", "CONFIRMED", "SUPERSEDED"]
    items: list[DocumentInputView]


class ProjectDocumentPort(Protocol):
    def list_inputs(self, project_id: UUID, version: int | None = None) -> DocumentInputsView: ...
    def upload(self, project_id: UUID, request: DraftDocumentRequest, *, filename: str, media_type: str, content: bytes, replace_document_id: UUID | None = None): ...
    def parse(self, project_id: UUID, version_id: UUID, request: DraftDocumentRequest): ...
    def unlink(self, project_id: UUID, version_id: UUID, request: DraftDocumentRequest): ...


class ProjectDocumentService:
    def __init__(self, repository: ProjectDocumentPort):
        self.repository = repository

    def list_inputs(self, *args): return self.repository.list_inputs(*args)
    def upload(self, *args, **kwargs): return self.repository.upload(*args, **kwargs)
    def parse(self, *args): return self.repository.parse(*args)
    def unlink(self, *args): return self.repository.unlink(*args)
