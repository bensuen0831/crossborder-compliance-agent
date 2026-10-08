"""Governed candidate/derived enhancement contracts; no legal decision purpose."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.knowledge import Contract
from crossborder_compliance.domain.llm_gateway import LLMResult

LLM_METADATA_KINDS = frozenset(
    {"LLM_INVOCATION_POLICY", "MODEL_USAGE_POLICY", "LLM_PROVIDER_PRESET"}
)


class LLMUsageMode(StrEnum):
    MINIMAL = "MINIMAL"
    STANDARD = "STANDARD"
    ENHANCED = "ENHANCED"


class ModelSelectionMode(StrEnum):
    AUTO = "AUTO"
    SINGLE = "SINGLE"
    MULTI_MODEL = "MULTI_MODEL"


class InvocationTrigger(StrEnum):
    DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED = "DOCUMENT_SEMANTIC_EXTRACTION_REQUIRED"
    DOCUMENT_EXTRACTION_LOW_CONFIDENCE = "DOCUMENT_EXTRACTION_LOW_CONFIDENCE"
    DOCUMENT_FIELD_CONFLICT = "DOCUMENT_FIELD_CONFLICT"
    RETRIEVAL_QUERY_EXPANSION_REQUIRED = "RETRIEVAL_QUERY_EXPANSION_REQUIRED"
    KNOWLEDGE_EVIDENCE_INSUFFICIENT = "KNOWLEDGE_EVIDENCE_INSUFFICIENT"
    RESULT_EXPLANATION_REQUESTED = "RESULT_EXPLANATION_REQUESTED"
    DOCUMENT_GENERATION_REQUESTED = "DOCUMENT_GENERATION_REQUESTED"
    CONTRACT_GENERATION_REQUESTED = "CONTRACT_GENERATION_REQUESTED"
    CONTRACT_REVIEW_REQUESTED = "CONTRACT_REVIEW_REQUESTED"


class InvocationPurpose(StrEnum):
    DOCUMENT_CANDIDATE_EXTRACTION = "DOCUMENT_CANDIDATE_EXTRACTION"
    QUERY_EXPANSION = "QUERY_EXPANSION"
    DERIVED_EXPLANATION = "DERIVED_EXPLANATION"


class AIModelPreference(Contract):
    usage_mode: LLMUsageMode = LLMUsageMode.STANDARD
    selection_mode: ModelSelectionMode = ModelSelectionMode.AUTO
    selected_model_ids: tuple[UUID, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def cardinality(self):
        size = len(self.selected_model_ids)
        if len(set(self.selected_model_ids)) != size:
            raise ValueError("DUPLICATE_MODEL_SELECTION")
        if (
            (self.selection_mode == ModelSelectionMode.AUTO and size != 0)
            or (self.selection_mode == ModelSelectionMode.SINGLE and size != 1)
            or (self.selection_mode == ModelSelectionMode.MULTI_MODEL and size < 2)
        ):
            raise ValueError("MODEL_SELECTION_CARDINALITY_INVALID")
        if (
            self.selection_mode == ModelSelectionMode.MULTI_MODEL
            and self.usage_mode != LLMUsageMode.ENHANCED
        ):
            raise ValueError("MULTI_MODEL_REQUIRES_ENHANCED")
        return self


class LLMInvocationPolicy(Contract):
    policy_id: UUID
    version_id: UUID
    allowed_triggers: dict[LLMUsageMode, tuple[InvocationTrigger, ...]]
    max_models: int = Field(ge=2, le=16)


class InvocationFacts(Contract):
    """Internal typed facts supplied by owning services, never browser authority."""

    trigger: InvocationTrigger
    purpose: InvocationPurpose
    parser_insufficient: bool = False
    structured_fields_complete: bool = False
    evidence_sufficient: bool = False


class InvocationDecision(Contract):
    allowed: bool
    reason_code: str
    policy_version_id: UUID
    purpose: InvocationPurpose


class ModelInvocationOutcome(Contract):
    request_id: UUID
    model_id: UUID
    status: str
    result: LLMResult | None = None
    reason_code: str | None = None


class MultiModelInvocationResult(Contract):
    invocation_group_id: UUID
    analysis_snapshot_id: UUID
    purpose: InvocationPurpose
    strategy: ModelSelectionMode
    model_results: tuple[ModelInvocationOutcome, ...]
    status: str
    authority: Literal["DERIVED_CANDIDATE"] = "DERIVED_CANDIDATE"
