from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from crossborder_compliance.domain.contracts import WorkflowEventDTO


@dataclass(frozen=True)
class AuthoritativeWorkflowContext:
    workflow_run_id: UUID
    thread_id: str
    tenant_id: UUID
    analysis_snapshot_id: UUID
    status: str
    graph_definition_version: str
    langgraph_runtime_version: str
    checkpointer_version: str
    state_schema_version: str
    pending_review_ids: tuple[UUID, ...]


class RuntimeOperationsPort(Protocol):
    def load_authoritative_workflow_context(
        self, workflow_run_id: UUID
    ) -> AuthoritativeWorkflowContext: ...
    def ensure_review_task(
        self, *, workflow_run_id: UUID, tenant_id: UUID, idempotency_key: str
    ) -> UUID: ...
    def resolve_review(self, review_id: UUID, decision: dict[str, object]) -> None: ...
    def record_event(self, tenant_id: UUID, event: WorkflowEventDTO) -> None: ...
    def mark_review_required(self, workflow_run_id: UUID) -> None: ...
    def mark_resumed(self, workflow_run_id: UUID) -> None: ...
    def mark_completed(
        self, workflow_run_id: UUID, tenant_id: UUID, snapshot_id: UUID
    ) -> None: ...
    def status(self, workflow_run_id: UUID) -> str: ...
