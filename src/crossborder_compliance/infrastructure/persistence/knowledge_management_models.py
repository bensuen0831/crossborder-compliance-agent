"""Detail of canonical AdminChangeSet audit, not another taxonomy or audit platform."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin


class AdminOperationReceiptEntity(Base):
    __tablename__ = "admin_operation_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "change_set_id"],
            ["admin_change_sets.tenant_id", "admin_change_sets.change_set_id"],
            ondelete="RESTRICT",
            name="fk_admin_operation_change_scope",
        ),
        UniqueConstraint("change_set_id", name="uq_admin_operation_change"),
        CheckConstraint(
            "operation IN ('CREATE','EDIT_DRAFT','NEW_VERSION','SUBMIT_REVIEW',"
            "'APPROVE','REJECT','PUBLISH','DELETE_DRAFT','MERGE_PROPOSAL','DEACTIVATE',"
            "'REACTIVATE','ARCHIVE','HOLD_CREATE','HOLD_RELEASE','DOCUMENT_CREATE',"
            "'DOCUMENT_NEW_VERSION','DOCUMENT_EDIT_DRAFT','DOCUMENT_DELETE_DRAFT',"
            "'DOCUMENT_VALIDATE','DOCUMENT_SUBMIT_REVIEW','DOCUMENT_APPROVE','DOCUMENT_PUBLISH',"
            "'DOCUMENT_SUPERSEDE','DOCUMENT_EXPIRE','DOCUMENT_ARCHIVE','UPLOAD_CREATE',"
            "'UPLOAD_PART_ACK','UPLOAD_COMPLETE','UPLOAD_CANCEL','UPLOAD_RETRY','UPLOAD_SCAN_RESULT',"
            "'UPLOAD_ATTACH','BATCH_CREATE','BATCH_EXTRACT','BATCH_CONFIRM','BATCH_CANCEL','BATCH_RETRY')",
            name="ck_admin_operation_action",
        ),
    )
    receipt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    change_set_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    # Tombstone identity intentionally survives an eligible draft deletion.
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class KnowledgeManagementHoldEntity(TenantAuditMixin, Base):
    """Retention authority, separate from content versions and lifecycle."""

    __tablename__ = "knowledge_management_holds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "metadata_definition_id"],
            ["metadata_definitions.tenant_id", "metadata_definitions.definition_id"],
            ondelete="RESTRICT",
            name="fk_kb_hold_metadata_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_document_id"],
            ["knowledge_documents.tenant_id", "knowledge_documents.document_id"],
            ondelete="RESTRICT",
            name="fk_kb_hold_document_scope",
        ),
        CheckConstraint(
            "(metadata_definition_id IS NOT NULL AND knowledge_document_id IS NULL) OR "
            "(metadata_definition_id IS NULL AND knowledge_document_id IS NOT NULL)",
            name="ck_kb_hold_resource",
        ),
        CheckConstraint(
            "(released_at IS NULL AND released_by IS NULL) OR "
            "(released_at IS NOT NULL AND released_by IS NOT NULL)",
            name="ck_kb_hold_release_actor",
        ),
    )
    hold_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    metadata_definition_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    knowledge_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[str | None] = mapped_column(String(160), nullable=True)


class KnowledgeDocumentLabelEntity(TenantAuditMixin, Base):
    """Exact metadata classification component of canonical KnowledgeDocumentVersion."""

    __tablename__ = "knowledge_document_labels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_version_id"],
            [
                "knowledge_document_versions.tenant_id",
                "knowledge_document_versions.knowledge_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_label_version_scope",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "definition_id", "metadata_version_id"],
            [
                "metadata_versions.tenant_id",
                "metadata_versions.definition_id",
                "metadata_versions.version_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_label_metadata_scope",
        ),
        UniqueConstraint(
            "tenant_id",
            "knowledge_version_id",
            "kind",
            "definition_id",
            name="uq_knowledge_version_label",
        ),
        Index(
            "ix_knowledge_document_labels_facets",
            "tenant_id",
            "kind",
            "definition_id",
            "knowledge_version_id",
        ),
        CheckConstraint(
            "kind IN ('JURISDICTION_CONFIG','REGULATION_CATEGORY','RESEARCH_TOPIC',"
            "'LANGUAGE','ISSUING_AUTHORITY','KNOWLEDGE_SOURCE_TYPE','LEGAL_EFFECT')",
            name="ck_knowledge_label_kind",
        ),
    )
    label_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    knowledge_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
