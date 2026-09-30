"""Phase 1A runtime-owned domain tables only.

Revision ID: 0001_phase1a

IMPORTANT: This migration deliberately does NOT create or alter LangGraph checkpointer
internal tables. Those are created/upgraded by PostgresSaver.setup() / official tooling.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_phase1a"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("analysis_snapshots",
        sa.Column("analysis_snapshot_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("project_version_id", sa.String(36), nullable=False),
        sa.Column("snapshot_version", sa.String(50), nullable=False),
        sa.Column("analysis_as_of_date", sa.Date(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analysis_snapshots_tenant", "analysis_snapshots", ["tenant_id"])

    op.create_table("workflow_runs",
        sa.Column("workflow_run_id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("analysis_snapshot_id", sa.String(36), sa.ForeignKey("analysis_snapshots.analysis_snapshot_id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("graph_definition_version", sa.String(50), nullable=False),
        sa.Column("langgraph_runtime_version", sa.String(50), nullable=False),
        sa.Column("checkpointer_version", sa.String(50), nullable=False),
        sa.Column("state_schema_version", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_runs_tenant_status", "workflow_runs", ["tenant_id", "status"])

    op.create_table("workflow_node_runs",
        sa.Column("workflow_node_run_id", sa.String(36), primary_key=True),
        sa.Column("workflow_run_id", sa.String(36), sa.ForeignKey("workflow_runs.workflow_run_id"), nullable=False),
        sa.Column("node_code", sa.String(120), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_run_id", "node_code", "attempt_no", name="uq_workflow_node_attempt"),
    )

    op.create_table("review_tasks",
        sa.Column("review_id", sa.String(36), primary_key=True),
        sa.Column("workflow_run_id", sa.String(36), sa.ForeignKey("workflow_runs.workflow_run_id"), nullable=False),
        sa.Column("thread_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("review_type", sa.String(120), nullable=False),
        sa.Column("object_type", sa.String(120), nullable=False),
        sa.Column("object_id", sa.String(120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_review_idempotency"),
    )

    op.create_table("workflow_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("workflow_run_id", sa.String(36), sa.ForeignKey("workflow_runs.workflow_run_id"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("node_code", sa.String(120), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_events_run_time", "workflow_events", ["workflow_run_id", "occurred_at"])

    op.create_table("audit_events",
        sa.Column("audit_event_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("workflow_run_id", sa.String(36), nullable=False),
        sa.Column("analysis_snapshot_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table("execution_idempotency_records",
        sa.Column("execution_idempotency_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("workflow_run_id", sa.String(36), nullable=False),
        sa.Column("scope", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("result_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "scope", "idempotency_key", name="uq_execution_idempotency"),
    )

    op.create_table("api_idempotency_records",
        sa.Column("api_idempotency_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("api_client_id", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(128), nullable=False),
        sa.Column("response_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("api_client_id", "idempotency_key", name="uq_api_idempotency"),
    )

def downgrade() -> None:
    for table in ["api_idempotency_records", "execution_idempotency_records", "audit_events", "workflow_events", "review_tasks", "workflow_node_runs", "workflow_runs", "analysis_snapshots"]:
        op.drop_table(table)
