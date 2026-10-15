"""Readiness records and independent test oracles, never formal legal authority.

These bounded payloads use the existing MetadataVersion lifecycle. They neither
replace canonical Knowledge/LegalBasis nor infer expert approval from a source URL.
"""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.formal_result_contracts import CrossBorderStatus
from crossborder_compliance.domain.formal_result_policies import RequirementLevel
from crossborder_compliance.domain.knowledge_management import ManagementRequest

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Code = Annotated[str, Field(min_length=1, max_length=160)]
DatasetKind = Literal["L1_SYNTHETIC_GOVERNED", "L2_REAL_REGULATORY"]


class AcceptancePayload(ManagementRequest):
    dataset_kind: DatasetKind
    synthetic_label: Literal["SYNTHETIC_GOVERNED_TEST_DATA"] | None = None

    @model_validator(mode="after")
    def explicit_acceptance_level(self):
        if (self.dataset_kind == "L1_SYNTHETIC_GOVERNED") != bool(self.synthetic_label):
            raise ValueError("ACCEPTANCE_DATASET_LABEL_MISMATCH")
        return self


class RegulatorySourcePin(ManagementRequest):
    knowledge_version_id: UUID
    content_sha256: Digest
    structure_node_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_nodes(self):
        if len(set(self.structure_node_ids)) != len(self.structure_node_ids):
            raise ValueError("DUPLICATE_ACCEPTANCE_CLAUSE")
        return self


class ExpectedRegulatorySemantics(ManagementRequest):
    """Explicit expert-authored oracle fields; no provider narrative or majority vote."""

    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)
    required_document_levels: dict[Code, RequirementLevel]
    generation_available: Literal[False] = False
    classification_codes: tuple[Code, ...] = Field(max_length=1000)
    applicability_codes: tuple[Code, ...] = Field(max_length=1000)
    cross_border_status: CrossBorderStatus
    obligation_codes: tuple[Code, ...] = Field(max_length=1000)
    candidate_path_codes: tuple[Code, ...] = Field(max_length=1000)
    risk_codes: tuple[Code, ...] = Field(max_length=1000)
    recommendation_codes: tuple[Code, ...] = Field(max_length=1000)
    final_path_codes: tuple[Code, ...] = Field(max_length=1000)
    required_document_codes: tuple[Code, ...] = Field(max_length=1000)
    reason_codes: tuple[Code, ...] = Field(max_length=1000)
    legal_source_pins: tuple[RegulatorySourcePin, ...] = Field(min_length=1, max_length=1000)


class RegulatoryAcceptanceCase(AcceptancePayload):
    schema_version: Literal["KB01_F0_CASE_V1"] = "KB01_F0_CASE_V1"
    description: str = Field(min_length=1, max_length=4096)
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)
    analysis_as_of_date: date
    input_manifest_sha256: Digest
    source_pins: tuple[RegulatorySourcePin, ...] = Field(max_length=1000)
    expected: ExpectedRegulatorySemantics | None = None
    evaluation_criteria: tuple[Code, ...] = Field(min_length=1, max_length=100)


class RegulatoryExpertAuthorization(AcceptancePayload):
    schema_version: Literal["KB01_F0_EXPERT_AUTHORIZATION_V1"] = "KB01_F0_EXPERT_AUTHORIZATION_V1"
    expert_actor_id: str = Field(min_length=1, max_length=160)
    jurisdiction_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)
    appointment_record_ref: str = Field(min_length=1, max_length=500)
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("INVALID_EXPERT_AUTHORIZATION_PERIOD")
        return self


class RegulatorySourceVerification(AcceptancePayload):
    schema_version: Literal["KB01_F0_SOURCE_VERIFICATION_V1"] = "KB01_F0_SOURCE_VERIFICATION_V1"
    source_pin: RegulatorySourcePin
    jurisdiction_id: UUID
    expert_authorization_version_id: UUID
    official_source_record_ref: str = Field(min_length=1, max_length=500)
    effective_from: date
    effective_to: date | None = None
    verification_notes: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def dates(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("INVALID_SOURCE_EFFECTIVITY_PERIOD")
        return self


class RegulatoryGoldReview(AcceptancePayload):
    schema_version: Literal["KB01_F0_GOLD_REVIEW_V1"] = "KB01_F0_GOLD_REVIEW_V1"
    case_version_id: UUID
    case_payload_sha256: Digest
    expected_semantics_sha256: Digest
    expert_authorization_version_id: UUID
    source_verification_version_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1000)
    expert_review_record_ref: str = Field(min_length=1, max_length=500)
    review_notes: str = Field(min_length=1, max_length=4096)


ACCEPTANCE_TYPES = {
    "REGULATORY_ACCEPTANCE_CASE": RegulatoryAcceptanceCase,
    "REGULATORY_EXPERT_AUTHORIZATION": RegulatoryExpertAuthorization,
    "REGULATORY_SOURCE_VERIFICATION": RegulatorySourceVerification,
    "REGULATORY_GOLD_REVIEW": RegulatoryGoldReview,
}
REGULATORY_ACCEPTANCE_KINDS = frozenset(ACCEPTANCE_TYPES)


class RegulatoryAcceptanceEvidence(ManagementRequest):
    schema_version: Literal["KB01_F0_ACCEPTANCE_EVIDENCE_V1"] = "KB01_F0_ACCEPTANCE_EVIDENCE_V1"
    dataset_kind: DatasetKind
    case_version_id: UUID
    gold_review_version_id: UUID
    tested_source_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    workflow_run_id: UUID
    analysis_snapshot_id: UUID
    observed_semantics_sha256: Digest
    expected_semantics_sha256: Digest
    exact_source_pins: tuple[RegulatorySourcePin, ...] = Field(min_length=1, max_length=1000)
    reconciliation: Literal["RECONCILIATION_MATCH", "RECONCILIATION_MISMATCH"]
    real_regulatory_legal_acceptance: Literal["NOT_EXECUTED", "PENDING_INDEPENDENT_ACCEPTANCE"]
    production_business_uat: Literal["NOT_EXECUTED"] = "NOT_EXECUTED"
    stage2_started: Literal[False] = False
