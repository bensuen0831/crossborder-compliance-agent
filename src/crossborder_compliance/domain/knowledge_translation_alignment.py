"""Human supplied translation alignment, over existing versioned knowledge content."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from crossborder_compliance.domain.knowledge_management import ManagementRequest


class ClauseTranslationPair(ManagementRequest):
    source_node_id: UUID
    target_node_id: UUID


class CreateTranslationAlignment(ManagementRequest):
    source_version_id: UUID
    target_version_id: UUID
    expected_source_record_version: int = Field(ge=1)
    expected_target_record_version: int = Field(ge=1)
    # This operation links already imported human translation. It does not
    # invoke an AI model or certify an official translation/legal evidence.
    translation_method: Literal["HUMAN"] = "HUMAN"
    pairs: tuple[ClauseTranslationPair, ...] = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def unique_pairs(self):
        identities = [(p.source_node_id, p.target_node_id) for p in self.pairs]
        if len(identities) != len(set(identities)):
            raise ValueError("DUPLICATE_TRANSLATION_ALIGNMENT")
        if self.source_version_id == self.target_version_id:
            raise ValueError("TRANSLATION_REQUIRES_DISTINCT_VERSIONS")
        return self


class ReviewTranslationAlignment(ManagementRequest):
    expected_record_version: int = Field(ge=1)
    action: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=1, max_length=2048)
