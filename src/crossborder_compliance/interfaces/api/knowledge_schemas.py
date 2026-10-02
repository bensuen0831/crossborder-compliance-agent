from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRequestDTO(RequestDTO):
    collection_id: UUID
    code: str = Field(min_length=1, max_length=120)
    source_type: str
    authority_ref: UUID | None = None
    canonical_url: str | None = None
    jurisdiction_refs: list[UUID] = Field(default_factory=list)
    trust_level: str = "APPROVED"
    language: str = Field(min_length=1, max_length=80)
    refresh_policy: dict = Field(default_factory=dict)
    enabled: bool = True
    validation_status: str = "PENDING"
    provenance: dict


class SourceUpdateDTO(RequestDTO):
    expected_record_version: int = Field(ge=1)
    enabled: bool | None = None
    refresh_policy: dict | None = None
    validation_status: str | None = None


class DocumentRequestDTO(RequestDTO):
    source_id: UUID
    display_name: str = Field(min_length=1, max_length=250)


class VersionRequestDTO(RequestDTO):
    collection_version_id: UUID
    language: str = Field(min_length=1, max_length=80)
    effective_from: date | None = None
    effective_to: date | None = None
    provenance: dict


class BindingRequestDTO(RequestDTO):
    scope_type: Literal["PRODUCT_SPECIFIC", "DOMAIN_SHARED", "CROSS_PRODUCT", "GLOBAL"]
    dimensions: dict[str, list[UUID]] = Field(default_factory=dict)
    permission_scopes: list[str] = Field(default_factory=list)
    effective_from: date | None = None
    effective_to: date | None = None
    provenance: dict


class StructureInputDTO(RequestDTO):
    node_type: str
    canonical_locator: str = Field(min_length=1, max_length=500)
    parent_locator: str | None = None
    official_number: str | None = None
    heading: str = ""
    original_text: str = Field(min_length=1, max_length=1_000_000)


class IngestionRequestDTO(RequestDTO):
    idempotency_key: str = Field(min_length=1, max_length=160)
    nodes: list[StructureInputDTO] = Field(default_factory=list, max_length=10000)
    url: str | None = None
    bindings: list[BindingRequestDTO] = Field(default_factory=list, max_length=1000)
    strategy: Literal[
        "STRUCTURE_AWARE", "ARTICLE", "SECTION", "PARAGRAPH", "TABLE", "SLIDING_WINDOW"
    ] = "STRUCTURE_AWARE"

    @model_validator(mode="after")
    def one_input(self):
        if bool(self.nodes) == bool(self.url):
            raise ValueError("exactly one input required")
        return self


class ExpectedVersionDTO(RequestDTO):
    expected_record_version: int = Field(ge=1)


class ScopeRequestDTO(RequestDTO):
    analysis_snapshot_id: UUID | None = None
    effective_as_of: date | None = None
    languages: list[str] = Field(default_factory=list)


class RecordDTO(BaseModel):
    """Public persisted record contract; JSON fields remain explicit domain projections."""

    model_config = ConfigDict(extra="ignore")
    tenant_id: UUID
    record_version: int
    status: str
    created_at: datetime
    updated_at: datetime


class RunDTO(RecordDTO):
    ingestion_run_id: UUID
    knowledge_version_id: UUID
    idempotency_key: str
    request_hash: str
    error_code: str | None = None
    outbox_event_id: UUID


class DocumentDTO(RecordDTO):
    document_id: UUID
    source_id: UUID
    display_name: str


class VersionDTO(RecordDTO):
    knowledge_version_id: UUID
    document_id: UUID
    collection_version_id: UUID
    version: int
    lifecycle: str
    language: str
    content_hash: str | None = None
    original_artifact_ref: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    provenance_json: dict
    review_task_id: UUID | None = None
    approved_by: str | None = None


class StructureDTO(RecordDTO):
    knowledge_version_id: UUID
    structure_node_id: UUID
    regulatory_structure_node_id: UUID | None
    parent_node_id: UUID | None
    node_type: str
    sequence: int
    canonical_locator: str
    official_number: str | None
    heading: str
    original_text: str
    normalized_text: str
    language: str
    effective_date: date | None
    source_trace_json: dict
    provenance_json: dict
    citation_id: UUID


class ChunkDTO(RecordDTO):
    knowledge_version_id: UUID
    chunk_id: UUID
    chunk_type: str
    original_text: str
    normalized_text: str
    token_count: int
    language: str
    sequence: int
    canonical_locator: str
    content_hash: str
    chunking_strategy_version: str
    structure_node_ids: list[UUID]
    citation_refs: list[UUID]
