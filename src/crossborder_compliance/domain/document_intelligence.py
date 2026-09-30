from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ParseStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ParseQualityStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class CandidateValidationStatus(StrEnum):
    UNVALIDATED = "UNVALIDATED"
    VALID = "VALID"
    INVALID = "INVALID"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ConflictStatus(StrEnum):
    NONE = "NONE"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"


class CanonicalNodeType(StrEnum):
    DOCUMENT = "DOCUMENT"
    PAGE = "PAGE"
    BLOCK = "BLOCK"
    PARAGRAPH = "PARAGRAPH"
    HEADING = "HEADING"
    TABLE = "TABLE"
    TABLE_CELL = "TABLE_CELL"
    LIST = "LIST"
    IMAGE = "IMAGE"
    DIAGRAM = "DIAGRAM"
    SHEET = "SHEET"
    SLIDE = "SLIDE"


@dataclass(frozen=True, slots=True)
class SourceLocator:
    page_no: int | None = None
    sheet_name: str | None = None
    slide_no: int | None = None
    section_path: str | None = None
    table_id: str | None = None
    row_index: int | None = None
    column_index: int | None = None
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class SourceTraceRef:
    source_trace_ref_id: UUID
    document_id: UUID
    document_version_id: UUID
    parse_run_id: UUID
    structure_node_id: UUID
    locator: SourceLocator
    original_text_hash: str


@dataclass(frozen=True, slots=True)
class CanonicalStructureNode:
    structure_node_id: UUID
    document_version_id: UUID
    node_type: CanonicalNodeType
    sequence: int
    parent_node_id: UUID | None = None
    page_no: int | None = None
    sheet_name: str | None = None
    slide_no: int | None = None
    section_path: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    original_text: str | None = None
    normalized_text: str | None = None
    language: str | None = None
    source_locator: dict[str, Any] = field(default_factory=dict)
    parser_confidence: float | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CanonicalDocument(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalPage(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalBlock(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalParagraph(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalHeading(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalTable(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalTableCell(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalList(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalImage(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalDiagram(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalSheet(CanonicalStructureNode): pass
@dataclass(frozen=True, slots=True)
class CanonicalSlide(CanonicalStructureNode): pass


@dataclass(frozen=True, slots=True)
class DiagramNodeCandidate:
    candidate_node_id: UUID
    label: str
    node_type_candidate: str | None
    bbox: tuple[float, float, float, float] | None
    confidence: float
    source_trace_refs: tuple[SourceTraceRef, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagramEdgeCandidate:
    candidate_edge_id: UUID
    source_candidate_node_id: UUID
    target_candidate_node_id: UUID
    relation: str | None
    direction: str | None
    bbox: tuple[float, float, float, float] | None
    confidence: float
    source_trace_refs: tuple[SourceTraceRef, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateDiagramResult:
    nodes: tuple[DiagramNodeCandidate, ...]
    edges: tuple[DiagramEdgeCandidate, ...]
    labels: tuple[str, ...] = ()
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    nodes: tuple[CanonicalStructureNode, ...]
    native_parse_used: bool
    ocr_used: bool = False
    vision_used: bool = False
    warnings: tuple[str, ...] = ()
    detected_language: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentParseQualityResult:
    quality_result_id: UUID
    parse_run_id: UUID
    text_coverage: float
    page_coverage: float
    table_extraction_quality: float
    ocr_confidence: float | None
    layout_quality: float
    structural_completeness: float
    language_detection_confidence: float
    status: ParseQualityStatus
    score: float


@dataclass(frozen=True, slots=True)
class BusinessFactCandidate:
    fact_id: UUID
    fact_type: str
    normalized_value: Any
    original_value: Any
    source_trace_refs: tuple[SourceTraceRef, ...]
    extraction_method: str
    confidence: float
    validation_status: CandidateValidationStatus = CandidateValidationStatus.UNVALIDATED
    conflict_status: ConflictStatus = ConflictStatus.NONE


@dataclass(frozen=True, slots=True)
class CandidateDataItem:
    candidate_data_item_id: UUID
    raw_name: str
    normalized_name: str
    description: str | None
    value_type: str | None
    unit: str | None
    quantity_metadata: dict[str, Any]
    system_ref: str | None
    source_trace_refs: tuple[SourceTraceRef, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class CandidateDataFlowNode:
    candidate_node_id: UUID
    name: str
    node_type_candidate: str | None
    location_candidate: str | None
    party_candidate: str | None
    system_candidate: str | None
    source_trace_refs: tuple[SourceTraceRef, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class CandidateDataFlowEdge:
    candidate_edge_id: UUID
    source_candidate_node_id: UUID
    target_candidate_node_id: UUID
    direction: str | None
    transfer_type_candidate: str | None
    data_item_refs: tuple[UUID, ...]
    source_trace_refs: tuple[SourceTraceRef, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class CrossDocumentLink:
    cross_document_link_id: UUID
    link_type: str
    left_object_type: str
    left_object_id: UUID
    right_object_type: str
    right_object_id: UUID
    confidence: float
    source_trace_refs: tuple[SourceTraceRef, ...]


@dataclass(frozen=True, slots=True)
class DocumentAnalysisSummary:
    document_count: int
    document_version_count: int
    page_count: int
    sheet_count: int
    slide_count: int
    table_count: int
    raw_field_count: int
    normalized_candidate_data_item_count: int
    candidate_data_flow_count: int
    diagram_count: int
    unresolved_fact_count: int
    conflict_count: int
    review_required_count: int
    parsing_warning_count: int


def new_structure_node(
    *,
    document_version_id: UUID,
    node_type: CanonicalNodeType,
    sequence: int,
    **kwargs: Any,
) -> CanonicalStructureNode:
    return CanonicalStructureNode(
        structure_node_id=uuid4(),
        document_version_id=document_version_id,
        node_type=node_type,
        sequence=sequence,
        **kwargs,
    )
