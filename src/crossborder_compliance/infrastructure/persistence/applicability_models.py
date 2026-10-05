"""Only the missing authoritative applicability result, referencing canonical stores."""

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin


class RegulationApplicabilityResultEntity(TenantAuditMixin, Base):
    __tablename__ = "regulation_applicability_results"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "analysis_snapshot_id",
            "subject_type",
            "subject_id",
            "jurisdiction_id",
            "applicability_config_version_id",
            "retrieval_run_id",
            name="uq_applicability_resolution",
        ),
        CheckConstraint(
            "subject_type IN ('DATA_ITEM','DATA_FLOW','SCENARIO')", name="ck_applicability_subject"
        ),
        CheckConstraint(
            "applicability_status IN"
            " ('APPLICABLE','NOT_APPLICABLE','CONDITIONALLY_APPLICABLE',"
            "'INSUFFICIENT_EVIDENCE','CONFLICTED','REVIEW_REQUIRED')",
            name="ck_applicability_status",
        ),
        Index("ix_applicability_snapshot", "tenant_id", "project_id", "analysis_snapshot_id"),
    )
    applicability_result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    analysis_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_snapshots.analysis_snapshot_id"), nullable=False
    )
    jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.jurisdiction_id"), nullable=False
    )
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    regulation_version_ref: Mapped[str] = mapped_column(
        ForeignKey("knowledge_document_versions.knowledge_version_id"), nullable=False
    )
    applicability_config_version_id: Mapped[str] = mapped_column(
        ForeignKey("metadata_versions.version_id"), nullable=False
    )
    country_profile_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("metadata_versions.version_id"), nullable=True
    )
    retrieval_run_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_runs.retrieval_run_id"), nullable=False
    )
    owner_actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    applicability_status: Mapped[str] = mapped_column(String(50), nullable=False)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
