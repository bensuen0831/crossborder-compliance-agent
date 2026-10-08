"""Read-only Stage 1 projection. Every legal value comes from its owning reader."""

from datetime import date
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from crossborder_compliance.domain.classification import ClassificationResult
from crossborder_compliance.domain.decision_contracts import (
    CandidateCompliancePathDTOv2,
    ComplianceObligationDTOv2,
    ComplianceRecommendationDTOv2,
    DecisionEnvelope,
    FinalCompliancePathDTOv2,
    RiskAssessmentDTOv2,
)
from crossborder_compliance.domain.formal_result_contracts import (
    CrossBorderAssessmentResult,
    RegulatoryDocumentRequirementResult,
)
from crossborder_compliance.domain.regulation_applicability import RegulationApplicabilityResult
from crossborder_compliance.domain.retrieval import RAGContextPack
from crossborder_compliance.domain.rules import Contract


class ProjectSummary(Contract):
    project_id: UUID
    project_version_id: UUID
    name: str
    analysis_as_of_date: date
    context_resolution_run_id: UUID
    data_inventory_version: int
    formal_context_version: int


class DocumentSummary(Contract):
    document_id: UUID
    document_version_id: UUID
    parse_run_id: UUID
    name: str
    version: int
    parse_status: str
    parser_version: str


class DataItemSummary(Contract):
    data_item_id: UUID
    name: str
    validation_status: str
    review_required: bool
    source_trace_ids: tuple[UUID, ...] = ()


class FlowNodeSummary(Contract):
    flow_node_id: UUID
    name: str
    jurisdiction_id: UUID | None


class FlowSummary(Contract):
    flow_edge_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    data_item_ids: tuple[UUID, ...]
    validation_status: str


class OfficialLegalBasis(Contract):
    legal_basis_id: UUID
    jurisdiction_id: UUID
    summary: str
    official_source: str
    citation_locator: str


class Stage1ContextProjection(Contract):
    project: ProjectSummary
    documents: tuple[DocumentSummary, ...]
    data_items: tuple[DataItemSummary, ...]
    flow_nodes: tuple[FlowNodeSummary, ...]
    flows: tuple[FlowSummary, ...]


class Stage1ComplianceResult(Stage1ContextProjection):
    contract_version: Literal["2.0"] = "2.0"
    workflow_run_id: UUID
    analysis_snapshot_id: UUID
    status: Literal["RUNNING", "COMPLETED", "REVIEW_REQUIRED", "WARNING", "FAILED", "CANCELLED"]
    graph_version: str
    mode: Literal["DATA_AWARE", "SCENARIO_LEVEL"]
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    steps: tuple[str, ...] = Field(max_length=17)
    completed_steps: tuple[str, ...] = Field(max_length=17)
    current_step: str | None
    reason_codes: tuple[str, ...]
    capability_gaps: tuple[str, ...]
    review_id: UUID | None
    classification: tuple[ClassificationResult, ...]
    applicability: tuple[RegulationApplicabilityResult, ...]
    obligation: DecisionEnvelope[ComplianceObligationDTOv2] | None
    cross_border: CrossBorderAssessmentResult | None
    candidate_path: DecisionEnvelope[CandidateCompliancePathDTOv2] | None
    risk: DecisionEnvelope[RiskAssessmentDTOv2] | None
    recommendation: DecisionEnvelope[ComplianceRecommendationDTOv2] | None
    final_path: DecisionEnvelope[FinalCompliancePathDTOv2] | None
    document_requirements: RegulatoryDocumentRequirementResult | None
    legal_basis: tuple[OfficialLegalBasis, ...]
    retrieval: RAGContextPack | None
    generation_available: Literal[False] = False


class Stage1ProjectionPort(Protocol):
    def context(
        self, project_id: UUID, snapshot_id: UUID, context_run_id: UUID
    ) -> Stage1ContextProjection: ...
    def legal_basis(self, ids: tuple[UUID, ...]) -> tuple[OfficialLegalBasis, ...]: ...


