"""Production intake over the canonical Project/ProjectVersion aggregate."""

from copy import deepcopy
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model

from crossborder_compliance.domain.contracts import ProjectIntakeContext

# Derive writable facts from the canonical contract. Authority and audit fields
# are constructed by the server, never accepted from a browser.
_authority = {
    "project_id",
    "project_name",
    "schema_version",
    "record_version",
    "created_at",
    "updated_at",
    "provenance",
}
IntakeFacts = create_model(
    "IntakeFacts",
    __config__=ConfigDict(extra="forbid"),
    **{
        name: (field.annotation, deepcopy(field))
        for name, field in ProjectIntakeContext.model_fields.items()
        if name not in _authority
    },
)


class CreateProjectFromIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=128)
    facts: IntakeFacts


class UpdateIntakeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    facts: IntakeFacts


class ConfirmProjectIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class IntakeView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    project_version_id: UUID
    version: int = Field(ge=1)
    status: str
    intake: ProjectIntakeContext
    analysis_snapshot_id: UUID | None = None
    workflow_run_id: UUID | None = None
    retrieval_policy_id: UUID | None = None


class IntakeRepositoryPort(Protocol):
    def create_intake(self, request: CreateProjectFromIntake) -> IntakeView: ...
    def read_intake(self, project_id: UUID, version: int | None = None) -> IntakeView: ...
    def update_intake(self, project_id: UUID, request: UpdateIntakeDraft) -> IntakeView: ...
    def confirm_intake(self, project_id: UUID, expected_version: int, prepare) -> IntakeView: ...


class ProjectIntakeService:
    def __init__(self, repository: IntakeRepositoryPort, prepare_snapshot=None):
        self.repository, self.prepare_snapshot = repository, prepare_snapshot

    def create(self, request: CreateProjectFromIntake):
        return self.repository.create_intake(request)

    def read(self, project_id: UUID, version: int | None = None):
        return self.repository.read_intake(project_id, version)

    def update(self, project_id: UUID, request: UpdateIntakeDraft):
        return self.repository.update_intake(project_id, request)

    def confirm(self, project_id: UUID, request: ConfirmProjectIntake):
        current = self.read(project_id)
        facts = current.intake
        if not (
            facts.business_scenario
            and facts.selected_products
            and facts.source_locations
            and facts.destination_locations
            and facts.business_purpose
            and facts.business_purpose.strip()
            and facts.scenario_description
            and facts.scenario_description.strip()
        ):
            raise ValueError("INTAKE_REQUIRED_FACTS_MISSING")
        if self.prepare_snapshot is None:
            raise ValueError("INTAKE_SNAPSHOT_PREPARATION_UNAVAILABLE")
        return self.repository.confirm_intake(
            project_id, request.expected_version, self.prepare_snapshot
        )
