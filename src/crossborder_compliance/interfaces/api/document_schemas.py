from __future__ import annotations
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

class ParseRequestDTO(BaseModel):
    idempotency_key: str = Field(min_length=1,max_length=255)
    parser_profile_id: str = "default"

class TaskAcceptedDTO(BaseModel):
    task_id: UUID
    status: str

class DocumentVersionResponseDTO(BaseModel):
    document_id: UUID
    document_version_id: UUID
    version_no: int
    filename: str
    mime_type: str
    size_bytes: int
    content_hash: str
    storage_ref: str

class ParseRunResponseDTO(BaseModel):
    parse_run_id: UUID
    document_version_id: UUID
    parse_run_version: int
    parser_profile_id: str
    parser_name: str
    parser_version: str
    status: str
    native_parse_used: bool
    ocr_used: bool
    vision_used: bool
    page_count: int
    table_count: int
    image_count: int
    warning_count: int
    quality_score: float | None = None
    error_code: str | None = None
    language: str | None = None

class StructureNodeResponseDTO(BaseModel):
    structure_node_id: UUID
    node_type: str
    parent_node_id: UUID | None = None
    sequence: int
    page_no: int | None = None
    sheet_name: str | None = None
    slide_no: int | None = None
    section_path: str | None = None
    bbox: list[float] | None = None
    original_text: str | None = None
    normalized_text: str | None = None
    language: str | None = None
    source_locator: dict[str, Any] = Field(default_factory=dict)
    parser_confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class DocumentAnalysisSummaryDTO(BaseModel):
    document_count:int
    document_version_count:int
    page_count:int
    sheet_count:int
    slide_count:int
    table_count:int
    raw_field_count:int
    normalized_candidate_data_item_count:int
    candidate_data_flow_count:int
    diagram_count:int
    unresolved_fact_count:int
    conflict_count:int
    review_required_count:int
    parsing_warning_count:int
