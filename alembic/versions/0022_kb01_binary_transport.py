"""Durable knowledge binary transport, version attachment and import work components."""

import sqlalchemy as sa

from alembic import op

revision = "0022_kb01_binary_transport"
down_revision = "0021_kb01_taxonomy_operations"
branch_labels = None
depends_on = None

TABLES = (
    "knowledge_upload_sessions",
    "knowledge_upload_parts",
    "knowledge_binary_attachments",
    "knowledge_import_batches",
    "knowledge_batch_items",
)
UPLOAD_OPERATIONS = (
    "UPLOAD_CREATE",
    "UPLOAD_PART_ACK",
    "UPLOAD_COMPLETE",
    "UPLOAD_CANCEL",
    "UPLOAD_RETRY",
    "UPLOAD_SCAN_RESULT",
    "UPLOAD_ATTACH",
    "BATCH_CREATE",
    "BATCH_EXTRACT",
    "BATCH_CONFIRM",
    "BATCH_CANCEL",
    "BATCH_RETRY",
)


PREVIOUS_OPERATIONS = (
    "CREATE",
    "EDIT_DRAFT",
    "NEW_VERSION",
    "SUBMIT_REVIEW",
    "APPROVE",
    "REJECT",
    "PUBLISH",
    "DELETE_DRAFT",
    "MERGE_PROPOSAL",
    "DEACTIVATE",
    "REACTIVATE",
    "ARCHIVE",
    "HOLD_CREATE",
    "HOLD_RELEASE",
    "DOCUMENT_CREATE",
    "DOCUMENT_NEW_VERSION",
    "DOCUMENT_EDIT_DRAFT",
    "DOCUMENT_DELETE_DRAFT",
    "DOCUMENT_VALIDATE",
    "DOCUMENT_SUBMIT_REVIEW",
    "DOCUMENT_APPROVE",
    "DOCUMENT_PUBLISH",
    "DOCUMENT_SUPERSEDE",
    "DOCUMENT_EXPIRE",
    "DOCUMENT_ARCHIVE",
)


