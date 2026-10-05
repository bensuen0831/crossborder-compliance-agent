"""Version2 extensions of the existing decision DTO kinds; v1 contracts stay unchanged."""

import json
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.contracts import RiskLevel
from crossborder_compliance.domain.localized_metadata import StableDisplayCode, StableMetadataCode
from crossborder_compliance.domain.rules import Contract

StageKind = Literal["OBLIGATION", "CANDIDATE_PATH", "RISK", "RECOMMENDATION", "FINAL_PATH"]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
UnitDecimal = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)]
Score = Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]
LegalEffect = Literal["REQUIRED", "CONDITIONAL", "NOT_APPLICABLE", "UNDETERMINED"]
Fulfillment = Literal["SATISFIED", "UNMET", "UNKNOWN", "NOT_APPLICABLE"]
LegalViability = Literal["VIABLE", "CONDITIONAL", "LEGALLY_PROHIBITED", "UNDETERMINED"]
Availability = Literal["AVAILABLE", "CAPABILITY_NOT_CONFIGURED", "UNAVAILABLE", "UNKNOWN"]
FactValue = str | bool | int | Decimal | date | datetime | tuple[str | bool | int | Decimal, ...]


class StageRef(Contract):
    kind: Literal[
        "APPLICABILITY", "OBLIGATION", "CANDIDATE_PATH", "RISK", "RECOMMENDATION", "FINAL_PATH"
    ]
    result_id: UUID
    item_id: UUID | None = None
    content_digest: Digest


class PinRef(Contract):
    pin_id: UUID
    kind: StableDisplayCode
    object_id: UUID
    version_id: UUID
    version_no: int = Field(ge=1)


class LegalSupport(Contract):
    applicability_result_ids: tuple[UUID, ...] = ()
    rule_hit_ids: tuple[UUID, ...] = ()
    rule_version_ids: tuple[UUID, ...] = ()
    legal_basis_ids: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    evidence_pack_ids: tuple[UUID, ...] = ()
    retrieval_run_ids: tuple[UUID, ...] = ()
    knowledge_version_ids: tuple[UUID, ...] = ()
    structure_node_ids: tuple[UUID, ...] = ()
    citation_ids: tuple[UUID, ...] = ()
    citation_locators: tuple[str, ...] = ()
    fact_refs: tuple[UUID, ...] = ()


class Condition(Contract):
    entry_id: UUID
    code: StableDisplayCode
    predicate_digest: Digest
    evaluation: Literal["TRUE", "FALSE", "UNKNOWN"]
    fact_refs: tuple[UUID, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()


class Action(Contract):
    entry_id: UUID
    action_code: StableDisplayCode
    sequence: int = Field(ge=1)
    responsible_party_ids: tuple[UUID, ...] = ()
    conditions: tuple[Condition, ...] = ()
    dependency_entry_ids: tuple[UUID, ...] = ()
    obligation_ids: tuple[UUID, ...] = ()
    performed: Literal[False] = False


class DecisionProvenance(Contract):
    origins: tuple[StageRef, ...]
    context_fact_refs: tuple[UUID, ...]
    retrieval_run_ids: tuple[UUID, ...]
    pins: tuple[PinRef, ...]
    engine_version: Literal["FORMAL_DECISION_V2"] = "FORMAL_DECISION_V2"
    schema_version: Literal["2.0"] = "2.0"
    computation_timestamp: datetime
    actor_ref: str
    request_id: str
    correlation_id: str


class DecisionItem(Contract):
    contract_version: Literal["2.0"] = "2.0"
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1)
    support: LegalSupport
    reason_codes: tuple[StableDisplayCode, ...] = Field(min_length=1)
    review_required: bool = False
    policy_version_ref: UUID


