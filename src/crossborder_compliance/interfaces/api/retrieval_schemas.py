from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from crossborder_compliance.domain.retrieval import (
    RAGContextPack,
    RetrievalStatistics,
    RetrievalTrace,
)


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrievalRequestDTO(DTO):
    analysis_snapshot_id: UUID
    policy_id: UUID
    query_text: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=120)
    subject_type: Literal["PROJECT", "DATA_ITEM", "DATA_FLOW"] = "PROJECT"
    subject_id: UUID | None = None
    languages: tuple[str, ...] = ()


class RetrievalResponseDTO(DTO):
    retrieval_run_id: str
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    query: dict
    traces: tuple[RetrievalTrace, ...]
    statistics: RetrievalStatistics
    record_version: int
    rag_context_pack: RAGContextPack | None


class PolicyRequestDTO(DTO):
    policy_id: UUID | None = None
    parameters: dict


class PolicyResponseDTO(DTO):
    policy_id: str
    policy_version_id: str
    version: int
    lifecycle: str
    record_version: int
    parameters: dict


class ExpectedDTO(DTO):
    expected_record_version: int = Field(ge=1)


class WikiRequestDTO(DTO):
    title: str = Field(min_length=1, max_length=250)
    knowledge_version_ids: tuple[UUID, ...]


class NavigationResponseDTO(DTO):
    result: dict


class GraphRequestDTO(DTO):
    parameters: dict
