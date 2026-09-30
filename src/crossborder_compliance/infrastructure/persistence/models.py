from __future__ import annotations
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass
def utcnow() -> datetime: return datetime.now(timezone.utc)

class AnalysisSnapshotEntity(Base):
    __tablename__="analysis_snapshots"
    analysis_snapshot_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    project_version_id:Mapped[str]=mapped_column(String(36),nullable=False)
    snapshot_version:Mapped[str]=mapped_column(String(50),nullable=False)
    analysis_as_of_date:Mapped[date]=mapped_column(Date,nullable=False)
    provenance_json:Mapped[dict]=mapped_column(JSON,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class WorkflowRunEntity(Base):
    __tablename__="workflow_runs"
    __table_args__=(Index("ix_workflow_runs_tenant_status","tenant_id","status"),)
    workflow_run_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    thread_id:Mapped[str]=mapped_column(String(36),unique=True,nullable=False)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False)
    analysis_snapshot_id:Mapped[str]=mapped_column(ForeignKey("analysis_snapshots.analysis_snapshot_id"),nullable=False)
    status:Mapped[str]=mapped_column(String(40),nullable=False)
    graph_definition_version:Mapped[str]=mapped_column(String(50),nullable=False)
    langgraph_runtime_version:Mapped[str]=mapped_column(String(50),nullable=False)
    checkpointer_version:Mapped[str]=mapped_column(String(50),nullable=False)
    state_schema_version:Mapped[str]=mapped_column(String(50),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow,nullable=False)

class WorkflowNodeRunEntity(Base):
    __tablename__="workflow_node_runs"
    __table_args__=(UniqueConstraint("workflow_run_id","node_code","attempt_no",name="uq_workflow_node_attempt"),)
    workflow_node_run_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    workflow_run_id:Mapped[str]=mapped_column(ForeignKey("workflow_runs.workflow_run_id"),nullable=False)
    node_code:Mapped[str]=mapped_column(String(120),nullable=False)
    attempt_no:Mapped[int]=mapped_column(Integer,nullable=False)
    status:Mapped[str]=mapped_column(String(40),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class ReviewTaskEntity(Base):
    __tablename__="review_tasks"
    __table_args__=(UniqueConstraint("tenant_id","idempotency_key",name="uq_review_idempotency"),)
    review_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    workflow_run_id:Mapped[str]=mapped_column(ForeignKey("workflow_runs.workflow_run_id"),nullable=False)
    thread_id:Mapped[str]=mapped_column(String(36),nullable=False)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False)
    review_type:Mapped[str]=mapped_column(String(120),nullable=False)
    object_type:Mapped[str]=mapped_column(String(120),nullable=False)
    object_id:Mapped[str]=mapped_column(String(120),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    status:Mapped[str]=mapped_column(String(40),nullable=False)
    idempotency_key:Mapped[str]=mapped_column(String(255),nullable=False)
    decision_json:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class WorkflowEventEntity(Base):
    __tablename__="workflow_events"
    event_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    workflow_run_id:Mapped[str]=mapped_column(ForeignKey("workflow_runs.workflow_run_id"),nullable=False,index=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False)
    event_type:Mapped[str]=mapped_column(String(80),nullable=False)
    node_code:Mapped[str|None]=mapped_column(String(120),nullable=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False)
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class AuditEventEntity(Base):
    __tablename__="audit_events"
    audit_event_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    workflow_run_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    analysis_snapshot_id:Mapped[str]=mapped_column(String(36),nullable=False)
    event_type:Mapped[str]=mapped_column(String(120),nullable=False)
    provenance_json:Mapped[dict]=mapped_column(JSON,nullable=False)
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class ExecutionIdempotencyEntity(Base):
    __tablename__="execution_idempotency_records"
    __table_args__=(UniqueConstraint("tenant_id","scope","idempotency_key",name="uq_execution_idempotency"),)
    execution_idempotency_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False)
    workflow_run_id:Mapped[str]=mapped_column(String(36),nullable=False)
    scope:Mapped[str]=mapped_column(String(120),nullable=False)
    idempotency_key:Mapped[str]=mapped_column(String(255),nullable=False)
    result_ref:Mapped[str|None]=mapped_column(String(255),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class ApiIdempotencyEntity(Base):
    __tablename__="api_idempotency_records"
    __table_args__=(UniqueConstraint("api_client_id","idempotency_key",name="uq_api_idempotency"),)
    api_idempotency_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False)
    api_client_id:Mapped[str]=mapped_column(String(120),nullable=False)
    idempotency_key:Mapped[str]=mapped_column(String(255),nullable=False)
    request_hash:Mapped[str]=mapped_column(String(128),nullable=False)
    response_ref:Mapped[str|None]=mapped_column(String(255),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)
