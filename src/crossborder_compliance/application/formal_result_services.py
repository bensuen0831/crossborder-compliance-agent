"""Reference-only owning use cases; no UI inputs, SDK or inference authority."""

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.formal_result_contracts import AuthorityKind
from crossborder_compliance.domain.formal_result_engine import (
    cross_border_assessment,
    regulatory_document_requirements,
)
from crossborder_compliance.domain.rules import Contract

if TYPE_CHECKING:
    from crossborder_compliance.application.country_compliance_services import (
        CountryComplianceRepositoryPort,
    )


class FormalAuthorityRequest(Contract):
    project_id: UUID
    analysis_snapshot_id: UUID
    subject_type: str = Field(pattern=r"^(DATA_ITEM|DATA_FLOW|SCENARIO)$")
    subject_id: UUID
    stage_kind: AuthorityKind
    obligation_result_id: UUID | None = None
    cross_border_result_id: UUID | None = None
    final_path_result_id: UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def references(self):
        if self.stage_kind == "CROSS_BORDER" and (
            self.cross_border_result_id or self.final_path_result_id
        ):
            raise ValueError("cross-border authority precedes implementation paths")
        return self


CALCULATE = {
    "CROSS_BORDER": cross_border_assessment,
    "DOCUMENT_REQUIREMENT": regulatory_document_requirements,
}


class _FormalAuthorityService:
    kind: str

    def __init__(self, repository: "CountryComplianceRepositoryPort"):
        self.repository = repository

    def initialize(self, project_id: UUID, snapshot_id: UUID):
        return self.repository.initialize_formal_results(project_id, snapshot_id)

    def execute(self, request: FormalAuthorityRequest):
        if request.stage_kind != self.kind:
            raise ValueError("wrong formal authority service")
        inputs = self.repository.prepare_formal_result(request)
        return self.repository.save_formal_result(request, CALCULATE[self.kind](inputs))

    def read(self, ident: UUID):
        return self.repository.read_formal_result(self.kind, ident)


class CrossBorderAssessmentService(_FormalAuthorityService):
    kind = "CROSS_BORDER"


class RegulatoryDocumentRequirementService(_FormalAuthorityService):
    kind = "DOCUMENT_REQUIREMENT"
