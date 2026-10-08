"""Canonical review application boundary; decisions never become legal facts."""

from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from crossborder_compliance.application.intake_services import IntakeFacts
from crossborder_compliance.domain.contracts import ProvenanceDTO, ReviewDecisionCode, ReviewStatus


class ReviewContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewDecisionRequest(ReviewContract):
    decision: ReviewDecisionCode
    expected_record_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    comment: str | None = Field(default=None, max_length=4096)


class FactSelection(ReviewContract):
    correction_type: Literal["SELECT_BUSINESS_FACT"]
    target_object_type: Literal["CONTEXT_CONFLICT"]
    target_object_id: UUID
    selected_fact_id: UUID


class ProductSelection(ReviewContract):
    correction_type: Literal["SELECT_PRODUCT_SCOPE"]
    target_object_type: Literal["CONTEXT_CONFLICT"]
    target_object_id: UUID
    selected_product_ids: tuple[UUID, ...] = Field(min_length=1, max_length=32)


class IntakeClarification(ReviewContract):
    correction_type: Literal["CLARIFY_INTAKE"]
    target_object_type: Literal["PROJECT_INTAKE"]
    target_object_id: UUID
    facts: IntakeFacts


class ReviewCorrectionRequest(ReviewContract):
    expected_record_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    correction: Annotated[
        FactSelection | ProductSelection | IntakeClarification,
        Field(discriminator="correction_type"),
    ]
    comment: str | None = Field(default=None, max_length=4096)


class ReviewHistoryItem(ReviewContract):
    decision_id: UUID
    decision: ReviewDecisionCode
    comment: str | None
    decided_by: str
    decided_at: datetime


class ReviewChoice(ReviewContract):
    object_id: UUID
    object_type: str
    display_value: str
    source_trace_ids: tuple[UUID, ...] = ()
    source_document_ids: tuple[UUID, ...] = ()
    structured_provenance: tuple[ProvenanceDTO, ...] = ()


class ReviewLineage(ReviewContract):
    correction_id: UUID
    source_review_id: UUID
    source_workflow_run_id: UUID
    source_snapshot_id: UUID
    successor_project_version_id: UUID
    successor_snapshot_id: UUID
    successor_workflow_run_id: UUID
    correction_type: str
    rerun_from_stage: Literal["requirement"] = "requirement"


class ReviewView(ReviewContract):
    review_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    workflow_run_id: UUID
    review_type: str
    reason_codes: tuple[str, ...]
    reason_summary: str
    object_type: str
    object_id: UUID
    owning_stage: str | None
    status: ReviewStatus
    presentation_state: Literal[
        "PENDING", "CHANGES_REQUESTED", "APPROVED", "REJECTED", "CANCELLED", "SUPERSEDED"
    ]
    allowed_actions: tuple[str, ...]
    resolution_mode: Literal["SAME_SNAPSHOT", "SUCCESSOR_SNAPSHOT", "UNAVAILABLE"]
    required_role: str
    continuation_status: Literal["NOT_AVAILABLE", "RESUME_PENDING", "CONTINUED"] = "NOT_AVAILABLE"
    created_at: datetime
    updated_at: datetime
    record_version: int
    evidence_refs: tuple[UUID, ...] = ()
    legal_basis_refs: tuple[UUID, ...] = ()
    choices: tuple[ReviewChoice, ...] = ()
    history: tuple[ReviewHistoryItem, ...] = ()
    lineage: ReviewLineage | None = None
    capability_gap: str | None = None
    intake_facts: IntakeFacts | None = None


class ReviewPage(ReviewContract):
    items: tuple[ReviewView, ...]
    total: int
    offset: int
    limit: int


class ReviewRepositoryPort(Protocol):
    def read(self, review_id: UUID) -> ReviewView: ...
    def list(self, **filters) -> ReviewPage: ...
    def decide(self, review_id: UUID, request: ReviewDecisionRequest): ...
    def correct(self, review_id: UUID, request: ReviewCorrectionRequest) -> ReviewLineage: ...


class HumanReviewService:
    def __init__(self, repository: ReviewRepositoryPort, delivery=None, successor_delivery=None):
        self.repository, self.delivery = repository, delivery
        self.successor_delivery = successor_delivery

    def read(self, review_id: UUID):
        return self.repository.read(review_id)

    def list(self, **filters):
        return self.repository.list(**filters)

    def decide(self, review_id: UUID, request: ReviewDecisionRequest):
        decision, review = self.repository.decide(review_id, request)
        # Ordinary human rejection/change requests never enter runtime.resume.
        if decision.decision == ReviewDecisionCode.APPROVE:
            if self.delivery is None:
                raise ValueError("CAPABILITY_NOT_CONFIGURED")
            self.delivery(review).resume(review.workflow_run_id, decision)
        return self.repository.read(review_id)

    def resume(self, review_id: UUID):
        decision, review = self.repository.approved_decision(review_id)
        if self.delivery is None:
            raise ValueError("CAPABILITY_NOT_CONFIGURED")
        self.delivery(review).resume(review.workflow_run_id, decision)
        return self.repository.read(review_id)

    def correct(self, review_id: UUID, request: ReviewCorrectionRequest):
        source = self.repository.read(review_id)
        lineage = self.repository.correct(review_id, request)
        if self.successor_delivery is not None:
            self.successor_delivery(source, lineage)
        return lineage


class WorkflowReviewGovernance:
    """Attach only canonical owner references; no copied legal payload in graph state."""

    def __init__(self, repository, contexts, plan):
        self.repository, self.contexts, self.plan = repository, contexts, plan

    def describe(self, review_id, step, reasons, result_refs=None):
        value = self.contexts.get_context_resolution(self.plan.project_id)
        if value is None or value.context_resolution_run_id != self.plan.context_resolution_run_id:
            raise LookupError("REVIEW_NOT_FOUND")
        conflicts = tuple(value.conflicts)
        codes = tuple(dict.fromkeys((*reasons, *(c.conflict_type for c in conflicts))))[:16]
        self.repository.describe(
            review_id,
            stage=step.value,
            reasons=codes,
            result_refs=result_refs or {},
            conflict_id=conflicts[0].conflict_id if conflicts else None,
            requirement_confirmation=bool(
                self.plan.requirement_review
                and step.value == "requirement"
                and not conflicts
                and not value.unresolved_items
            ),
        )

    def authorize_resume(self, workflow_run_id, decision):
        value = self.repository.read(UUID(str(decision["review_id"])))
        if value.workflow_run_id != workflow_run_id or value.resolution_mode != "SAME_SNAPSHOT":
            raise ValueError("ACTION_NOT_ALLOWED")
        if decision["decision"] != "APPROVE":
            raise ValueError("ACTION_NOT_ALLOWED")
        if value.status == "PENDING" and "APPROVE" not in value.allowed_actions:
            raise ValueError("ACTION_NOT_ALLOWED")
        if value.status != "PENDING" and value.status != "APPROVED":
            raise ValueError("REVIEW_ALREADY_RESOLVED")
        return decision
