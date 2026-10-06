"""Orchestration contracts; no future legal domain types or runtime dependencies."""

from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SemanticStep(StrEnum):
    REQUIREMENT = "requirement"
    FORMAL_CONTEXT = "formal_context"
    DATA_FLOW = "data_flow"
    JURISDICTION = "jurisdiction"
    KNOWLEDGE_SCOPE = "knowledge_scope"
    RETRIEVAL = "retrieval"
    SUFFICIENCY = "sufficiency"
    CLASSIFICATION = "classification"
    APPLICABILITY = "applicability"
    OBLIGATION = "obligation"
    CANDIDATE_PATH = "candidate_path"
    RISK = "risk"
    RECOMMENDATION = "recommendation"
    FINAL_PATH = "final_path"
    DOCUMENTS = "documents"
    REPORT = "report"


class StageOutcomeCode(StrEnum):
    SUCCESS = "SUCCESS"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_INPUT = "INSUFFICIENT_INPUT"
    EVIDENCE_SUFFICIENT = "EVIDENCE_SUFFICIENT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    CONFLICTED = "CONFLICTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CAPABILITY_NOT_CONFIGURED = "CAPABILITY_NOT_CONFIGURED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    NON_RETRYABLE_FAILURE = "NON_RETRYABLE_FAILURE"
    FAILED = "FAILED"


class ReferenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExecutionIdentity(ReferenceModel):
    workflow_run_id: UUID
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    request_context_ref: UUID
    mode: Literal["DATA_AWARE", "SCENARIO_LEVEL"]
    graph_definition_version: str = Field(max_length=50)
    state_schema_version: str = Field(max_length=50)
    langgraph_runtime_version: str = Field(max_length=50)
    checkpointer_version: str = Field(max_length=50)


class StageExecutionRequest(ReferenceModel):
    identity: ExecutionIdentity
    step: SemanticStep
    result_refs: dict[SemanticStep, UUID] = Field(default_factory=dict, max_length=16)
    result_ref_sets: dict[SemanticStep, tuple[UUID, ...]] = Field(
        default_factory=dict, max_length=16
    )
    fallback_ref: UUID | None = None
    review_ref: UUID | None = None
    idempotency_key: str = Field(max_length=160)
    timeout_seconds: float = Field(gt=0)


class StageExecutionResult(ReferenceModel):
    status: StageOutcomeCode
    result_ref: UUID | None = None
    related_result_refs: tuple[UUID, ...] = Field(default=(), max_length=128)
    fallback_ref: UUID | None = None
    reason_codes: tuple[str, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def safe_result(self):
        import re

        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", c) for c in self.reason_codes):
            raise ValueError("structured reason codes only")
        if self.status == StageOutcomeCode.EVIDENCE_INSUFFICIENT and self.fallback_ref is None:
            raise ValueError("persisted actionable fallback reference required")
        if len(set(self.related_result_refs)) != len(self.related_result_refs):
            raise ValueError("unique related result references required")
        if self.related_result_refs and self.result_ref != self.related_result_refs[0]:
            raise ValueError("primary result must identify the first related reference")
        return self


class WorkflowAuthorizationPort(Protocol):
    def authorize(self, workflow_run_id: UUID, operation: str) -> ExecutionIdentity: ...
    def authorize_review(self, workflow_run_id: UUID, decision: dict) -> dict: ...


class WorkflowStagePort(Protocol):
    """Owning services enforce deadline, authorization and durable idempotency.

    Result/fallback refs must identify already persisted, authorized objects.
    Never return raw evidence, a provider object or a invented future legal result.
    """

    def execute(self, request: StageExecutionRequest) -> StageExecutionResult: ...


class UnavailableStage:
    def execute(self, request: StageExecutionRequest) -> StageExecutionResult:
        return StageExecutionResult(
            status=StageOutcomeCode.CAPABILITY_NOT_CONFIGURED,
            reason_codes=("STAGE_SERVICE_NOT_CONFIGURED",),
        )


class WorkflowRetryPolicy(ReferenceModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    interval_seconds: float = Field(default=0.1, ge=0, le=60)
    backoff_factor: float = Field(default=2, ge=1, le=10)


class WorkflowTimeoutPolicy(ReferenceModel):
    stage_seconds: float = Field(default=30, gt=0, le=3600)


class WorkflowExecutionPolicy(ReferenceModel):
    retry: WorkflowRetryPolicy = Field(default_factory=WorkflowRetryPolicy)
    timeout: WorkflowTimeoutPolicy = Field(default_factory=WorkflowTimeoutPolicy)
    recursion_limit: int = Field(default=100, ge=4, le=500)
    max_steps: int = Field(default=64, ge=1, le=200)
    max_visits_per_step: int = Field(default=3, ge=1, le=10)


class StageTransientFailure(Exception):
    """Only this explicit exception participates in bounded node retry."""


class WorkflowDeliveryRetryableFailure(Exception):
    """Queue delivery contention; deliberately distinct from node retry."""


class StageBusinessFailure(Exception):
    """Business errors must never be retried as transient infrastructure errors."""
