"""Reference-only requests; canonical country-compliance ownership prepares and saves."""

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.decision_contracts import StageKind
from crossborder_compliance.domain.decision_contracts import DecisionEngineVersion
from crossborder_compliance.domain.decision_engine import (
    CORRECTED_CALCULATION,
    LEGACY_VERIFICATION_CALCULATION,
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
    """New execution has one server-owned version; callers cannot choose legacy."""
    return _calculate(stage, inputs, parents, CORRECTED_CALCULATION)


def verify_calculation(stage, inputs, parents, engine_version: DecisionEngineVersion):
    """Historical read dispatches solely from the validated persisted version."""
    version = DecisionEngineVersion(engine_version)
    strategy = {DecisionEngineVersion.LEGACY: LEGACY_VERIFICATION_CALCULATION,
                DecisionEngineVersion.CORRECTED: CORRECTED_CALCULATION}[version]
    return _calculate(stage, inputs, parents, strategy)


def _calculate(stage, inputs, parents, strategy):
    if any(parent.engine_version != strategy.engine_version for parent in parents.values()):
        raise ValueError("FORMAL_DECISION_MIXED_ENGINE_VERSIONS")
    if stage == "OBLIGATION":
        return obligations(inputs, _calculation=strategy)
    if stage == "CANDIDATE_PATH":
        return candidates(inputs, parents["OBLIGATION"], _calculation=strategy)
    if stage == "RISK":
        return risks(inputs, parents["CANDIDATE_PATH"], _calculation=strategy)
    if stage == "RECOMMENDATION":
        return recommendation(inputs, parents["CANDIDATE_PATH"], parents["RISK"], _calculation=strategy)
    if stage == "FINAL_PATH":
        return final_path(
            inputs,
            parents["OBLIGATION"],
            parents["CANDIDATE_PATH"],
            parents["RISK"],
            parents["RECOMMENDATION"],
            _calculation=strategy,
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
