"""Version-two legal transfer/document requirement authority; v1 remains a projection."""

from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.decision_contracts import (
    Condition,
    DecisionProvenance,
    Digest,
    PinRef,
    StageRef,
    UnitDecimal,
    digest,
)
from crossborder_compliance.domain.decision_engine import DecisionIdentity
from crossborder_compliance.domain.formal_result_policies import RequirementLevel
from crossborder_compliance.domain.localized_metadata import StableDisplayCode
from crossborder_compliance.domain.rules import Contract

AuthorityKind = Literal["CROSS_BORDER", "DOCUMENT_REQUIREMENT"]
CrossBorderStatus = Literal[
    "DIRECT_TRANSFER_ALLOWED",
    "CONDITIONAL_TRANSFER_ALLOWED",
    "TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED",
    "REVIEW_REQUIRED",
    "NOT_APPLICABLE",
]


class AuthorityIdentity(DecisionIdentity):
    # Unresolved jurisdictions are retained as missing, never fabricated.
    jurisdiction_ids: tuple[UUID, ...] = ()


class AuthorityRef(StageRef):
    kind: Literal[
        "APPLICABILITY",
        "OBLIGATION",
        "CANDIDATE_PATH",
        "RISK",
        "RECOMMENDATION",
        "FINAL_PATH",
        "CROSS_BORDER",
        "DOCUMENT_REQUIREMENT",
    ]


class AuthorityProvenance(DecisionProvenance):
    origins: tuple[AuthorityRef, ...]
    engine_version: Literal["FORMAL_RESULT_AUTHORITY_V2"] = "FORMAL_RESULT_AUTHORITY_V2"


class CrossBorderAssessmentDTOv2(Contract):
    cross_border_assessment_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    data_item_ids: tuple[UUID, ...]
    data_flow_ids: tuple[UUID, ...]
    source_jurisdiction_ids: tuple[UUID, ...]
    destination_jurisdiction_ids: tuple[UUID, ...]
    status: CrossBorderStatus
    reason_codes: tuple[StableDisplayCode, ...] = Field(min_length=1)
    localization_required: bool
    filing_required: bool
    assessment_required: bool
    approval_required: bool
    obligation_ids: tuple[UUID, ...]
    applicability_result_ids: tuple[UUID, ...]
    rule_hit_ids: tuple[UUID, ...]
    legal_basis_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    policy_version_id: UUID | None
    review_required: bool
    confidence: UnitDecimal
    input_digest: Digest
    pins_digest: Digest

    @model_validator(mode="after")
    def legal_certainty(self):
        if self.review_required != (self.status == "REVIEW_REQUIRED"):
            raise ValueError("assessment review/status mismatch")
        if self.status not in {"REVIEW_REQUIRED", "NOT_APPLICABLE"} and not (
            self.source_jurisdiction_ids
            and self.destination_jurisdiction_ids
            and self.policy_version_id
            and self.applicability_result_ids
            and self.rule_hit_ids
            and self.legal_basis_ids
            and self.evidence_ids
        ):
            raise ValueError("transfer conclusion lacks exact formal support")
        return self


class RequiredDocumentDTOv2(Contract):
    document_requirement_id: UUID
    document_type_code: StableDisplayCode
    name: str
    requirement_level: RequirementLevel
    trigger_obligation_ids: tuple[UUID, ...]
    trigger_cross_border_assessment_ids: tuple[UUID, ...]
    trigger_path_step_ids: tuple[UUID, ...]
    requirement_ids: tuple[UUID, ...]
    legal_basis_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    jurisdiction_ids: tuple[UUID, ...]
    template_version_id: UUID | None
    reason_codes: tuple[StableDisplayCode, ...]
    conditions: tuple[Condition, ...]
    review_required: bool
    policy_version_id: UUID
    input_digest: Digest
    pins_digest: Digest

    @model_validator(mode="after")
    def traceability(self):
        if self.requirement_level != "NOT_APPLICABLE" and not (
            (
                self.trigger_obligation_ids
                or self.trigger_cross_border_assessment_ids
                or self.trigger_path_step_ids
            )
            and self.legal_basis_ids
            and self.evidence_ids
        ):
            raise ValueError("document requirement lacks authoritative legal trigger")
        return self


Item = TypeVar("Item")


class FormalAuthorityResult(AuthorityIdentity, Generic[Item]):
    result_id: UUID
    contract_version: Literal["2.0"] = "2.0"
    stage_kind: AuthorityKind
    upstream_refs: tuple[AuthorityRef, ...]
    items: tuple[Item, ...]
    input_sufficiency: Literal["SUFFICIENT", "INSUFFICIENT_EVIDENCE", "UNKNOWN"]
    conflict_state: Literal["CLEAR", "CONFLICTED"]
    review_required: bool
    reason_codes: tuple[StableDisplayCode, ...] = Field(min_length=1)
    confidence: UnitDecimal
    pins: tuple[PinRef, ...]
    input_digest: Digest
    pins_digest: Digest
    engine_version: Literal["FORMAL_RESULT_AUTHORITY_V2"] = "FORMAL_RESULT_AUTHORITY_V2"
    provenance: AuthorityProvenance
    ordinary_status: StableDisplayCode

    @property
    def summary_status(self):
        return "REVIEW_REQUIRED" if self.review_required else self.ordinary_status

    @model_validator(mode="after")
    def pinned(self):
        if self.pins != self.provenance.pins or digest(self.pins) != self.pins_digest:
            raise ValueError("formal authority pin provenance mismatch")
        if self.stage_kind == "DOCUMENT_REQUIREMENT" and self.review_required and self.items:
            raise ValueError("review cannot fabricate final document requirements")
        return self


class CrossBorderAssessmentResult(FormalAuthorityResult[CrossBorderAssessmentDTOv2]):
    stage_kind: Literal["CROSS_BORDER"] = "CROSS_BORDER"
    items: tuple[CrossBorderAssessmentDTOv2, ...] = Field(min_length=1, max_length=1)


class RegulatoryDocumentRequirementResult(FormalAuthorityResult[RequiredDocumentDTOv2]):
    stage_kind: Literal["DOCUMENT_REQUIREMENT"] = "DOCUMENT_REQUIREMENT"


AUTHORITY_ENVELOPES = {
    "CROSS_BORDER": CrossBorderAssessmentResult,
    "DOCUMENT_REQUIREMENT": RegulatoryDocumentRequirementResult,
}
