from __future__ import annotations
from uuid import UUID
from crossborder_compliance.application.ports import RuntimeOperationsPort
from crossborder_compliance.domain.contracts import WorkflowEventDTO
from crossborder_compliance.infrastructure.persistence.repositories import RuntimeRepository

class SqlRuntimeOperations(RuntimeOperationsPort):
    def __init__(self, repository: RuntimeRepository): self._repository=repository
    def ensure_review_task(self, *, workflow_run_id: UUID, tenant_id: UUID, idempotency_key: str,
                           review_type: str = "PHASE1A_SMOKE_REVIEW", reason: str = "Verify durable interrupt/resume") -> UUID:
        return self._repository.ensure_review_task(workflow_run_id=workflow_run_id,tenant_id=tenant_id,idempotency_key=idempotency_key,review_type=review_type,reason=reason)
    def resolve_review(self, review_id: UUID, decision: dict[str, object]) -> None: self._repository.resolve_review(review_id,decision)
    def record_event(self, tenant_id: UUID, event: WorkflowEventDTO) -> None: self._repository.record_event(tenant_id,event)
    def mark_review_required(self, workflow_run_id: UUID) -> None: self._repository.set_status(workflow_run_id,"REVIEW_REQUIRED")
    def mark_resumed(self, workflow_run_id: UUID) -> None: self._repository.set_status(workflow_run_id,"RUNNING")
    def mark_completed(self, workflow_run_id: UUID, tenant_id: UUID, snapshot_id: UUID) -> None: self._repository.mark_completed(workflow_run_id,tenant_id,snapshot_id)
    def status(self, workflow_run_id: UUID) -> str: return self._repository.status(workflow_run_id)
    def set_status(self, workflow_run_id: UUID, status: str) -> None:
        if status not in {"WAITING", "RUNNING", "COMPLETED", "WARNING", "REVIEW_REQUIRED", "FAILED"}:
            raise ValueError("unsupported workflow status")
        self._repository.set_status(workflow_run_id, status)
    def workflow_events(self, workflow_run_id: UUID, tenant_id: UUID) -> list[WorkflowEventDTO]:
        return self._repository.workflow_events(workflow_run_id, tenant_id)
