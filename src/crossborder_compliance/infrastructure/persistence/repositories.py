from __future__ import annotations
from datetime import date, datetime, timezone
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from crossborder_compliance.domain.contracts import WorkflowEventDTO
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity, AuditEventEntity, ReviewTaskEntity, WorkflowEventEntity, WorkflowRunEntity,
)

def utcnow(): return datetime.now(timezone.utc)

class RuntimeRepository:
    def __init__(self, session_factory: sessionmaker): self._sessions=session_factory

    def _audit_id(self, workflow_run_id: UUID, event_key: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"audit:{workflow_run_id}:{event_key}"))

    def create_snapshot_and_run(self, *, snapshot_id: UUID, workflow_run_id: UUID, tenant_id: UUID,
                                project_version_id: UUID, graph_definition_version: str,
                                langgraph_runtime_version: str, checkpointer_version: str,
                                state_schema_version: str) -> None:
        with self._sessions() as s, s.begin():
            s.add(AnalysisSnapshotEntity(analysis_snapshot_id=str(snapshot_id),tenant_id=str(tenant_id),project_version_id=str(project_version_id),
                snapshot_version="1.0",analysis_as_of_date=date.today(),provenance_json={"source":"phase1a-smoke","immutable":True}))
            s.add(WorkflowRunEntity(workflow_run_id=str(workflow_run_id),thread_id=str(workflow_run_id),tenant_id=str(tenant_id),
                analysis_snapshot_id=str(snapshot_id),status="RUNNING",graph_definition_version=graph_definition_version,
                langgraph_runtime_version=langgraph_runtime_version,checkpointer_version=checkpointer_version,state_schema_version=state_schema_version))
            s.add(AuditEventEntity(audit_event_id=self._audit_id(workflow_run_id,"workflow-created"),tenant_id=str(tenant_id),workflow_run_id=str(workflow_run_id),
                analysis_snapshot_id=str(snapshot_id),event_type="WORKFLOW_CREATED",provenance_json={"thread_id":str(workflow_run_id),"snapshot_id":str(snapshot_id)}))

    def ensure_review_task(self, *, workflow_run_id: UUID, tenant_id: UUID, idempotency_key: str,
                           review_type: str = "PHASE1A_SMOKE_REVIEW", reason: str = "Verify durable interrupt/resume") -> UUID:
        with self._sessions() as s:
            existing=s.scalar(select(ReviewTaskEntity).where(ReviewTaskEntity.tenant_id==str(tenant_id),ReviewTaskEntity.idempotency_key==idempotency_key))
            if existing: return UUID(existing.review_id)
            review_id=uuid4()
            s.add(ReviewTaskEntity(review_id=str(review_id),workflow_run_id=str(workflow_run_id),thread_id=str(workflow_run_id),tenant_id=str(tenant_id),
                review_type=review_type,object_type="WORKFLOW_RUN",object_id=str(workflow_run_id),reason=reason,
                status="PENDING",idempotency_key=idempotency_key))
            try:
                s.commit()
                return review_id
            except IntegrityError:
                s.rollback()
                existing=s.scalar(select(ReviewTaskEntity).where(ReviewTaskEntity.tenant_id==str(tenant_id),ReviewTaskEntity.idempotency_key==idempotency_key))
                if existing is None: raise
                return UUID(existing.review_id)

    def resolve_review(self, review_id: UUID, decision: dict[str, object]) -> None:
        with self._sessions() as s, s.begin():
            row=s.get(ReviewTaskEntity,str(review_id))
            if row:
                row.status="APPROVED" if decision.get("decision") in {"APPROVE","APPROVED"} else "REJECTED"
                row.decision_json=decision; row.resolved_at=utcnow()

    def record_event(self, tenant_id: UUID, event: WorkflowEventDTO) -> None:
        with self._sessions() as s, s.begin():
            if s.get(WorkflowEventEntity,str(event.event_id)) is not None:
                return
            s.add(WorkflowEventEntity(event_id=str(event.event_id),workflow_run_id=str(event.workflow_run_id),tenant_id=str(tenant_id),
                event_type=event.event_type.value,node_code=event.node_code,payload_json=event.payload,occurred_at=event.timestamp))

    def set_status(self, workflow_run_id: UUID, status: str) -> None:
        with self._sessions() as s, s.begin():
            row=s.get(WorkflowRunEntity,str(workflow_run_id))
            if row is None: raise LookupError(f"workflow run not found: {workflow_run_id}")
            row.status=status; row.updated_at=utcnow()

    def mark_completed(self, workflow_run_id: UUID, tenant_id: UUID, snapshot_id: UUID) -> None:
        with self._sessions() as s, s.begin():
            row=s.get(WorkflowRunEntity,str(workflow_run_id))
            if row is None: raise LookupError(f"workflow run not found: {workflow_run_id}")
            row.status="COMPLETED"; row.updated_at=utcnow()
            audit_id=self._audit_id(workflow_run_id,"workflow-completed")
            if s.get(AuditEventEntity,audit_id) is None:
                s.add(AuditEventEntity(audit_event_id=audit_id,tenant_id=str(tenant_id),workflow_run_id=str(workflow_run_id),analysis_snapshot_id=str(snapshot_id),
                    event_type="WORKFLOW_COMPLETED",provenance_json={"thread_id":str(workflow_run_id),"snapshot_id":str(snapshot_id)}))

    def status(self, workflow_run_id: UUID) -> str:
        with self._sessions() as s:
            row=s.get(WorkflowRunEntity,str(workflow_run_id)); return row.status if row else "NOT_FOUND"

    def review_task_count(self, workflow_run_id: UUID) -> int:
        with self._sessions() as s:
            return int(s.scalar(select(func.count()).select_from(ReviewTaskEntity).where(ReviewTaskEntity.workflow_run_id==str(workflow_run_id))) or 0)

    def canonical_event_types(self, workflow_run_id: UUID) -> list[str]:
        with self._sessions() as s:
            return list(s.scalars(select(WorkflowEventEntity.event_type).where(WorkflowEventEntity.workflow_run_id==str(workflow_run_id)).order_by(WorkflowEventEntity.occurred_at)))

    def workflow_events(self, workflow_run_id: UUID, tenant_id: UUID) -> list[WorkflowEventDTO]:
        from crossborder_compliance.domain.contracts import ProvenanceDTO, WorkflowEventType

        with self._sessions() as session:
            rows = session.scalars(select(WorkflowEventEntity).where(
                WorkflowEventEntity.workflow_run_id == str(workflow_run_id),
                WorkflowEventEntity.tenant_id == str(tenant_id),
            ).order_by(WorkflowEventEntity.occurred_at, WorkflowEventEntity.event_id))
            return [WorkflowEventDTO(
                event_id=UUID(row.event_id), workflow_run_id=workflow_run_id,
                event_type=WorkflowEventType(row.event_type), node_code=row.node_code,
                status=row.payload_json.get("status"), payload=row.payload_json,
                timestamp=row.occurred_at, request_id=row.payload_json.get("request_id", "persisted"),
                provenance=ProvenanceDTO(source_type="workflow_runtime", source_ref=str(workflow_run_id),
                    generated_by="CanonicalWorkflowEventReader"),
            ) for row in rows]