def upgrade():
    # Render explicit frozen DDL; no runtime model imports or create_all migration.
    op.create_table(
        "knowledge_upload_sessions",
        sa.Column("upload_session_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("knowledge_version_id", sa.String(36)),
        sa.Column("expected_knowledge_record_version", sa.Integer()),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("relative_path", sa.String(1024), nullable=False),
        sa.Column("declared_format", sa.String(16), nullable=False),
        sa.Column("declared_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("part_bytes", sa.BigInteger(), nullable=False),
        sa.Column("policy_version_id", sa.String(36), nullable=False),
        sa.Column("policy_definition_id", sa.String(36), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("multipart_id", sa.String(500)),
        sa.Column("object_version", sa.String(500)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80)),
        sa.Column("scan_json", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.UniqueConstraint("tenant_id", "upload_session_id", name="uq_kb_upload_scope"),
        sa.UniqueConstraint("object_key", name="uq_kb_upload_object_key"),
        fk(
            "fk_kb_upload_knowledge_scope",
            "knowledge_version_id",
            "knowledge_document_versions",
            "knowledge_version_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "policy_definition_id", "policy_version_id"],
            [
                "metadata_versions.tenant_id",
                "metadata_versions.definition_id",
                "metadata_versions.version_id",
            ],
            name="fk_kb_upload_policy_scope",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "declared_bytes > 0 AND part_bytes >= 5242880", name="ck_kb_upload_size"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_kb_upload_attempts"),
        sa.CheckConstraint(
            "status IN ('CREATING','UPLOADING','FINALIZING','QUEUED_SCAN','SCANNING',"
            "'VERIFIED','QUARANTINED','FAILED','CANCELLING','CANCELLED','EXPIRED')",
            name="ck_kb_upload_status",
        ),
        sa.CheckConstraint(
            "declared_format IN ('DOC','DOCX','HTML','PDF','TXT','XHTML','RAR','ZIP')",
            name="ck_kb_upload_format",
        ),
    )
    op.create_index(
        "ix_kb_upload_worker",
        "knowledge_upload_sessions",
        ["status", "lease_expires_at", "created_at"],
    )
    op.create_index(
        "ix_knowledge_upload_sessions_tenant_id", "knowledge_upload_sessions", ["tenant_id"]
    )
    op.create_table(
        "knowledge_upload_parts",
        sa.Column("tenant_id", sa.String(36), primary_key=True),
        sa.Column("upload_session_id", sa.String(36), primary_key=True),
        sa.Column("part_number", sa.Integer(), primary_key=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("etag", sa.String(160), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        fk(
            "fk_kb_upload_part_scope",
            "upload_session_id",
            "knowledge_upload_sessions",
            "upload_session_id",
        ),
        sa.CheckConstraint("part_number BETWEEN 1 AND 10000", name="ck_kb_upload_part_number"),
        sa.CheckConstraint("byte_size > 0", name="ck_kb_upload_part_size"),
    )
    op.create_table(
        "knowledge_binary_attachments",
        sa.Column("tenant_id", sa.String(36), primary_key=True),
        sa.Column("knowledge_version_id", sa.String(36), primary_key=True),
        sa.Column("upload_session_id", sa.String(36), nullable=False),
        sa.Column("attached_by", sa.String(160), nullable=False),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "upload_session_id", name="uq_kb_upload_attachment"),
        fk(
            "fk_kb_binary_knowledge_scope",
            "knowledge_version_id",
            "knowledge_document_versions",
            "knowledge_version_id",
        ),
        fk(
            "fk_kb_binary_upload_scope",
            "upload_session_id",
            "knowledge_upload_sessions",
            "upload_session_id",
        ),
    )
    op.create_table(
        "knowledge_import_batches",
        sa.Column("batch_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("archive_upload_session_id", sa.String(36)),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("manifest_digest", sa.String(64)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80)),
        *audit_columns(),
        sa.UniqueConstraint("tenant_id", "batch_id", name="uq_kb_batch_scope"),
        fk(
            "fk_kb_batch_archive_scope",
            "archive_upload_session_id",
            "knowledge_upload_sessions",
            "upload_session_id",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','EXTRACTING','PREVIEW','CONFIRMED','PROCESSING',"
            "'COMPLETED','PARTIAL_FAILURE','FAILED','CANCELLING','CANCELLED')",
            name="ck_kb_batch_status",
        ),
    )
    op.create_index(
        "ix_knowledge_import_batches_tenant_id", "knowledge_import_batches", ["tenant_id"]
    )
    op.create_table(
        "knowledge_batch_items",
        sa.Column("item_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("upload_session_id", sa.String(36), nullable=False),
        sa.Column("relative_path", sa.String(1024), nullable=False),
        sa.Column("knowledge_version_id", sa.String(36)),
        sa.Column("proposed_metadata_json", sa.JSON(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80)),
        *audit_columns(),
        sa.UniqueConstraint("tenant_id", "batch_id", "relative_path", name="uq_kb_batch_path"),
        fk("fk_kb_batch_item_scope", "batch_id", "knowledge_import_batches", "batch_id"),
        fk(
            "fk_kb_batch_item_upload_scope",
            "upload_session_id",
            "knowledge_upload_sessions",
            "upload_session_id",
        ),
        fk(
            "fk_kb_batch_item_knowledge_scope",
            "knowledge_version_id",
            "knowledge_document_versions",
            "knowledge_version_id",
        ),
        sa.CheckConstraint(
            "status IN ('UNMAPPED','READY','PROCESSING','COMPLETED','FAILED','CANCELLED')",
            name="ck_kb_batch_item_status",
        ),
    )
    op.create_index("ix_knowledge_batch_items_tenant_id", "knowledge_batch_items", ["tenant_id"])
    op.execute("""CREATE FUNCTION kb01_binary_attachment_immutable()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'KB01_BINARY_ATTACHMENT_IMMUTABLE'; END $$""")
    op.execute("""CREATE TRIGGER kb01_binary_attachment_immutable BEFORE UPDATE OR DELETE
    ON knowledge_binary_attachments FOR EACH ROW
    EXECUTE FUNCTION kb01_binary_attachment_immutable()""")
    op.execute("""CREATE FUNCTION kb01_upload_manifest_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'KB01_UPLOAD_HISTORY_IMMUTABLE'; END IF;
      IF ROW(NEW.tenant_id,NEW.upload_session_id,NEW.created_by,NEW.relative_path,
        NEW.declared_format,NEW.declared_bytes,NEW.content_sha256,NEW.part_bytes,
        NEW.policy_definition_id,NEW.policy_version_id,NEW.policy_json::text,
        NEW.object_key,NEW.created_at,NEW.expires_at)
        IS DISTINCT FROM ROW(OLD.tenant_id,OLD.upload_session_id,OLD.created_by,
        OLD.relative_path,OLD.declared_format,OLD.declared_bytes,OLD.content_sha256,
        OLD.part_bytes,OLD.policy_definition_id,OLD.policy_version_id,OLD.policy_json::text,
        OLD.object_key,OLD.created_at,OLD.expires_at)
        OR (OLD.multipart_id IS NOT NULL AND NEW.multipart_id IS DISTINCT FROM OLD.multipart_id)
        OR (OLD.object_version IS NOT NULL
            AND NEW.object_version IS DISTINCT FROM OLD.object_version)
        OR (OLD.knowledge_version_id IS NOT NULL
            AND NEW.knowledge_version_id IS DISTINCT FROM OLD.knowledge_version_id)
      THEN RAISE EXCEPTION 'KB01_UPLOAD_MANIFEST_IMMUTABLE'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER kb01_upload_manifest_guard BEFORE UPDATE OR DELETE
    ON knowledge_upload_sessions FOR EACH ROW EXECUTE FUNCTION kb01_upload_manifest_guard()""")
    op.execute("""CREATE FUNCTION kb01_upload_part_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$ DECLARE state text; BEGIN
      SELECT status INTO state FROM knowledge_upload_sessions
      WHERE tenant_id=OLD.tenant_id AND upload_session_id=OLD.upload_session_id;
      IF state IS DISTINCT FROM 'UPLOADING'
      THEN RAISE EXCEPTION 'KB01_COMPLETED_UPLOAD_PART_IMMUTABLE'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END $$""")
    op.execute("""CREATE TRIGGER kb01_upload_part_guard BEFORE UPDATE OR DELETE
    ON knowledge_upload_parts FOR EACH ROW EXECUTE FUNCTION kb01_upload_part_guard()""")
    op.execute("""CREATE FUNCTION kb01_binary_origin_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$ DECLARE original_hash text; original_ref text; BEGIN
      SELECT u.content_sha256,'s3://' || (u.scan_json->>'bucket') || '/' || u.object_key
      INTO original_hash,original_ref FROM knowledge_binary_attachments a
      JOIN knowledge_upload_sessions u ON u.tenant_id=a.tenant_id
        AND u.upload_session_id=a.upload_session_id
      WHERE a.tenant_id=OLD.tenant_id AND a.knowledge_version_id=OLD.knowledge_version_id;
      IF FOUND AND (NEW.content_hash IS DISTINCT FROM original_hash
        OR NEW.original_artifact_ref IS DISTINCT FROM original_ref)
      THEN RAISE EXCEPTION 'KB01_ORIGINAL_BINARY_IDENTITY_IMMUTABLE'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER kb01_binary_origin_guard BEFORE UPDATE
    ON knowledge_document_versions FOR EACH ROW EXECUTE FUNCTION kb01_binary_origin_guard()""")
    op.execute("""CREATE FUNCTION kb01_import_batch_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'KB01_IMPORT_HISTORY_IMMUTABLE'; END IF;
      IF ROW(NEW.tenant_id,NEW.batch_id,NEW.archive_upload_session_id,NEW.created_by,NEW.created_at)
        IS DISTINCT FROM ROW(OLD.tenant_id,OLD.batch_id,OLD.archive_upload_session_id,
          OLD.created_by,OLD.created_at)
        OR (OLD.manifest_digest IS NOT NULL
          AND NEW.manifest_digest IS DISTINCT FROM OLD.manifest_digest)
      THEN RAISE EXCEPTION 'KB01_IMPORT_MANIFEST_IMMUTABLE'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER kb01_import_batch_guard BEFORE UPDATE OR DELETE
    ON knowledge_import_batches FOR EACH ROW EXECUTE FUNCTION kb01_import_batch_guard()""")
    op.execute("""CREATE FUNCTION kb01_import_item_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'KB01_IMPORT_ITEM_HISTORY_IMMUTABLE'; END IF;
      IF ROW(NEW.tenant_id,NEW.item_id,NEW.batch_id,NEW.upload_session_id,NEW.relative_path,
          NEW.created_at)
        IS DISTINCT FROM ROW(OLD.tenant_id,OLD.item_id,OLD.batch_id,OLD.upload_session_id,
          OLD.relative_path,OLD.created_at)
        OR (OLD.knowledge_version_id IS NOT NULL
          AND NEW.knowledge_version_id IS DISTINCT FROM OLD.knowledge_version_id)
      THEN RAISE EXCEPTION 'KB01_IMPORT_ITEM_IDENTITY_IMMUTABLE'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER kb01_import_item_guard BEFORE UPDATE OR DELETE
    ON knowledge_batch_items FOR EACH ROW EXECUTE FUNCTION kb01_import_item_guard()""")
    op.drop_constraint("ck_admin_operation_action", "admin_operation_receipts", type_="check")
    op.create_check_constraint(
        "ck_admin_operation_action",
        "admin_operation_receipts",
        operation_constraint(PREVIOUS_OPERATIONS + UPLOAD_OPERATIONS),
    )


def operation_constraint(actions):
    return "operation IN (" + ",".join("'" + action + "'" for action in actions) + ")"


def audit_columns():
    return (
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def fk(name, column, table, target):
    return sa.ForeignKeyConstraint(
        ["tenant_id", column],
        [table + ".tenant_id", table + "." + target],
        name=name,
        ondelete="RESTRICT",
    )


def downgrade():
    bind = op.get_bind()
    extra = ",".join("'" + action + "'" for action in UPLOAD_OPERATIONS)
    if any(
        bind.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")) for table in TABLES
    ) or bind.scalar(
        sa.text(
            f"SELECT EXISTS(SELECT 1 FROM admin_operation_receipts WHERE operation IN ({extra}))"
        )
    ):
        raise RuntimeError("KB01_BINARY_TRANSPORT_DOWNGRADE_REFUSED")
    op.drop_constraint("ck_admin_operation_action", "admin_operation_receipts", type_="check")
    op.create_check_constraint(
        "ck_admin_operation_action",
        "admin_operation_receipts",
        operation_constraint(PREVIOUS_OPERATIONS),
    )
    op.execute("DROP TRIGGER kb01_binary_attachment_immutable ON knowledge_binary_attachments")
    op.execute("DROP FUNCTION kb01_binary_attachment_immutable()")
    op.execute("DROP TRIGGER kb01_binary_origin_guard ON knowledge_document_versions")
    op.execute("DROP FUNCTION kb01_binary_origin_guard()")
    op.execute("DROP TRIGGER kb01_upload_manifest_guard ON knowledge_upload_sessions")
    op.execute("DROP FUNCTION kb01_upload_manifest_guard()")
    op.execute("DROP TRIGGER kb01_upload_part_guard ON knowledge_upload_parts")
    op.execute("DROP FUNCTION kb01_upload_part_guard()")
    op.execute("DROP TRIGGER kb01_import_batch_guard ON knowledge_import_batches")
    op.execute("DROP FUNCTION kb01_import_batch_guard()")
    op.execute("DROP TRIGGER kb01_import_item_guard ON knowledge_batch_items")
    op.execute("DROP FUNCTION kb01_import_item_guard()")
    for table in reversed(TABLES):
        op.drop_table(table)
