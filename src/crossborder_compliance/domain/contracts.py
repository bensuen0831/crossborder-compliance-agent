from __future__ import annotations
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

class ChannelType(StrEnum): WEB="WEB"; VSCODE="VSCODE"; THIRD_PARTY_API="THIRD_PARTY_API"
class AnalysisStatus(StrEnum): QUEUED="QUEUED"; RUNNING="RUNNING"; REVIEW_REQUIRED="REVIEW_REQUIRED"; COMPLETED="COMPLETED"; PARTIAL_COMPLETED="PARTIAL_COMPLETED"; FAILED="FAILED"; CANCELLED="CANCELLED"
class StageStatus(StrEnum): PENDING="PENDING"; RUNNING="RUNNING"; REVIEW_REQUIRED="REVIEW_REQUIRED"; COMPLETED="COMPLETED"; PARTIAL="PARTIAL"; FAILED="FAILED"; SKIPPED="SKIPPED"
class RiskLevel(StrEnum): LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CRITICAL="CRITICAL"; UNKNOWN="UNKNOWN"
class ComplianceStatus(StrEnum): ALLOWED="ALLOWED"; CONDITIONAL="CONDITIONAL"; BLOCKED="BLOCKED"; UNKNOWN="UNKNOWN"; NOT_APPLICABLE="NOT_APPLICABLE"
class ReviewStatus(StrEnum): NOT_REQUIRED="NOT_REQUIRED"; PENDING="PENDING"; APPROVED="APPROVED"; REJECTED="REJECTED"; CANCELLED="CANCELLED"
class WorkflowEventType(StrEnum): WORKFLOW_STARTED="WORKFLOW_STARTED"; NODE_STARTED="NODE_STARTED"; NODE_PROGRESS="NODE_PROGRESS"; NODE_COMPLETED="NODE_COMPLETED"; REVIEW_REQUIRED="REVIEW_REQUIRED"; WORKFLOW_RESUMED="WORKFLOW_RESUMED"; WORKFLOW_COMPLETED="WORKFLOW_COMPLETED"; WORKFLOW_FAILED="WORKFLOW_FAILED"
class MessageRole(StrEnum): USER="USER"; ASSISTANT="ASSISTANT"; SYSTEM="SYSTEM"; TOOL="TOOL"
class SubjectType(StrEnum): DATA_ITEM="DATA_ITEM"; DATA_ITEM_GROUP="DATA_ITEM_GROUP"; FLOW="FLOW"
class CapabilityType(StrEnum): AGENT="AGENT"; SKILL="SKILL"
class EvidenceValidationStatus(StrEnum): UNVALIDATED="UNVALIDATED"; VALID="VALID"; INVALID="INVALID"; CONFLICTED="CONFLICTED"
class ReviewDecisionCode(StrEnum): APPROVE="APPROVE"; REJECT="REJECT"; REQUEST_CHANGES="REQUEST_CHANGES"