class ComplianceObligationDTOv2(DecisionItem):
    obligation_id: UUID
    requirement_id: UUID
    obligation_code: StableDisplayCode
    legal_effect: LegalEffect
    fulfillment_state: Fulfillment
    conditions: tuple[Condition, ...]
    responsible_party_ids: tuple[UUID, ...] = ()
    legal_effect_code: Literal["REQUIREMENT", "TRANSFER_PROHIBITED", "LOCALIZATION_REQUIRED"]

    @model_validator(mode="after")
    def legal_authority(self):
        if self.legal_effect in {"REQUIRED", "CONDITIONAL"} and not (
            self.support.applicability_result_ids
            and self.support.rule_hit_ids
            and self.support.legal_basis_ids
            and self.support.evidence_ids
        ):
            raise ValueError("obligation lacks formal legal support")
        return self


class CapabilityDependency(Contract):
    capability_id: UUID
    version_id: UUID | None
    availability: Availability


class CandidateCompliancePathDTOv2(DecisionItem):
    candidate_path_id: UUID
    path_code: StableDisplayCode
    template_entry_id: UUID
    obligation_ids: tuple[UUID, ...]
    prerequisites: tuple[Condition, ...]
    unmet_requirement_ids: tuple[UUID, ...]
    mechanism_entry_ids: tuple[UUID, ...]
    capability_dependencies: tuple[CapabilityDependency, ...]
    legal_viability: LegalViability
    operational_availability: Availability
    steps: tuple[Action, ...]
    template_priority: int


class RiskFactorResult(Contract):
    code: StableDisplayCode
    observation_code: StableMetadataCode
    observed_value: Decimal | None
    score: Score | None
    weight: UnitDecimal
    required: bool
    included: bool
    fact_refs: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]


class RiskDimensionResult(Contract):
    code: StableDisplayCode
    factors: tuple[RiskFactorResult, ...]
    score: Score | None
    band: RiskLevel
    weight: UnitDecimal


class RiskAssessmentDTOv2(DecisionItem):
    risk_assessment_id: UUID
    candidate_path_id: UUID
    dimensions: tuple[RiskDimensionResult, ...]
    band_conditions: tuple[Condition, ...] = ()
    score: Score | None
    risk_level: RiskLevel
    coverage: UnitDecimal
    input_sufficiency: Literal["SUFFICIENT", "INSUFFICIENT_EVIDENCE", "UNKNOWN"]
    score_mode: Literal["WEIGHTED", "BAND_ONLY"]
    decimal_scale: int = Field(ge=0, le=8)
    rounding: Literal["ROUND_HALF_EVEN", "ROUND_HALF_UP", "ROUND_DOWN"]


class RankingOutcome(Contract):
    candidate_path_id: UUID
    criterion_values: tuple[Decimal, ...]


class ExcludedCandidate(Contract):
    candidate_path_id: UUID
    reason_codes: tuple[StableDisplayCode, ...] = Field(min_length=1)


class ComplianceRecommendationDTOv2(DecisionItem):
    recommendation_id: UUID
    status: Literal[
        "RECOMMENDED", "CONDITIONAL_ALTERNATIVES", "TIED", "NO_RECOMMENDATION", "NOT_APPLICABLE"
    ]
    selected_candidate_id: UUID | None
    rankings: tuple[RankingOutcome, ...]
    excluded_candidates: tuple[ExcludedCandidate, ...]
    alternative_candidate_ids: tuple[UUID, ...]
    tied_candidate_ids: tuple[UUID, ...]
    risk_assessment_ids: tuple[UUID, ...]

    @model_validator(mode="after")
    def selection(self):
        if self.status != "RECOMMENDED" and self.selected_candidate_id is not None:
            raise ValueError("unresolved recommendation cannot select")
        if self.status == "TIED" and (not self.review_required or len(self.tied_candidate_ids) < 2):
            raise ValueError("tie requires review and alternatives")
        return self


