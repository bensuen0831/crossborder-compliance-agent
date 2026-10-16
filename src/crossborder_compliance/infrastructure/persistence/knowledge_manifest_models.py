"""Immutable catalogue preview receipts under canonical import batches and uploads."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base


class KnowledgeImportManifestEntity(Base):
    __tablename__ = "knowledge_import_manifests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", "manifest_id", name="uq_kb_manifest_scope"),
        UniqueConstraint(
            "tenant_id", "batch_id", "idempotency_key", name="uq_kb_manifest_idempotency"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["knowledge_import_batches.tenant_id", "knowledge_import_batches.batch_id"],
            name="fk_kb_manifest_batch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "upload_session_id"],
            ["knowledge_upload_sessions.tenant_id", "knowledge_upload_sessions.upload_session_id"],
            name="fk_kb_manifest_upload",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('COMPLETED','FAILED')", name="ck_kb_manifest_status"),
        CheckConstraint("record_count >= 0", name="ck_kb_manifest_count"),
    )
    manifest_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    upload_session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeManifestRecordEntity(Base):
    __tablename__ = "knowledge_manifest_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "batch_id", "manifest_record_id", name="uq_kb_manifest_record_scope"
        ),
        UniqueConstraint("tenant_id", "manifest_id", "row_number", name="uq_kb_manifest_row"),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id", "manifest_id"],
            [
                "knowledge_import_manifests.tenant_id",
                "knowledge_import_manifests.batch_id",
                "knowledge_import_manifests.manifest_id",
            ],
            name="fk_kb_manifest_record_parent",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id", "matched_item_id"],
            [
                "knowledge_batch_items.tenant_id",
                "knowledge_batch_items.batch_id",
                "knowledge_batch_items.item_id",
            ],
            name="fk_kb_manifest_record_item",
            ondelete="RESTRICT",
        ),
        CheckConstraint("row_number >= 2", name="ck_kb_manifest_row_number"),
        CheckConstraint(
            "status IN ('MAPPING_REQUIRED','FILE_MATCHED','FILE_MISSING')",
            name="ck_kb_manifest_row_status",
        ),
    )
    manifest_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(36), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    matched_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    proposed_values_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_refs_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    issues_json: Mapped[list] = mapped_column(JSON, nullable=False)