class ProvenanceDTO(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_type: str
    source_ref: str
    source_version: str | None = None
    source_locator: str | None = None
    actor_ref: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    generated_by: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_ids: list[UUID] = Field(default_factory=list)

class ContractDTO(BaseModel):
    model_config=ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: str = "1.0"
    record_version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    provenance: ProvenanceDTO

class ObjectRefDTO(BaseModel):
    object_type: str
    object_id: UUID
class SourceLocatorDTO(BaseModel):
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    table: str | None = None
    row: str | None = None
    bbox: tuple[float,float,float,float] | None = None

class ProjectIntakeContext(ContractDTO):
    project_id: UUID; project_name: str = Field(min_length=1,max_length=200)
    industry: str|None=None; business_scenario: str|None=None; scenario_description: str|None=None
    selected_product_domains: list[str]=Field(default_factory=list); selected_products: list[str]=Field(default_factory=list)
    source_locations: list[str]=Field(default_factory=list); destination_locations: list[str]=Field(default_factory=list)
    processing_locations: list[str]=Field(default_factory=list); storage_locations: list[str]=Field(default_factory=list)
    data_flow_description: str|None=None; data_categories: list[str]=Field(default_factory=list); data_volume: str|None=None
    business_purpose: str|None=None; organizations: list[str]=Field(default_factory=list); third_parties: list[str]=Field(default_factory=list)
    uploaded_documents: list[str]=Field(default_factory=list); requested_outputs: list[str]=Field(default_factory=list); analysis_as_of_date: date

class ChannelContext(ContractDTO):
    channel_type: ChannelType; channel_instance_id: str|None=None; client_id: str|None=None; user_id: str|None=None
    tenant_id: UUID; locale: str|None=None; request_id: str; ip_hash: str|None=None
class InteractionSession(ContractDTO):
    session_id: UUID=Field(default_factory=uuid4); tenant_id: UUID; channel_context: ChannelContext; started_at: datetime; ended_at: datetime|None=None
class ConversationThread(ContractDTO):
    conversation_thread_id: UUID=Field(default_factory=uuid4); session_id: UUID; tenant_id: UUID; project_id: UUID|None=None; title: str|None=None
    analysis_run_ids: list[UUID]=Field(default_factory=list); status: Literal["ACTIVE","CLOSED","ARCHIVED"]="ACTIVE"
class ConversationMessage(ContractDTO):
    message_id: UUID=Field(default_factory=uuid4); conversation_thread_id: UUID; tenant_id: UUID; role: MessageRole; content: str
    attachment_refs: list[str]=Field(default_factory=list); analysis_run_id: UUID|None=None
class ComplianceAnalysisRequest(ContractDTO):
    project_id: UUID; project_version_id: UUID|None=None; conversation_thread_id: UUID|None=None; requested_outputs: list[str]=Field(min_length=1)
    analysis_as_of_date: date; idempotency_key: str=Field(min_length=1,max_length=128); channel_context: ChannelContext

class DataItemDTO(ContractDTO):
    data_item_id: UUID; project_id: UUID; name: str; canonical_type_ref: str|None=None; description: str|None=None
    source_document_version_id: UUID|None=None; source_locator: SourceLocatorDTO|None=None; group_ids: list[UUID]=Field(default_factory=list)
class DataItemGroupDTO(ContractDTO):
    data_item_group_id: UUID; project_id: UUID; name: str; member_data_item_ids: list[UUID]=Field(min_length=1); grouping_reason: str|None=None
class DataFlowNodeDTO(ContractDTO):
    flow_node_id: UUID; project_id: UUID; node_type: str; display_name: str; jurisdiction_id: UUID|None=None; party_ids:list[UUID]=Field(default_factory=list); system_refs:list[str]=Field(default_factory=list)
class DataFlowEdgeDTO(ContractDTO):
    flow_edge_id: UUID; project_id: UUID; source_node_id: UUID; target_node_id: UUID; flow_type:str; route_sequence:int|None=Field(default=None,ge=1); declared_cross_border:bool|None=None
    @model_validator(mode="after")
    def distinct_nodes(self):
        if self.source_node_id == self.target_node_id: raise ValueError("source_node_id and target_node_id must differ")
        return self
class DataItemFlowLinkDTO(ContractDTO):
    link_id: UUID; data_item_id:UUID; flow_edge_id:UUID; purpose:str|None=None; volume_band:str|None=None
class PartyRoleAssignmentDTO(ContractDTO):
    assignment_id:UUID; project_party_id:UUID; role_code:str; jurisdiction_id:UUID|None=None; effective_from:date|None=None; effective_to:date|None=None
class ProjectPartyDTO(ContractDTO):
    project_party_id:UUID; project_id:UUID; legal_entity_id:UUID|None=None; display_name:str; registration_jurisdiction_id:UUID|None=None; role_assignments:list[PartyRoleAssignmentDTO]=Field(default_factory=list)
class ClassificationResultDTO(ContractDTO):
    classification_result_id:UUID; subject_type:SubjectType; subject_id:UUID; scheme_id:UUID; scheme_version_id:UUID; level_id:UUID|None=None
    category_ids:list[UUID]; jurisdiction_id:UUID; confidence:float=Field(ge=0,le=1); evidence_ids:list[UUID]; review_required:bool
class CrossBorderAssessmentDTO(ContractDTO):
    cross_border_assessment_id:UUID; flow_edge_id:UUID; status:ComplianceStatus; reason_codes:list[str]; mechanism_ids:list[UUID]=Field(default_factory=list)
    requirement_ids:list[UUID]=Field(default_factory=list); legal_basis_ids:list[UUID]=Field(default_factory=list); evidence_ids:list[UUID]=Field(default_factory=list)
class LocalizationAssessmentDTO(ContractDTO):
    localization_assessment_id:UUID; subject_type:SubjectType; subject_id:UUID; jurisdiction_id:UUID; localization_required:bool|None
    requirement_ids:list[UUID]=Field(default_factory=list); legal_basis_ids:list[UUID]=Field(default_factory=list)
class ComplianceObligationDTO(ContractDTO):
    obligation_id:UUID; requirement_id:UUID; subject_refs:list[ObjectRefDTO]; responsible_party_ids:list[UUID]; status:Literal["APPLICABLE","NOT_APPLICABLE","CONDITIONAL","UNKNOWN"]
    legal_basis_ids:list[UUID]; evidence_ids:list[UUID]
class CandidateCompliancePathDTO(ContractDTO):
    candidate_path_id:UUID; analysis_run_id:UUID; mechanism_ids:list[UUID]; requirement_ids:list[UUID]; step_ids:list[UUID]
    eligibility_status:Literal["ELIGIBLE","CONDITIONAL","INELIGIBLE","UNKNOWN"]; legal_basis_ids:list[UUID]
class RiskAssessmentDTO(ContractDTO):
    risk_assessment_id:UUID; analysis_run_id:UUID; risk_level:RiskLevel; score_or_band:str|float|None=None; risk_item_ids:list[UUID]
    related_object_refs:list[ObjectRefDTO]; rule_hit_ids:list[UUID]=Field(default_factory=list); evidence_ids:list[UUID]
class ComplianceRecommendationDTO(ContractDTO):
    recommendation_id:UUID; analysis_run_id:UUID; recommendation_type:str; priority:str; description:str; related_requirement_ids:list[UUID]
    related_risk_item_ids:list[UUID]=Field(default_factory=list); evidence_ids:list[UUID]
class CompliancePathStepDTO(ContractDTO):
    step_id:UUID; sequence:int=Field(ge=1); step_name:str; description:str; status:Literal["PENDING","READY","BLOCKED","COMPLETED","REVIEW_REQUIRED"]
    prerequisite_step_ids:list[UUID]=Field(default_factory=list); responsible_party_ids:list[UUID]=Field(default_factory=list); requirement_ids:list[UUID]
    required_document_ids:list[UUID]=Field(default_factory=list); evidence_ids:list[UUID]
class FinalCompliancePathDTO(ContractDTO):
    final_path_id:UUID; analysis_run_id:UUID; selected_candidate_path_id:UUID|None=None; status:Literal["PROPOSED","REVIEW_REQUIRED","APPROVED","SUPERSEDED"]
    steps:list[CompliancePathStepDTO]; required_document_ids:list[UUID]=Field(default_factory=list); legal_basis_ids:list[UUID]; review_status:ReviewStatus
class RequiredDocumentDTO(ContractDTO):
    document_requirement_id:UUID; document_type_code:str; name:str; required:bool; requirement_ids:list[UUID]; template_ref:str|None=None; legal_basis_ids:list[UUID]
class EvidenceReferenceDTO(ContractDTO):
    evidence_id:UUID; evidence_type:str; source_ref:str; citation_id:UUID|None=None; locator:SourceLocatorDTO|None=None; excerpt_hash:str|None=None; validation_status:EvidenceValidationStatus
class LegalBasisItemDTO(ContractDTO):
    legal_basis_id:UUID; jurisdiction_id:UUID; regulation_id:UUID; regulation_name:str; regulation_version_id:UUID; regulator:str|None=None; article_or_section:str
    requirement_id:UUID|None=None; rule_hit_ids:list[UUID]=Field(default_factory=list); legal_basis_summary:str; applicability_reason:str; official_source:str
    source_url:HttpUrl|None=None; effective_date:date; evidence_ids:list[UUID]=Field(min_length=1); citation_locator:str; original_language:str|None=None
    confidence:float=Field(ge=0,le=1); validation_status:EvidenceValidationStatus
class DocumentComplianceSummary(ContractDTO):
    document_version_id:UUID; analysis_run_id:UUID; data_item_count:int=Field(ge=0); flow_count:int=Field(ge=0); issue_count:int=Field(ge=0); review_required:bool; evidence_ids:list[UUID]
class DataItemComplianceResult(ContractDTO):
    data_item_id:UUID; classification_results:list[ClassificationResultDTO]; cross_border_results:list[CrossBorderAssessmentDTO]=Field(default_factory=list)
    localization_results:list[LocalizationAssessmentDTO]=Field(default_factory=list); obligations:list[ComplianceObligationDTO]=Field(default_factory=list)
    risk_assessments:list[RiskAssessmentDTO]=Field(default_factory=list); recommendations:list[ComplianceRecommendationDTO]=Field(default_factory=list)
    legal_basis_ids:list[UUID]; evidence_ids:list[UUID]
class AnalysisStageResultDTO(ContractDTO):
    analysis_run_id:UUID; stage_code:str; stage_name:str; sequence:int=Field(ge=1); status:StageStatus; summary:str|None=None
    key_findings_count:int=Field(ge=0); warning_count:int=Field(ge=0); review_required:bool; started_at:datetime|None=None; completed_at:datetime|None=None
    related_object_refs:list[ObjectRefDTO]=Field(default_factory=list)
class ComplianceVisualizationResultDTO(ContractDTO):
    project_id:UUID; analysis_run_id:UUID; workflow_stage_views:list[dict[str,Any]]; kpi_cards:list[dict[str,Any]]; status_distribution:dict[str,int]
    risk_distribution:dict[str,int]; jurisdiction_distribution:dict[str,int]; map_nodes:list[dict[str,Any]]; map_edges:list[dict[str,Any]]
    topology_nodes:list[dict[str,Any]]; topology_edges:list[dict[str,Any]]; risk_layers:list[dict[str,Any]]; path_steps:list[dict[str,Any]]
    statistics:dict[str,Any]; legends:list[dict[str,Any]]; filters:list[dict[str,Any]]; default_view:str; available_views:list[str]
    @model_validator(mode="after")
    def default_must_exist(self):
        if self.default_view not in self.available_views: raise ValueError("default_view must be in available_views")
        return self
class Stage1ComplianceResultDTO(ContractDTO):
    project_id:UUID; analysis_run_id:UUID; analysis_snapshot_id:UUID; project_summary:dict[str,Any]; document_analysis_summary:list[DocumentComplianceSummary]
    stage_results:list[AnalysisStageResultDTO]; data_item_results:list[DataItemComplianceResult]; data_flow_results:list[dict[str,Any]]
    cross_border_results:list[CrossBorderAssessmentDTO]; jurisdiction_results:list[dict[str,Any]]; risk_summary:dict[str,Any]; recommendation_summary:dict[str,Any]
    final_compliance_path:FinalCompliancePathDTO|None=None; required_documents:list[RequiredDocumentDTO]; legal_basis_items:list[LegalBasisItemDTO]
    evidence_summary:dict[str,Any]; visualization:ComplianceVisualizationResultDTO|None=None; review_status:ReviewStatus; generated_at:datetime; version:str
class WorkflowEventDTO(ContractDTO):
    event_id:UUID=Field(default_factory=uuid4); event_type:WorkflowEventType; workflow_run_id:UUID; analysis_run_id:UUID|None=None; node_code:str|None=None
    status:str|None=None; payload:dict[str,Any]=Field(default_factory=dict); timestamp:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); request_id:str
