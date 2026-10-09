"""Public input schemas derived from the canonical intake, without authority."""
from pydantic import Field
from crossborder_compliance.application.intake_services import IntakeFacts
from crossborder_compliance.domain.integrations import Contract


class ExternalProjectCreate(Contract):
    name: str = Field(min_length=1,max_length=200)
    facts: IntakeFacts


class ExternalIntakeUpdate(Contract):
    expected_version: int = Field(ge=1)
    facts: IntakeFacts
