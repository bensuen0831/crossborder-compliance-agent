from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DataGroupSpecDTO(BaseModel):
    name: str
    candidate_ids: list[UUID] = Field(default_factory=list)
    grouping_reason: str = "LOGICAL_CONTEXT_GROUP"


class ContextResolutionRunRequestDTO(BaseModel):
    selected_product_scope: list[UUID] = Field(default_factory=list)
    detected_product_scope: list[UUID] = Field(default_factory=list)
    selected_scenarios: list[UUID] = Field(default_factory=list)
    detected_scenarios: list[UUID] = Field(default_factory=list)
    systems: list[dict[str, Any]] = Field(default_factory=list)
    devices: list[dict[str, Any]] = Field(default_factory=list)
    parties: list[dict[str, Any]] = Field(default_factory=list)
    jurisdictions: list[dict[str, Any]] = Field(default_factory=list)
    data_item_product_bindings: dict[str, list[str]] = Field(default_factory=dict)
    data_item_flow_bindings: dict[str, list[str]] = Field(default_factory=dict)
    data_groups: list[DataGroupSpecDTO] = Field(default_factory=list)
    workflow_run_id: UUID | None = None


class ContextResolutionRunResponseDTO(BaseModel):
    context_resolution_run_id: UUID
    project_id: UUID
    version: int
    statistics: dict[str, int]
    review_task_ids: list[UUID]
    confidence: float


class ContextConflictResolveRequestDTO(BaseModel):
    resolution: dict[str, Any]
    resolved_by: str
    expected_record_version: int = Field(ge=1)


class ContextConflictDTO(BaseModel):
    conflict_id: UUID
    project_id: UUID
    conflict_type: str
    object_type: str
    object_ids: list[UUID]
    reason_code: str
    details: dict[str, Any]
    source_trace_ids: list[UUID]
    confidence: float
    resolution_status: str
    review_required: bool
    record_version: int


class ContextResolutionSummaryDTO(BaseModel):
    context_resolution_run_id: UUID
    project_id: UUID
    business_fact_summary: dict[str, Any]
    data_inventory_summary: dict[str, Any]
    data_flow_summary: dict[str, Any]
    unresolved_items: list[str]
    statistics: dict[str, int]
    confidence: float
    version: int
