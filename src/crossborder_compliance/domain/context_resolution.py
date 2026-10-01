from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ResolutionAction(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    MERGED = "MERGED"
    SPLIT = "SPLIT"
    CONFLICT = "CONFLICT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ContextValidationStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class DedupDecision(StrEnum):
    SAME_ITEM = "SAME_ITEM"
    POSSIBLE_SAME = "POSSIBLE_SAME"
    DIFFERENT = "DIFFERENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class LocationPrecision(StrEnum):
    EXACT_CANONICAL = "EXACT_CANONICAL"
    REGION = "REGION"
    COUNTRY = "COUNTRY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class BusinessFact:
    fact_id: UUID
    project_id: UUID
    fact_type: str
    normalized_value: Any
    original_values: tuple[Any, ...]
    source_trace_ids: tuple[UUID, ...]
    source_document_ids: tuple[UUID, ...]
    resolution_method: str
    confidence: float
    validation_status: ContextValidationStatus
    conflict_status: str
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class BusinessFactResolution:
    resolution_id: UUID
    candidate_fact_id: UUID
    business_fact_id: UUID | None
    action: ResolutionAction
    confidence: float
    reason_code: str
    source_trace_ids: tuple[UUID, ...]
    reviewer_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class BusinessFactConflict:
    conflict_id: UUID
    project_id: UUID
    fact_type: str
    conflicting_fact_ids: tuple[UUID, ...]
    source_trace_ids: tuple[UUID, ...]
    confidence: float
    resolution_status: str
    review_required: bool


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    resolution_id: UUID
    candidate_type: str
    candidate_id: UUID
    formal_object_type: str
    formal_object_id: UUID | None
    action: ResolutionAction
    confidence: float
    resolution_reason_code: str
    source_trace_ids: tuple[UUID, ...]
    reviewer_required: bool
    resolved_at: datetime | None
    resolved_by_type: str
    version: int


@dataclass(frozen=True, slots=True)
class ProductContextCandidate:
    product_context_candidate_id: UUID
    project_id: UUID
    dimension_type: str
    definition_id: UUID
    source: str
    confidence: float
    source_trace_ids: tuple[UUID, ...]
    version: int


@dataclass(frozen=True, slots=True)
class ProductContext:
    product_context_id: UUID
    project_id: UUID
    product_domain_ids: tuple[UUID, ...] = ()
    product_category_ids: tuple[UUID, ...] = ()
    product_family_ids: tuple[UUID, ...] = ()
    product_ids: tuple[UUID, ...] = ()
    product_tag_ids: tuple[UUID, ...] = ()
    source: str = "GENERIC"
    confidence: float = 0.0
    evidence_ids: tuple[UUID, ...] = ()
    source_trace_ids: tuple[UUID, ...] = ()
    effective_scope: tuple[UUID, ...] = ()
    resolution_status: str = "PENDING"
    review_required: bool = False
    version: int = 1


@dataclass(frozen=True, slots=True)
class ProductScopeResolution:
    product_scope_resolution_id: UUID
    project_id: UUID
    selected_product_scope: tuple[UUID, ...]
    detected_product_context: tuple[UUID, ...]
    effective_product_scope: tuple[UUID, ...]
    conflict_id: UUID | None
    resolution_status: str
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class ScenarioContext:
    scenario_context_id: UUID
    project_id: UUID
    scenario_definition_id: UUID | None
    source: str
    confidence: float
    source_trace_ids: tuple[UUID, ...]
    validation_status: ContextValidationStatus
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class ScenarioResolution:
    scenario_resolution_id: UUID
    project_id: UUID
    scenario_definition_id: UUID
    action: ResolutionAction
    source: str
    confidence: float
    source_trace_ids: tuple[UUID, ...]
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class SystemContext:
    system_id: UUID
    project_id: UUID
    display_name: str
    system_type_ref: UUID | None
    product_context_refs: tuple[UUID, ...]
    party_refs: tuple[UUID, ...]
    location_refs: tuple[UUID, ...]
    source_trace_ids: tuple[UUID, ...]
    confidence: float
    validation_status: ContextValidationStatus
    version: int


@dataclass(frozen=True, slots=True)
class DeviceContext:
    device_id: UUID
    project_id: UUID
    display_name: str
    device_type_ref: UUID | None
    system_id: UUID | None
    product_context_refs: tuple[UUID, ...]
    source_trace_ids: tuple[UUID, ...]
    confidence: float
    validation_status: ContextValidationStatus
    version: int


@dataclass(frozen=True, slots=True)
class PartyCandidate:
    party_candidate_id: UUID
    project_id: UUID
    display_name: str
    role_definition_id: UUID | None
    source_trace_ids: tuple[UUID, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class PartyResolution:
    party_resolution_id: UUID
    party_candidate_id: UUID
    project_party_id: UUID | None
    legal_entity_id: UUID | None
    action: ResolutionAction
    confidence: float
    reason_code: str
    source_trace_ids: tuple[UUID, ...]
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class DataItemResolutionDetail:
    data_item_id: UUID
    display_name: str
    value_type: str | None
    format: str | None
    unit: str | None
    frequency_quantity_metadata: dict[str, Any]
    system_ids: tuple[UUID, ...]
    device_ids: tuple[UUID, ...]
    source_trace_ids: tuple[UUID, ...]
    raw_candidate_ids: tuple[UUID, ...]
    confidence: float
    validation_status: ContextValidationStatus
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class DataItemDeduplicationResult:
    deduplication_result_id: UUID
    project_id: UUID
    left_candidate_id: UUID
    right_candidate_id: UUID
    decision: DedupDecision
    deterministic_score: float
    semantic_candidate_score: float | None
    reason_code: str
    reviewer_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class DataFlowNodeContext:
    flow_node_id: UUID
    system_id: UUID | None
    party_id: UUID | None
    jurisdiction_context_id: UUID | None
    storage_or_processing_role: str | None
    source_trace_ids: tuple[UUID, ...]
    confidence: float
    validation_status: ContextValidationStatus
    version: int


@dataclass(frozen=True, slots=True)
class DataFlowEdgeContext:
    flow_edge_id: UUID
    transfer_type_ref: UUID | None
    direction: str
    protocol_metadata: dict[str, Any]
    frequency_metadata: dict[str, Any]
    source_trace_ids: tuple[UUID, ...]
    confidence: float
    validation_status: ContextValidationStatus
    version: int


@dataclass(frozen=True, slots=True)
class JurisdictionContext:
    jurisdiction_context_id: UUID
    project_id: UUID
    jurisdiction_id: UUID | None
    context_type: str
    location_precision: LocationPrecision
    source: str
    confidence: float
    latitude: float | None
    longitude: float | None
    source_trace_ids: tuple[UUID, ...]
    validation_status: ContextValidationStatus
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class JurisdictionResolution:
    jurisdiction_resolution_id: UUID
    project_id: UUID
    input_value: str
    jurisdiction_context_id: UUID | None
    action: ResolutionAction
    confidence: float
    reason_code: str
    source_trace_ids: tuple[UUID, ...]
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class ContextConflict:
    conflict_id: UUID
    project_id: UUID
    conflict_type: str
    object_type: str
    object_ids: tuple[UUID, ...]
    reason_code: str
    details: dict[str, Any]
    source_trace_ids: tuple[UUID, ...]
    confidence: float
    resolution_status: str
    review_required: bool
    version: int


@dataclass(frozen=True, slots=True)
class ContextStatistics:
    raw_field_count: int
    normalized_data_item_count: int
    data_group_count: int
    data_flow_node_count: int
    data_flow_edge_count: int
    unresolved_count: int
    conflict_count: int
    review_required_count: int


@dataclass(frozen=True, slots=True)
class ContextResolutionResult:
    context_resolution_run_id: UUID
    project_id: UUID
    business_fact_summary: dict[str, Any]
    product_contexts: tuple[ProductContext, ...]
    scenario_contexts: tuple[ScenarioContext, ...]
    system_contexts: tuple[SystemContext, ...]
    device_contexts: tuple[DeviceContext, ...]
    party_contexts: tuple[PartyResolution, ...]
    data_inventory_summary: dict[str, Any]
    data_flow_summary: dict[str, Any]
    jurisdiction_contexts: tuple[JurisdictionContext, ...]
    unresolved_items: tuple[str, ...]
    conflicts: tuple[ContextConflict, ...]
    review_task_ids: tuple[UUID, ...]
    statistics: ContextStatistics
    confidence: float
    version: int
