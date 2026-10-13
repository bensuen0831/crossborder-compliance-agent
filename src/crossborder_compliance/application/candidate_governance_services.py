"""Shared pre-formal candidate governance commands for all channels."""

import json
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.knowledge import Contract


class PrepareDocumentCandidates(Contract):
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


class CandidateDecisionInput(Contract):
    preparation_candidate_id: UUID
    action: Literal["ACCEPT", "REJECT", "EDIT"]
    edited_payload: dict | None = None

    @model_validator(mode="after")
    def edit_shape(self):
        if (self.action == "EDIT") != (self.edited_payload is not None):
            raise ValueError("INVALID_CANDIDATE_DECISION")
        if (
            self.edited_payload is not None
            and len(json.dumps(self.edited_payload, ensure_ascii=False)) > 8192
        ):
            raise ValueError("CANDIDATE_EDIT_TOO_LARGE")
        return self


class ResolveDocumentCandidates(PrepareDocumentCandidates):
    candidate_preparation_id: UUID
    candidate_universe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: tuple[CandidateDecisionInput, ...] = Field(max_length=512)

    @model_validator(mode="after")
    def unique(self):
        if len({d.preparation_candidate_id for d in self.decisions}) != len(self.decisions):
            raise ValueError("INVALID_CANDIDATE_DECISION")
        return self


class CandidateSourcePreview(Contract):
    source_trace_ref_id: UUID
    parse_run_id: UUID
    document_version_id: UUID | None
    section: str | None = None
    source_excerpt: str = Field(max_length=600)


class CandidatePreviewItem(Contract):
    preparation_candidate_id: UUID
    candidate_id: UUID
    candidate_type: Literal["BUSINESS_FACT", "DATA_ITEM", "DATA_FLOW_NODE", "DATA_FLOW_EDGE"]
    candidate_origin: Literal["LLM_STRUCTURED_OUTPUT", "NATIVE_DETERMINISTIC", "DOCUMENT_DERIVED"]
    candidate_digest: str
    proposed_payload: dict
    confidence: float | None
    requires_confirmation: bool
    sources: tuple[CandidateSourcePreview, ...]
    decision_status: Literal["UNRESOLVED", "ACCEPT", "REJECT", "EDIT"] = "UNRESOLVED"
    edited_payload: dict | None = None
    llm_provenance: dict | None = None


class CandidatePreview(Contract):
    candidate_preparation_id: UUID | None
    project_version_id: UUID | None = None
    status: Literal["NOT_PREPARED", "PREPARING", "COMPLETED", "FAILED"]
    candidate_universe_digest: str | None
    stale: bool = False
    candidates: tuple[CandidatePreviewItem, ...]
    candidate_decision_set_id: UUID | None = None


class CandidateDecisionReceipt(Contract):
    candidate_decision_set_id: UUID
    candidate_preparation_id: UUID
    submitted_by: str
    submitted_at: datetime


class CandidateGovernancePort(Protocol):
    def prepare(self, project_id: UUID, request: PrepareDocumentCandidates) -> dict: ...
    def preview(self, project_id: UUID, preparation_id: UUID | None = None) -> dict: ...
    def resolve(self, project_id: UUID, request: ResolveDocumentCandidates) -> dict: ...


class DocumentCandidateGovernanceService:
    def __init__(self, owner: CandidateGovernancePort):
        self.owner = owner

    def prepare(self, project_id: UUID, request: PrepareDocumentCandidates):
        return self.owner.prepare(project_id, request)

    def preview(self, project_id: UUID, preparation_id: UUID | None = None):
        return self.owner.preview(project_id, preparation_id)

    def resolve(self, project_id: UUID, request: ResolveDocumentCandidates):
        return self.owner.resolve(project_id, request)
