"""Governed C0 policy payloads in the existing metadata/version/AST authority."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.decision_policies import ConditionPolicy, DecisionPolicy
from crossborder_compliance.domain.localized_metadata import (
    LocalizedDisplayMetadata,
    StableDisplayCode,
)
from crossborder_compliance.domain.rules import Contract

RequirementLevel = Literal["REQUIRED", "CONDITIONAL", "RECOMMENDED", "NOT_APPLICABLE"]


class TransferPrerequisite(Contract):
    requirement_id: UUID
    kind: Literal[
        "APPROVAL", "FILING", "ASSESSMENT", "CONTRACTUAL_MECHANISM", "SECURITY_MEASURE", "OTHER"
    ]


class CrossBorderAssessmentPolicy(DecisionPolicy):
    obligation_policy_id: UUID
    transfer_legally_possible: ConditionPolicy
    non_transfer_condition: ConditionPolicy | None = None
    prerequisites: tuple[TransferPrerequisite, ...] = ()

    @model_validator(mode="after")
    def governed_scope(self):
        if not self.transfer_legally_possible.required_evidence:
            raise ValueError("transfer permission requires formal evidence")
        if self.non_transfer_condition and not self.non_transfer_condition.required_evidence:
            raise ValueError("non-transfer decision requires formal evidence")
        if len({p.requirement_id for p in self.prerequisites}) != len(self.prerequisites):
            raise ValueError("duplicate transfer prerequisite")
        return self


class DocumentRequirementEntry(LocalizedDisplayMetadata):
    entry_id: UUID
    document_type_code: StableDisplayCode
    name: str = Field(min_length=1, max_length=200)
    requirement_level: RequirementLevel
    trigger_obligation_entry_ids: tuple[UUID, ...] = ()
    trigger_path_action_codes: tuple[StableDisplayCode, ...] = ()
    cross_border_statuses: tuple[
        Literal[
            "DIRECT_TRANSFER_ALLOWED",
            "CONDITIONAL_TRANSFER_ALLOWED",
            "TRANSFER_NOT_ALLOWED_OR_LOCALIZATION_REQUIRED",
            "NOT_APPLICABLE",
        ],
        ...,
    ] = ()
    condition: ConditionPolicy | None = None
    template_binding_id: UUID | None = None

    @model_validator(mode="after")
    def legal_trigger(self):
        if not (
            self.trigger_obligation_entry_ids
            or self.trigger_path_action_codes
            or self.cross_border_statuses
        ):
            raise ValueError("a template is not a legal requirement trigger")
        if self.condition and not self.condition.required_evidence:
            raise ValueError("document legal condition requires evidence")
        return self


class DocumentRequirementPolicy(DecisionPolicy):
    obligation_policy_id: UUID
    cross_border_policy_id: UUID
    entries: tuple[DocumentRequirementEntry, ...] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def identities(self):
        if len({e.entry_id for e in self.entries}) != len(self.entries) or len(
            {e.document_type_code for e in self.entries}
        ) != len(self.entries):
            raise ValueError("ambiguous document requirement entry")
        return self


FORMAL_RESULT_POLICY_TYPES = {
    "CROSS_BORDER_ASSESSMENT_POLICY": CrossBorderAssessmentPolicy,
    "DOCUMENT_REQUIREMENT_POLICY": DocumentRequirementPolicy,
}
FORMAL_RESULT_POLICY_KINDS = frozenset(FORMAL_RESULT_POLICY_TYPES)
