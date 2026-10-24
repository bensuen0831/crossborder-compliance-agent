"""Original attachment ingestion request. Parser/policy/actor pins are server owned."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from crossborder_compliance.domain.knowledge_management import ManagementRequest
from crossborder_compliance.interfaces.api.knowledge_schemas import BindingRequestDTO, RunDTO


class KnowledgeBinaryIngestionRequest(ManagementRequest):
    binary_upload_session_id: UUID
    expected_record_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    bindings: tuple[BindingRequestDTO, ...] = Field(default=(), max_length=1000)
    strategy: Literal[
        "STRUCTURE_AWARE", "ARTICLE", "SECTION", "PARAGRAPH", "TABLE", "SLIDING_WINDOW"
    ] = "STRUCTURE_AWARE"


class KnowledgeBinaryIngestionView(RunDTO):
    batch_id: UUID
