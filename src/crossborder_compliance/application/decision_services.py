"""Reference-only requests; canonical country-compliance ownership prepares and saves."""

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.decision_contracts import StageKind
from crossborder_compliance.domain.decision_engine import (
    candidates,
    final_path,
    obligations,
    recommendation,
    risks,
)
from crossborder_compliance.domain.rules import Contract

if TYPE_CHECKING:
    from crossborder_compliance.application.country_compliance_services import (
        CountryComplianceRepositoryPort,
    )

PARENTS = {
    "OBLIGATION": (),
    "CANDIDATE_PATH": ("OBLIGATION",),
    "RISK": ("CANDIDATE_PATH",),
    "RECOMMENDATION": ("CANDIDATE_PATH", "RISK"),
    "FINAL_PATH": ("OBLIGATION", "CANDIDATE_PATH", "RISK", "RECOMMENDATION"),
}


class UpstreamIdentifier(Contract):
    kind: StageKind
    result_id: UUID


class DecisionRequest(Contract):
    project_id: UUID
    analysis_snapshot_id: UUID
    subject_type: str = Field(pattern=r"^(DATA_ITEM|DATA_FLOW|SCENARIO)$")
    subject_id: UUID
    stage_kind: StageKind
    applicability_result_ids: tuple[UUID, ...] = Field(min_length=1)
    upstream_refs: tuple[UpstreamIdentifier, ...] = ()
    idempotency_key: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def shape(self):
        if len(set(self.applicability_result_ids)) != len(self.applicability_result_ids):
            raise ValueError("duplicate applicability reference")
        if len({r.kind for r in self.upstream_refs}) != len(self.upstream_refs) or {
            r.kind for r in self.upstream_refs
        } != set(PARENTS[self.stage_kind]):
            raise ValueError("wrong stage dependency references")
        return self


def calculate(stage, inputs, parents):
    if stage == "OBLIGATION":
        return obligations(inputs)
    if stage == "CANDIDATE_PATH":
        return candidates(inputs, parents["OBLIGATION"])
    if stage == "RISK":
        return risks(inputs, parents["CANDIDATE_PATH"])
    if stage == "RECOMMENDATION":
        return recommendation(inputs, parents["CANDIDATE_PATH"], parents["RISK"])
    if stage == "FINAL_PATH":
        return final_path(
            inputs,
            parents["OBLIGATION"],
            parents["CANDIDATE_PATH"],
            parents["RISK"],
            parents["RECOMMENDATION"],
        )
    raise ValueError("unknown stage")


class FormalDecisionService:
    def __init__(self, repository: "CountryComplianceRepositoryPort"):
        self.repository = repository

    def execute(self, request: DecisionRequest):
        inputs, parents = self.repository.prepare_decision(request)
        result = calculate(request.stage_kind, inputs, parents)
        return self.repository.save_decision(request, result)

    def read(self, stage: StageKind, ident: UUID):
        return self.repository.read_decision(stage, ident)
