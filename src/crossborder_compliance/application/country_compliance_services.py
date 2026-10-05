"""Generic typed facade; all authorization/persistence/evidence access stays in ports."""

from typing import Literal, Protocol
from uuid import UUID

from crossborder_compliance.domain.classification import ClassificationResult
from crossborder_compliance.domain.compliance_profiles import (
    CapabilityInput,
    CapabilityKind,
    CapabilityResult,
    CountryCapability,
    CountryComplianceProfile,
    ScenarioExecutionConfiguration,
    resolve_capability,
)
from crossborder_compliance.domain.localized_metadata import StableDisplayCode
from crossborder_compliance.domain.regulation_applicability import (
    ApplicabilityInput,
    RegulationApplicabilityResult,
    RegulationApplicabilitySkill,
)
from crossborder_compliance.domain.rules import Contract


class ApplicabilityRequest(Contract):
    project_id: UUID
    analysis_snapshot_id: UUID
    subject_type: Literal["DATA_ITEM", "DATA_FLOW", "SCENARIO"]
    subject_id: UUID
    jurisdiction_id: UUID
    applicability_config_id: UUID
    retrieval_run_id: UUID
    classification_result_ids: tuple[UUID, ...] = ()
    rule_hit_ids: tuple[UUID, ...] = ()


class CountryProfileResolution(Contract):
    status: Literal["READY", "REVIEW_REQUIRED", "CONFLICTED"]
    profiles: tuple[CountryComplianceProfile, ...]
    capabilities: tuple[CountryCapability, ...]
    scenario_configuration: ScenarioExecutionConfiguration
    reason_codes: tuple[StableDisplayCode, ...]


class CountryComplianceRepositoryPort(Protocol):
    def prepare_decision(self, request): ...
    def save_decision(self, request, result): ...
    def read_decision(self, stage, ident): ...
    def resolve_profile(
        self, project_id: UUID, snapshot_id: UUID, jurisdiction_id: UUID
    ) -> CountryProfileResolution: ...
    def classification(self, ident: UUID) -> ClassificationResult: ...
    def country_evidence(self, ident: UUID) -> dict: ...
    def prepare(self, request: ApplicabilityRequest) -> ApplicabilityInput: ...
    def save(
        self, request: ApplicabilityRequest, result: RegulationApplicabilityResult
    ) -> RegulationApplicabilityResult: ...


class CountryComplianceSkill:
    def __init__(self, repository: CountryComplianceRepositoryPort):
        self.repository = repository

    def resolve_profile(self, *, project_id: UUID, snapshot_id: UUID, jurisdiction_id: UUID):
        return self.repository.resolve_profile(project_id, snapshot_id, jurisdiction_id)

    def classify(self, result_id: UUID) -> ClassificationResult:
        return self.repository.classification(result_id)

    def retrieve_country_evidence(self, retrieval_run_id: UUID) -> dict:
        return self.repository.country_evidence(retrieval_run_id)

    def resolve_capability(self, request: CapabilityInput) -> CapabilityResult:
        resolution = self.resolve_profile(
            project_id=request.project_id,
            snapshot_id=request.analysis_snapshot_id,
            jurisdiction_id=request.jurisdiction_id,
        )
        if resolution.status != "READY":
            return CapabilityResult(
                kind=request.kind, status="REVIEW_REQUIRED", reason_codes=resolution.reason_codes
            )
        return resolve_capability(
            resolution.profiles[0] if resolution.profiles else None,
            resolution.capabilities,
            request,
        )

    def resolve_regulation_applicability(
        self, request: ApplicabilityRequest
    ) -> RegulationApplicabilityResult:
        inputs = self.repository.prepare(request)
        result = RegulationApplicabilitySkill().execute(inputs)
        return self.repository.save(request, result)

    # Controlled availability boundaries only: these do not calculate obligations or paths.
    def assess_cross_border(self, request: CapabilityInput):
        return self._future(request, CapabilityKind.CROSS_BORDER)

    def assess_localization(self, request: CapabilityInput):
        return self._future(request, CapabilityKind.LOCALIZATION)

    def resolve_filing_requirements(self, request: CapabilityInput):
        return self._future(request, CapabilityKind.FILING)

    def resolve_assessment_requirements(self, request: CapabilityInput):
        return self._future(request, CapabilityKind.IMPACT_ASSESSMENT)

    def resolve_contract_requirements(self, request: CapabilityInput):
        return self._future(request, CapabilityKind.CONTRACT)

    def resolve_regulator_requirements(self, request: CapabilityInput):
        return self._future(request, CapabilityKind.REGULATOR)

    def _future(self, request: CapabilityInput, kind: CapabilityKind):
        if request.kind != kind:
            raise ValueError("capability kind mismatch")
        return self.resolve_capability(request)
