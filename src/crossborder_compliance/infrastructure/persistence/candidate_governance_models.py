"""Pre-formal authorization identities; existing candidates remain authoritative."""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, utcnow


class CandidatePreparationEntity(Base):
    __tablename__ = "candidate_preparations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "candidate_preparation_id", name="uq_candidate_preparation_tenant"
        ),
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "project_version_id",
            "candidate_preparation_id",
            name="uq_candidate_preparation_scope",
        ),
        Index(
            "uq_candidate_preparation_universe",
            "tenant_id",
            "project_version_id",
            "input_universe_digest",
            "configuration_digest",
            unique=True,
            postgresql_where=text("status IN ('PREPARING','COMPLETED')"),
        ),
        CheckConstraint(
            "status IN ('PREPARING','COMPLETED','FAILED')", name="ck_candidate_preparation_status"
        ),
        CheckConstraint(
            "status <> 'COMPLETED' OR (candidate_universe_digest IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_candidate_preparation_complete",
        ),
        Index("ix_candidate_preparation_draft", "tenant_id", "project_id", "project_version_id"),
    )
    candidate_preparation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False
    )
    project_version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.project_version_id", ondelete="RESTRICT"), nullable=False
    )
    analysis_as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    input_universe_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_universe_digest: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="PREPARING", server_default="PREPARING"
    )
    record_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)


class CandidatePreparationDocumentPinEntity(Base):
    __tablename__ = "candidate_preparation_document_pins"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "candidate_preparation_id"],
            ["candidate_preparations.tenant_id", "candidate_preparations.candidate_preparation_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "candidate_preparation_id",
            "document_version_id",
            name="uq_candidate_preparation_document",
        ),
    )
    preparation_document_pin_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_preparation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.document_version_id", ondelete="RESTRICT"), nullable=False
    )
    parse_run_id: Mapped[str] = mapped_column(
        ForeignKey("document_parse_runs.document_parse_run_id", ondelete="RESTRICT"), nullable=False
    )


class CandidatePreparationRegistryPinEntity(Base):
    __tablename__ = "candidate_preparation_registry_pins"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "candidate_preparation_id"],
            ["candidate_preparations.tenant_id", "candidate_preparations.candidate_preparation_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "candidate_preparation_id",
            "pin_type",
            "logical_key",
            name="uq_candidate_preparation_registry_pin",
        ),
    )
    preparation_registry_pin_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_preparation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    pin_type: Mapped[str] = mapped_column(String(100), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(160), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)


class CandidatePreparationCandidateEntity(Base):
    __tablename__ = "candidate_preparation_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "candidate_preparation_id"],
            ["candidate_preparations.tenant_id", "candidate_preparations.candidate_preparation_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "candidate_preparation_id",
            "preparation_candidate_id",
            name="uq_preparation_candidate_scope",
        ),
        UniqueConstraint(
            "tenant_id",
            "candidate_preparation_id",
            "candidate_type",
            "candidate_id",
            name="uq_preparation_candidate_identity",
        ),
        CheckConstraint(
            "candidate_type IN ('BUSINESS_FACT','DATA_ITEM','DATA_FLOW_NODE','DATA_FLOW_EDGE')",
            name="ck_preparation_candidate_type",
        ),
        CheckConstraint(
            "candidate_origin IN ('LLM_STRUCTURED_OUTPUT','NATIVE_DETERMINISTIC','DOCUMENT_DERIVED')",
            name="ck_preparation_candidate_origin",
        ),
    )
    preparation_candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_preparation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(40), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_origin: Mapped[str] = mapped_column(String(40), nullable=False)
    candidate_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_request_id: Mapped[str | None] = mapped_column(String(36))
    llm_invocation_group_id: Mapped[str | None] = mapped_column(String(36))


class CandidateDecisionSetEntity(Base):
    __tablename__ = "candidate_decision_sets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "project_version_id", "candidate_preparation_id"],
            [
                "candidate_preparations.tenant_id",
                "candidate_preparations.project_id",
                "candidate_preparations.project_version_id",
                "candidate_preparations.candidate_preparation_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "candidate_preparation_id",
            "candidate_decision_set_id",
            name="uq_candidate_decision_set_scope",
        ),
        Index("ix_candidate_decision_set_draft", "tenant_id", "project_id", "project_version_id"),
    )
    candidate_decision_set_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    project_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_preparation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_universe_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(160), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class CandidateDecisionEntity(Base):
    __tablename__ = "candidate_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "candidate_preparation_id", "candidate_decision_set_id"],
            [
                "candidate_decision_sets.tenant_id",
                "candidate_decision_sets.candidate_preparation_id",
                "candidate_decision_sets.candidate_decision_set_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "candidate_preparation_id", "preparation_candidate_id"],
            [
                "candidate_preparation_candidates.tenant_id",
                "candidate_preparation_candidates.candidate_preparation_id",
                "candidate_preparation_candidates.preparation_candidate_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "candidate_decision_set_id",
            "preparation_candidate_id",
            name="uq_candidate_decision_once",
        ),
        CheckConstraint(
            "action IN ('ACCEPT','REJECT','EDIT')", name="ck_candidate_decision_action"
        ),
        CheckConstraint(
            "(action = 'EDIT' AND edited_payload_json IS NOT NULL) OR (action <> 'EDIT' AND edited_payload_json IS NULL)",
            name="ck_candidate_decision_edit",
        ),
    )
    candidate_decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_preparation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_decision_set_id: Mapped[str] = mapped_column(String(36), nullable=False)
    preparation_candidate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    edited_payload_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    decision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
