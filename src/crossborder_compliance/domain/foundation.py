from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class EntityMeta:
    tenant_id: UUID
    record_version: int = 1
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.record_version < 1:
            raise ValueError("record_version must be >= 1")


@dataclass(frozen=True, slots=True)
class DataFlowPartyLink(EntityMeta):
    data_flow_party_link_id: UUID = field(default=None)
    flow_node_id: UUID = field(default=None)
    project_party_id: UUID = field(default=None)
    role_code: str = ""


@dataclass(frozen=True, slots=True)
class ContractPartyLink(EntityMeta):
    contract_party_link_id: UUID = field(default=None)
    contract_id: UUID = field(default=None)
    project_party_id: UUID = field(default=None)
    relationship_code: str = ""


@dataclass(frozen=True, slots=True)
class PathStepResponsibleParty(EntityMeta):
    path_step_responsible_party_id: UUID = field(default=None)
    compliance_path_step_id: UUID = field(default=None)
    project_party_id: UUID = field(default=None)


@dataclass(frozen=True, slots=True)
class DocumentVersion(EntityMeta):
    document_version_id: UUID = field(default=None)
    document_id: UUID = field(default=None)
    version_no: int = 1
    storage_ref: str = ""
    content_hash: str = ""
    effective_from: date | None = None
    effective_to: date | None = None

    def __post_init__(self) -> None:
        EntityMeta.__post_init__(self)
        if self.version_no < 1:
            raise ValueError("version_no must be >= 1")


@dataclass(frozen=True, slots=True)
class SourceTraceRef(EntityMeta):
    source_trace_ref_id: UUID = field(default=None)
    document_version_id: UUID = field(default=None)
    page_no: int | None = None
    section: str | None = None
    table_ref: str | None = None
    row_ref: str | None = None
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class DocumentParseRun(EntityMeta):
    document_parse_run_id: UUID = field(default=None)
    document_version_id: UUID = field(default=None)
    parser_version: str = ""
    result_ref: str | None = None


@dataclass(frozen=True, slots=True)
class DataItemGroup(EntityMeta):
    data_item_group_id: UUID = field(default=None)
    project_id: UUID = field(default=None)
    name: str = ""
    grouping_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DataFlowNode(EntityMeta):
    flow_node_id: UUID = field(default=None)
    project_id: UUID = field(default=None)
    node_type: str = ""
    display_name: str = ""
    jurisdiction_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DataFlowEdge(EntityMeta):
    flow_edge_id: UUID = field(default=None)
    project_id: UUID = field(default=None)
    source_node_id: UUID = field(default=None)
    target_node_id: UUID = field(default=None)
    flow_type: str = ""
    route_sequence: int | None = None
    declared_cross_border: bool | None = None

    def __post_init__(self) -> None:
        EntityMeta.__post_init__(self)
        if self.source_node_id == self.target_node_id:
            raise ValueError("source_node_id and target_node_id must differ")


@dataclass(frozen=True, slots=True)
class DataItemFlowLink(EntityMeta):
    link_id: UUID = field(default=None)
    data_item_id: UUID = field(default=None)
    flow_edge_id: UUID = field(default=None)
    purpose: str | None = None
    volume_band: str | None = None


@dataclass(frozen=True, slots=True)
class DataItemProductLink(EntityMeta):
    data_item_product_link_id: UUID = field(default=None)
    data_item_id: UUID = field(default=None)
    product_ref: str = ""


@dataclass(frozen=True, slots=True)
class JurisdictionRelation(EntityMeta):
    jurisdiction_relation_id: UUID = field(default=None)
    source_jurisdiction_id: UUID = field(default=None)
    target_jurisdiction_id: UUID = field(default=None)
    relation_type: str = ""
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class ClassificationScheme(EntityMeta):
    scheme_id: UUID = field(default=None)
    code: str = ""
    name: str = ""
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class ClassificationCategory(EntityMeta):
    category_id: UUID = field(default=None)
    scheme_id: UUID = field(default=None)
    code: str = ""
    name: str = ""


@dataclass(frozen=True, slots=True)
class ClassificationLevel(EntityMeta):
    level_id: UUID = field(default=None)
    scheme_id: UUID = field(default=None)
    code: str = ""
    rank: int = 0


@dataclass(frozen=True, slots=True)
class Citation(EntityMeta):
    citation_id: UUID = field(default=None)
    evidence_id: UUID = field(default=None)
    locator: str = ""
    quote_hash: str | None = None


@dataclass(frozen=True, slots=True)
class LegalBasisRuleHitLink(EntityMeta):
    legal_basis_rule_hit_link_id: UUID = field(default=None)
    legal_basis_id: UUID = field(default=None)
    rule_hit_id: UUID = field(default=None)


@dataclass(frozen=True, slots=True)
class LegalBasisEvidenceLink(EntityMeta):
    legal_basis_evidence_link_id: UUID = field(default=None)
    legal_basis_id: UUID = field(default=None)
    evidence_id: UUID = field(default=None)


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot(EntityMeta):
    analysis_snapshot_id: UUID = field(default=None)
    project_version_id: UUID = field(default=None)
    snapshot_version: str = "1.0"
    analysis_as_of_date: date = field(default_factory=date.today)
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowRun(EntityMeta):
    workflow_run_id: UUID = field(default=None)
    thread_id: UUID = field(default=None)
    analysis_snapshot_id: UUID = field(default=None)
    graph_definition_version: str = ""
    langgraph_runtime_version: str = ""
    checkpointer_version: str = ""
    state_schema_version: str = ""

    def __post_init__(self) -> None:
        EntityMeta.__post_init__(self)
        if self.workflow_run_id != self.thread_id:
            raise ValueError("formal workflow_run_id must equal LangGraph thread_id")


@dataclass(frozen=True, slots=True)
class WorkflowNodeRun(EntityMeta):
    workflow_node_run_id: UUID = field(default=None)
    workflow_run_id: UUID = field(default=None)
    node_code: str = ""
    attempt_no: int = 1


@dataclass(frozen=True, slots=True)
class ReviewTask(EntityMeta):
    review_id: UUID = field(default=None)
    workflow_run_id: UUID = field(default=None)
    review_type: str = ""
    object_type: str = ""
    object_id: UUID = field(default=None)
    reason: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True, slots=True)
class ReviewDecision(EntityMeta):
    decision_id: UUID = field(default=None)
    review_id: UUID = field(default=None)
    decision_code: str = ""
    comment: str | None = None
    decided_by: str = ""
    decided_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class ExecutionIdempotencyRecord(EntityMeta):
    execution_idempotency_id: UUID = field(default=None)
    workflow_run_id: UUID = field(default=None)
    scope: str = ""
    idempotency_key: str = ""
    result_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ChannelContext(EntityMeta):
    channel_context_id: UUID = field(default=None)
    channel_type: str = ""
    request_id: str = ""
    user_id: str | None = None
    client_id: str | None = None
    locale: str | None = None


@dataclass(frozen=True, slots=True)
class InteractionSession(EntityMeta):
    session_id: UUID = field(default=None)
    channel_context_id: UUID = field(default=None)
    started_at: datetime = field(default_factory=utcnow)
    ended_at: datetime | None = None
