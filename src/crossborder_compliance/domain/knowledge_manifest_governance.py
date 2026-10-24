"""Optional catalogue proposals; no catalogue field authorizes legal knowledge publication."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.knowledge_management import (
    KnowledgeDocumentLabel,
    ManagementRequest,
)

ManifestField = Literal[
    "sequence",
    "title",
    "language",
    "category",
    "jurisdiction",
    "topic",
    "issuer",
    "format",
    "relative_path",
]


class ManifestMetadataMapping(ManagementRequest):
    dimension: Literal["language", "category", "jurisdiction", "topic", "issuer"]
    source_value: str = Field(min_length=1, max_length=4096)
    labels: tuple[KnowledgeDocumentLabel, ...] = Field(min_length=1, max_length=128)


class PrepareKnowledgeManifest(ManagementRequest):
    upload_session_id: UUID
    expected_record_version: int = Field(ge=1)
    columns: dict[ManifestField, str] = Field(min_length=2, max_length=9)
    required_fields: tuple[ManifestField, ...] = ("title", "relative_path")
    metadata_mappings: tuple[ManifestMetadataMapping, ...] = Field(default=(), max_length=1000)
    sheet_name: str | None = Field(default=None, min_length=1, max_length=128)
    csv_encoding: Literal["utf-8-sig", "utf-8", "utf-16", "gb18030"] = "utf-8-sig"
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def bounded_mapping(self):
        if any(not value.strip() or len(value) > 128 for value in self.columns.values()):
            raise ValueError("INVALID_COLUMN_MAPPING")
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("DUPLICATE_REQUIRED_FIELD")
        identities = [(m.dimension, m.source_value) for m in self.metadata_mappings]
        if sum(len(mapping.labels) for mapping in self.metadata_mappings) > 1000:
            raise ValueError("MANIFEST_METADATA_PIN_LIMIT")
        if len(set(identities)) != len(identities):
            raise ValueError("DUPLICATE_MANIFEST_METADATA_MAPPING")
        return self
