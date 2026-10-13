"""Public input schemas derived from the canonical intake, without authority."""

from uuid import UUID

from pydantic import Field

from crossborder_compliance.application.candidate_governance_services import CandidateDecisionInput
from crossborder_compliance.application.intake_services import IntakeFacts
from crossborder_compliance.domain.integrations import Contract


class ExternalProjectCreate(Contract):
    name: str = Field(min_length=1, max_length=200)
    facts: IntakeFacts


class ExternalIntakeUpdate(Contract):
    expected_version: int = Field(ge=1)
    facts: IntakeFacts


class ExternalCandidatePreparation(Contract):
    expected_version: int = Field(ge=1)


class ExternalCandidateDecisions(ExternalCandidatePreparation):
    candidate_preparation_id: UUID
    candidate_universe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: tuple[CandidateDecisionInput, ...] = Field(max_length=512)
