"""Durable transport components of the existing KnowledgeDocumentVersion owner."""

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin


class KnowledgeUploadSessionEntity(TenantAuditMixin, Base):
    __tablename__ = "knowledge_upload_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "upload_session_id", name="uq_kb_upload_scope"),
        UniqueConstraint("object_key", name="uq_kb_upload_object_key"),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_version_id"],
            [
                "knowledge_document_versions.tenant_id",
                "knowledge_document_versions.knowledge_version_id",
            ],
            name="fk_kb_upload_knowledge_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "policy_definition_id", "policy_version_id"],
            [
                "metadata_versions.tenant_id",
                "metadata_versions.definition_id",
                "metadata_versions.version_id",
            ],
            name="fk_kb_upload_policy_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint("declared_bytes > 0 AND part_bytes >= 5242880", name="ck_kb_upload_size"),
        CheckConstraint("attempts >= 0", name="ck_kb_upload_attempts"),
        CheckConstraint(
            "status IN ('CREATING','UPLOADING','FINALIZING','QUEUED_SCAN','SCANNING',"
            "'VERIFIED','QUARANTINED','FAILED','CANCELLING','CANCELLED','EXPIRED')",
            name="ck_kb_upload_status",
        ),
        CheckConstraint(
            "declared_format IN ('DOC','DOCX','HTML','PDF','TXT','XHTML','RAR','ZIP','CSV','XLSX')",
            name="ck_kb_upload_format",
        ),
        Index("ix_kb_upload_worker", "status", "lease_expires_at", "created_at"),
    )
    upload_session_id = mapped_column(String(36), primary_key=True)
    knowledge_version_id = mapped_column(String(36), nullable=True)
    expected_knowledge_record_version = mapped_column(Integer, nullable=True)
    created_by = mapped_column(String(160), nullable=False)
    relative_path = mapped_column(String(1024), nullable=False)
    declared_format = mapped_column(String(16), nullable=False)
    declared_bytes = mapped_column(BigInteger, nullable=False)
    content_sha256 = mapped_column(String(64), nullable=False)
    part_bytes = mapped_column(BigInteger, nullable=False)
    policy_version_id = mapped_column(String(36), nullable=False)
    policy_definition_id = mapped_column(String(36), nullable=False)
    policy_json = mapped_column(JSON, nullable=False)
    object_key = mapped_column(String(500), nullable=False)
    multipart_id = mapped_column(String(500), nullable=True)
    object_version = mapped_column(String(500), nullable=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    lease_token = mapped_column(String(36), nullable=True)
    lease_expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    attempts = mapped_column(Integer, nullable=False, default=0)
    error_code = mapped_column(String(80), nullable=True)
    scan_json = mapped_column(JSON, nullable=False, default=dict)


class KnowledgeUploadPartEntity(Base):
    __tablename__ = "knowledge_upload_parts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "upload_session_id"],
            ["knowledge_upload_sessions.tenant_id", "knowledge_upload_sessions.upload_session_id"],
            name="fk_kb_upload_part_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint("part_number BETWEEN 1 AND 10000", name="ck_kb_upload_part_number"),
        CheckConstraint("byte_size > 0", name="ck_kb_upload_part_size"),
    )
    tenant_id = mapped_column(String(36), primary_key=True)
    upload_session_id = mapped_column(String(36), primary_key=True)
    part_number = mapped_column(Integer, primary_key=True)
    byte_size = mapped_column(BigInteger, nullable=False)
    content_sha256 = mapped_column(String(64), nullable=False)
    etag = mapped_column(String(160), nullable=False)
    received_at = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeBinaryAttachmentEntity(Base):
    """Immutable original-binary receipt for a canonical KnowledgeVersion, not a file SoT."""

    __tablename__ = "knowledge_binary_attachments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "upload_session_id", name="uq_kb_upload_attachment"),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_version_id"],
            [
                "knowledge_document_versions.tenant_id",
                "knowledge_document_versions.knowledge_version_id",
            ],
            name="fk_kb_binary_knowledge_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "upload_session_id"],
            ["knowledge_upload_sessions.tenant_id", "knowledge_upload_sessions.upload_session_id"],
            name="fk_kb_binary_upload_scope",
            ondelete="RESTRICT",
        ),
    )
    tenant_id = mapped_column(String(36), primary_key=True)
    knowledge_version_id = mapped_column(String(36), primary_key=True)
    upload_session_id = mapped_column(String(36), nullable=False)
    attached_by = mapped_column(String(160), nullable=False)
    attached_at = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeImportBatchEntity(TenantAuditMixin, Base):
    """Operational work identity. Legal content remains in canonical knowledge versions."""

    __tablename__ = "knowledge_import_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", name="uq_kb_batch_scope"),
        ForeignKeyConstraint(
            ["tenant_id", "archive_upload_session_id"],
            ["knowledge_upload_sessions.tenant_id", "knowledge_upload_sessions.upload_session_id"],
            name="fk_kb_batch_archive_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('PENDING','EXTRACTING','PREVIEW','CONFIRMED','PROCESSING',"
            "'COMPLETED','PARTIAL_FAILURE','FAILED','CANCELLING','CANCELLED')",
            name="ck_kb_batch_status",
        ),
    )
    batch_id = mapped_column(String(36), primary_key=True)
    archive_upload_session_id = mapped_column(String(36), nullable=True)
    created_by = mapped_column(String(160), nullable=False)
    manifest_digest = mapped_column(String(64), nullable=True)
    lease_token = mapped_column(String(36), nullable=True)
    lease_expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    attempts = mapped_column(Integer, nullable=False, default=0)
    error_code = mapped_column(String(80), nullable=True)


