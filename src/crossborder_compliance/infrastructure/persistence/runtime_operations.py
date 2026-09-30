from __future__ import annotations

from uuid import UUID

from crossborder_compliance.application.ports import (
    AuthoritativeWorkflowContext,
    RuntimeOperationsPort,
)
from crossborder_compliance.domain.contracts import WorkflowEventDTO
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository


class SqlRuntimeOperations(RuntimeOperationsPort):
    def __init__(self, repository: RuntimeRepository):
        self._repository = repository

    def load_authoritative_workflow_context(
        self, workflow_run_id: UUID
    ) -> AuthoritativeWorkflowContext:
        return self._repository.authoritative_workflow_context(workflow_run_id)

    def ensure_review_task(
        self, *, workflow_run_id: UUID, tenant_id: UUID, idempotency_key: str
    ) -> UUID:
        return self._repository.ensure_review_task(
            workflow_run_id=workflow_run_id,
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )

    def resolve_review(self, review_id: UUID, decision: dict[str, object]) -> None:
        self._repository.resolve_review(review_id, decision)

    def record_event(self, tenant_id: UUID, event: WorkflowEventDTO) -> None:
        self._repository.record_event(tenant_id, event)

    def mark_review_required(self, workflow_run_id: UUID) -> None:
        self._repository.set_status(workflow_run_id, "REVIEW_REQUIRED")

    def mark_resumed(self, workflow_run_id: UUID) -> None:
        self._repository.set_status(workflow_run_id, "RUNNING")

    def mark_completed(
        self, workflow_run_id: UUID, tenant_id: UUID, snapshot_id: UUID
    ) -> None:
        self._repository.mark_completed(workflow_run_id, tenant_id, snapshot_id)

    def status(self, workflow_run_id: UUID) -> str:
        return self._repository.status(workflow_run_id)