class ReviewTaskDTO(ContractDTO):
    review_id:UUID; review_type:str; object_type:str; object_id:UUID; workflow_run_id:UUID; langgraph_thread_id:str; reason:str; evidence_ids:list[UUID]=Field(default_factory=list)
    required_role:str; status:ReviewStatus; review_result:dict[str,Any]|None=None; resolved_at:datetime|None=None
class ReviewDecisionDTO(ContractDTO):
    decision_id:UUID=Field(default_factory=uuid4); review_id:UUID; decision:ReviewDecisionCode; comment:str|None=None; decided_by:str; decided_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
class CapabilityExecutionRequestDTO(ContractDTO):
    capability_type:CapabilityType; capability_id:str; project_id:UUID; tenant_id:UUID; input:dict[str,Any]; requested_output:list[str]=Field(default_factory=list)
    analysis_snapshot_id:UUID; caller_context:ChannelContext
class StandardErrorDTO(ContractDTO):
    error_code:str=Field(pattern=r"^[A-Z0-9_]+$"); message:str; details:dict[str,Any]|None=None; trace_id:str; retryable:bool
class ComplianceAnalysisResult(ContractDTO):
    analysis_run_id:UUID; workflow_run_id:UUID; analysis_snapshot_id:UUID; status:AnalysisStatus; stage1_result:Stage1ComplianceResultDTO|None=None; error:StandardErrorDTO|None=None