class KnowledgeBatchItemEntity(TenantAuditMixin, Base):
    __tablename__ = "knowledge_batch_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", "item_id", name="uq_kb_batch_item_scope"),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id", "manifest_record_id"],
            [
                "knowledge_manifest_records.tenant_id",
                "knowledge_manifest_records.batch_id",
                "knowledge_manifest_records.manifest_record_id",
            ],
            name="fk_kb_batch_confirmed_manifest",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "batch_id", "relative_path", name="uq_kb_batch_path"),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["knowledge_import_batches.tenant_id", "knowledge_import_batches.batch_id"],
            name="fk_kb_batch_item_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "upload_session_id"],
            ["knowledge_upload_sessions.tenant_id", "knowledge_upload_sessions.upload_session_id"],
            name="fk_kb_batch_item_upload_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_version_id"],
            [
                "knowledge_document_versions.tenant_id",
                "knowledge_document_versions.knowledge_version_id",
            ],
            name="fk_kb_batch_item_knowledge_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('UNMAPPED','READY','PROCESSING','COMPLETED','FAILED','CANCELLED')",
            name="ck_kb_batch_item_status",
        ),
    )
    item_id = mapped_column(String(36), primary_key=True)
    batch_id = mapped_column(String(36), nullable=False)
    upload_session_id = mapped_column(String(36), nullable=False)
    relative_path = mapped_column(String(1024), nullable=False)
    knowledge_version_id = mapped_column(String(36), nullable=True)
    manifest_record_id = mapped_column(String(36), nullable=True)
    # Bounded user-proposed mapping, never an expected legal outcome.
    proposed_metadata_json = mapped_column(JSON, nullable=False, default=dict)
    lease_token = mapped_column(String(36), nullable=True)
    lease_expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    attempts = mapped_column(Integer, nullable=False, default=0)
    error_code = mapped_column(String(80), nullable=True)


# BatchItem's optional catalogue FK belongs to this same canonical Base. Load
# its target for independently imported upload/batch owners, without depending
# on API-router or pytest collection order.
from crossborder_compliance.infrastructure.persistence import (
    knowledge_manifest_models as _knowledge_manifest_models,
)  # noqa: E402,F401
