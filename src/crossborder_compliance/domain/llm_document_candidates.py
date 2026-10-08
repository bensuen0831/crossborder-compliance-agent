"""Bounded, source-addressed candidate output. No formal-result fields."""

from uuid import UUID

from pydantic import Field

from crossborder_compliance.domain.knowledge import Contract


class TracedCandidate(Contract):
    source_node_id: UUID
    confidence: float = Field(ge=0, le=1)


class FactExtraction(TracedCandidate):
    fact_type: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=4000)


class ItemExtraction(TracedCandidate):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)


class FlowNodeExtraction(TracedCandidate):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)


class FlowEdgeExtraction(TracedCandidate):
    source_key: str = Field(min_length=1, max_length=80)
    destination_key: str = Field(min_length=1, max_length=80)


class DocumentCandidateExtraction(Contract):
    facts: tuple[FactExtraction, ...] = Field(max_length=128)
    items: tuple[ItemExtraction, ...] = Field(max_length=128)
    nodes: tuple[FlowNodeExtraction, ...] = Field(max_length=128)
    edges: tuple[FlowEdgeExtraction, ...] = Field(max_length=128)
