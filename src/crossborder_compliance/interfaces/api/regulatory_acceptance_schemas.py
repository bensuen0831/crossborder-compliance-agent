"""Typed draft import and provenance read; callers cannot submit approval authority."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.knowledge_management import ManagementRequest
from crossborder_compliance.domain.regulatory_acceptance import ACCEPTANCE_TYPES, DatasetKind


class ImportAcceptanceDraft(ManagementRequest):
    kind: Literal[
        "REGULATORY_ACCEPTANCE_CASE",
        "REGULATORY_EXPERT_AUTHORIZATION",
        "REGULATORY_SOURCE_VERIFICATION",
        "REGULATORY_GOLD_REVIEW",
    ]
    code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
    display_name: str = Field(min_length=1, max_length=200)
    payload: dict

    @model_validator(mode="after")
    def typed_payload(self):
        ACCEPTANCE_TYPES[self.kind].model_validate(self.payload)
        return self


class AcceptanceTransition(ManagementRequest):
    expected_record_version: int = Field(ge=1)


class AcceptanceRecordView(ManagementRequest):
    definition_id: UUID
    version_id: UUID
    kind: str
    code: str
    version_no: int
    record_version: int
    lifecycle: str
    created_by: str
    approved_by: str | None
    approved_at: datetime | None
    published_at: datetime | None
    payload: dict
    payload_sha256: str


class AcceptanceReadinessView(ManagementRequest):
    case_version_id: UUID
    gold_review_version_id: UUID | None
    dataset_kind: DatasetKind
    checks: dict[str, bool]
    decision: Literal[
        "ENGINEERING_READINESS_ONLY",
        "READY_FOR_INDEPENDENT_ACCEPTANCE",
        "BLOCKED_EXTERNAL_EVIDENCE_PENDING",
    ]
    reason_codes: list[str]
    real_regulatory_legal_acceptance: Literal["NOT_EXECUTED"]
    production_business_uat: Literal["NOT_EXECUTED"]
