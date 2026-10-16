"""Bounded import work commands. Metadata mapping never publishes legal knowledge."""

from uuid import UUID

from pydantic import Field, field_validator, model_validator

from crossborder_compliance.domain.knowledge_management import (
    CreateManagedKnowledgeDocument,
    ManagementRequest,
)
from crossborder_compliance.domain.knowledge_upload import KnowledgeUploadMutation


class CreateKnowledgeImportBatch(ManagementRequest):
    archive_upload_session_id: UUID | None = None
    upload_session_ids: tuple[UUID, ...] = Field(default=(), max_length=20000)
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def exact_source(self):
        if bool(self.archive_upload_session_id) == bool(self.upload_session_ids):
            raise ValueError("EXACTLY_ONE_BATCH_SOURCE_REQUIRED")
        if len(set(self.upload_session_ids)) != len(self.upload_session_ids):
            raise ValueError("DUPLICATE_BATCH_UPLOAD")
        return self


class KnowledgeBatchMapping(ManagementRequest):
    item_id: UUID
    document: CreateManagedKnowledgeDocument
    manifest_record_id: UUID | None = None


class ConfirmKnowledgeBatchItems(KnowledgeUploadMutation):
    mappings: tuple[KnowledgeBatchMapping, ...] = Field(min_length=1, max_length=100)

    @field_validator("mappings")
    @classmethod
    def unique_items(cls, values):
        if len({item.item_id for item in values}) != len(values):
            raise ValueError("DUPLICATE_BATCH_MAPPING")
        return values


class RetryKnowledgeBatchItem(KnowledgeUploadMutation):
    expected_item_record_version: int = Field(ge=1)
