"""Phase 1B domain foundation and PostgreSQL persistence.

Revision ID: 0002_phase1b
Revises: 0001_phase1a

The Domain migration owns only Domain/Application persistence tables.
It MUST NOT create, alter, rename, inspect, or drop LangGraph checkpoint internal tables.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from crossborder_compliance.infrastructure.persistence.models import Base

revision = "0002_phase1b"
down_revision = "0001_phase1a"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "tenants",
    "organizations",
    "jurisdictions",
    "jurisdiction_relations",
    "projects",
    "project_versions",
    "legal_entities",
    "project_parties",
    "party_role_assignments",
    "contracts",
    "contract_party_links",
    "documents",
    "document_versions",
    "source_trace_refs",
    "document_parse_runs",
    "data_items",
    "data_item_groups",
    "data_item_group_members",
    "data_flow_nodes",
    "data_flow_edges",
    "data_item_flow_links",
    "data_item_product_links",
    "data_flow_party_links",
    "compliance_path_steps",
    "path_step_responsible_parties",
    "classification_schemes",
    "classification_categories",
    "classification_levels",
    "classification_results",
    "classification_result_categories",
    "evidence_references",
    "citations",
    "regulatory_structure_nodes",
    "rule_hits",
    "legal_basis_items",
    "legal_basis_rule_hit_links",
    "legal_basis_evidence_links",
    "analysis_stage_results",
    "review_decisions",
    "channel_contexts",
    "interaction_sessions",
    "conversation_threads",
    "conversation_messages",
]


def _add_runtime_foundation_columns() -> None:
    op.add_column(
        "analysis_snapshots",
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "analysis_snapshots",
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
    )
    op.add_column(
        "analysis_snapshots",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.add_column(
        "workflow_runs",
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.add_column("workflow_node_runs", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.execute(
        """
        UPDATE workflow_node_runs n
        SET tenant_id = w.tenant_id
        FROM workflow_runs w
        WHERE n.workflow_run_id = w.workflow_run_id
        """
    )
    op.alter_column("workflow_node_runs", "tenant_id", nullable=False)
    op.create_index(
        "ix_workflow_node_runs_tenant_id",
        "workflow_node_runs",
        ["tenant_id"],
        unique=False,
    )
    op.add_column(
        "workflow_node_runs",
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "workflow_node_runs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.add_column(
        "review_tasks",
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "review_tasks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.add_column(
        "execution_idempotency_records",
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "execution_idempotency_records",
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
    )
    op.add_column(
        "execution_idempotency_records",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def upgrade() -> None:
    _add_runtime_foundation_columns()
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    # Reverse dependency order; destructive downgrade is for local/dev only.
    for name in reversed(NEW_TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)

    op.drop_column("execution_idempotency_records", "updated_at")
    op.drop_column("execution_idempotency_records", "status")
    op.drop_column("execution_idempotency_records", "record_version")

    op.drop_column("review_tasks", "updated_at")
    op.drop_column("review_tasks", "record_version")

    op.drop_column("workflow_node_runs", "updated_at")
    op.drop_column("workflow_node_runs", "record_version")
    op.drop_index("ix_workflow_node_runs_tenant_id", table_name="workflow_node_runs")
    op.drop_column("workflow_node_runs", "tenant_id")

    op.drop_column("workflow_runs", "record_version")

    op.drop_column("analysis_snapshots", "updated_at")
    op.drop_column("analysis_snapshots", "status")
    op.drop_column("analysis_snapshots", "record_version")
