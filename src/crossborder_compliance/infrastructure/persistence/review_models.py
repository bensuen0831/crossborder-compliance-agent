"""Typed lineage of governed corrections; canonical input tables retain values."""

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin


class ReviewCorrectionEntity(TenantAuditMixin, Base):
    __tablename__ = "review_corrections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "successor_snapshot_id", name="uq_review_successor_snapshot"),
        CheckConstraint(
            "correction_type IN ('SELECT_BUSINESS_FACT','SELECT_PRODUCT_SCOPE','CLARIFY_INTAKE')",
            name="ck_review_correction_type",
        ),
    )
    correction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_review_id: Mapped[str] = mapped_column(
        ForeignKey("review_tasks.review_id"), nullable=False
    )
    source_workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.workflow_run_id"), nullable=False
    )
    source_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_snapshots.analysis_snapshot_id"), nullable=False
    )
    source_conflict_id: Mapped[str | None] = mapped_column(
        ForeignKey("context_conflicts.conflict_id"), nullable=True
    )
    successor_project_version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.project_version_id"), nullable=False
    )
    successor_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "analysis_snapshots.analysis_snapshot_id", deferrable=True, initially="DEFERRED"
        ),
        nullable=False,
    )
    successor_workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.workflow_run_id", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    correction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    selected_fact_id: Mapped[str | None] = mapped_column(
        ForeignKey("business_facts.fact_id"), nullable=True
    )
    selected_product_ids_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    submitted_by: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(4096), nullable=True)