class Stage1ResultService:
    """No producer or persistence: compose authorized exact-snapshot reads only."""

    def __init__(
        self, *, projection, decisions, cross_border, documents, classification, country, retrieval
    ):
        self.projection = projection
        self.decisions, self.cross_border, self.documents = decisions, cross_border, documents
        self.classification, self.country, self.retrieval = classification, country, retrieval

    def read(self, *, plan, run_id, state, status, review_id, steps):
        context = self.projection.context(
            plan.project_id, plan.analysis_snapshot_id, plan.context_resolution_run_id
        )
        refs = state.get("result_refs", {})
        ref_sets = state.get("result_ref_sets", {})

        def check(value):
            if (value.project_id, value.analysis_snapshot_id) != (
                plan.project_id,
                plan.analysis_snapshot_id,
            ):
                raise LookupError("formal result scope mismatch")
            if value.context_version != context.project.formal_context_version:
                raise LookupError("formal result context version mismatch")
            if isinstance(value, ClassificationResult):
                if value.data_item_id not in plan.classification_data_item_ids:
                    raise LookupError("formal classification subject mismatch")
            elif (value.subject_type, value.subject_id) != (plan.subject_type, plan.subject_id):
                raise LookupError("formal result subject mismatch")
            return value

        classes = tuple(
            check(ClassificationResult.model_validate(self.classification.get_result(UUID(ref))))
            for ref in ref_sets.get(
                "classification", [refs["classification"]] if "classification" in refs else []
            )
        )
        apps = tuple(
            check(self.country.read(UUID(ref)))
            for ref in ref_sets.get(
                "applicability", [refs["applicability"]] if "applicability" in refs else []
            )
        )
        values = {
            step: check(self.decisions.read(step.upper(), UUID(refs[step])))
            if step in refs
            else None
            for step in ("obligation", "candidate_path", "risk", "recommendation", "final_path")
        }
        cross = (
            check(self.cross_border.read(UUID(refs["cross_border"])))
            if "cross_border" in refs
            else None
        )
        modern = state["identity"]["graph_definition_version"] == "phase1l-a-canonical-v2"
        docs = (
            check(self.documents.read(UUID(refs["documents"])))
            if modern and "documents" in refs
            else None
        )
        rag = None
        if "retrieval" in refs:
            saved = self.retrieval.scoped_saved_response(refs["retrieval"])
            rag = RAGContextPack.model_validate(saved["rag_context_pack"])
            if (UUID(rag.scope.project_id), UUID(rag.scope.analysis_snapshot_id)) != (
                plan.project_id,
                plan.analysis_snapshot_id,
            ):
                raise LookupError("retrieval scope mismatch")
        basis_ids = set(b for app in apps for b in app.legal_basis_ids)
        for result in values.values():
            if result:
                basis_ids.update(b for item in result.items for b in item.support.legal_basis_ids)
        if cross:
            basis_ids.update(b for item in cross.items for b in item.legal_basis_ids)
        if docs:
            basis_ids.update(b for item in docs.items for b in item.legal_basis_ids)
        gaps = [plan.input_capability_gap] if plan.input_capability_gap else []
        if not modern:
            gaps.append("HISTORICAL_FORMAL_RESULT_AUTHORITY_NOT_CONFIGURED")
        elif status == "COMPLETED" and (not cross or not docs):
            raise LookupError("completed formal authority references unavailable")
        return Stage1ComplianceResult(
            **context.model_dump(),
            workflow_run_id=run_id,
            analysis_snapshot_id=plan.analysis_snapshot_id,
            status=status,
            graph_version=state["identity"]["graph_definition_version"],
            mode=plan.mode,
            subject_type=plan.subject_type,
            subject_id=plan.subject_id,
            steps=steps,
            completed_steps=state.get("completed_steps", []),
            current_step=state.get("current_step"),
            reason_codes=state.get("reason_codes", []),
            capability_gaps=gaps,
            review_id=review_id,
            classification=classes,
            applicability=apps,
            **values,
            cross_border=cross,
            document_requirements=docs,
            legal_basis=self.projection.legal_basis(tuple(sorted(basis_ids, key=str))),
            retrieval=rag,
        )