class FinalCompliancePathDTOv2(DecisionItem):
    final_path_id: UUID
    status: Literal[
        "PROPOSED",
        "CONDITIONAL_PROPOSAL",
        "NO_VIABLE_PATH",
        "NOT_APPLICABLE",
        "UNDETERMINED",
        "LEGALLY_PROHIBITED",
    ]
    selected_candidate_path_id: UUID | None
    obligation_ids: tuple[UUID, ...]
    required_conditions: tuple[Condition, ...]
    actions: tuple[Action, ...]
    unmet_requirement_ids: tuple[UUID, ...]
    residual_risk_ref: StageRef | None
    alternative_candidate_ids: tuple[UUID, ...]
    unresolved_codes: tuple[StableDisplayCode, ...]
    review_status: Literal["NOT_REQUIRED", "PENDING"]

    @model_validator(mode="after")
    def unresolved_selection(self):
        if self.unresolved_codes and self.selected_candidate_path_id is not None:
            raise ValueError("unresolved final path cannot select")
        return self


Item = TypeVar("Item", bound=DecisionItem)


class DecisionEnvelope(Contract, Generic[Item]):
    result_id: UUID
    contract_version: Literal["2.0"] = "2.0"
    stage_kind: StageKind
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    project_version_id: UUID
    context_version: int = Field(ge=1)
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    data_item_ids: tuple[UUID, ...] = ()
    data_flow_ids: tuple[UUID, ...] = ()
    scenario_definition_ids: tuple[UUID, ...] = ()
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1)
    analysis_as_of_date: date
    upstream_refs: tuple[StageRef, ...]
    items: tuple[Item, ...]
    input_sufficiency: Literal["SUFFICIENT", "INSUFFICIENT_EVIDENCE", "UNKNOWN"]
    conflict_state: Literal["CLEAR", "CONFLICTED"]
    review_required: bool
    reason_codes: tuple[StableDisplayCode, ...] = Field(min_length=1)
    confidence: UnitDecimal
    pins: tuple[PinRef, ...]
    input_digest: Digest
    pins_digest: Digest
    engine_version: Literal["FORMAL_DECISION_V2"] = "FORMAL_DECISION_V2"
    provenance: DecisionProvenance
    ordinary_status: StableDisplayCode

    @property
    def summary_status(self):
        if self.conflict_state == "CONFLICTED":
            return "CONFLICTED"
        if self.input_sufficiency != "SUFFICIENT":
            return "INSUFFICIENT_EVIDENCE"
        if self.review_required:
            return "REVIEW_REQUIRED"
        return self.ordinary_status

    @model_validator(mode="after")
    def scope(self):
        if len(set(self.jurisdiction_ids)) != len(self.jurisdiction_ids):
            raise ValueError("duplicate jurisdiction")
        if any(not set(i.jurisdiction_ids) <= set(self.jurisdiction_ids) for i in self.items):
            raise ValueError("item outside envelope jurisdiction")
        if self.pins != self.provenance.pins or digest(self.pins) != self.pins_digest:
            raise ValueError("pin provenance mismatch")
        return self


ENVELOPE_TYPES = {
    "OBLIGATION": DecisionEnvelope[ComplianceObligationDTOv2],
    "CANDIDATE_PATH": DecisionEnvelope[CandidateCompliancePathDTOv2],
    "RISK": DecisionEnvelope[RiskAssessmentDTOv2],
    "RECOMMENDATION": DecisionEnvelope[ComplianceRecommendationDTOv2],
    "FINAL_PATH": DecisionEnvelope[FinalCompliancePathDTOv2],
}


def canonical(value):
    """Preserve ordered arrays; normalize declared reference sets before constructing them."""
    if hasattr(value, "model_dump"):
        return canonical(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in sorted(value.items(), key=lambda v: str(v[0]))}
    if isinstance(value, (tuple, list)):
        return [canonical(v) for v in value]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("nonfinite formal decimal")
        return format(value.normalize(), "f")
    if isinstance(value, (UUID, date, datetime)):
        return str(value) if isinstance(value, UUID) else value.isoformat()
    return value


def canonical_json(value):
    return json.dumps(
        canonical(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value):
    return sha256(canonical_json(value).encode()).hexdigest()


def result_digest(value):
    data = value.model_dump(mode="python")
    if "provenance" in data:
        for name in ("computation_timestamp", "actor_ref", "request_id", "correlation_id"):
            data["provenance"].pop(name, None)
    return digest(data)


def unique(values):
    return tuple(sorted(set(values), key=str))
