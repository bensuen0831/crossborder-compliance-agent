"""Immutable operational catalogue proposals under existing import/upload identities."""

import sqlalchemy as sa

from alembic import op

revision = "0024_kb01_import_manifest_records"
down_revision = "0023_kb01_evidence_source_reference"
branch_labels = None
depends_on = None

FORMATS = ("DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML", "RAR", "ZIP")
OPERATIONS = (
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


def allowed(column, values):
    return column + " IN (" + ",".join("'" + value + "'" for value in values) + ")"


def scope_fk(name, columns, target, target_columns):
    return sa.ForeignKeyConstraint(
        ["tenant_id", *columns],
        [target + "." + x for x in ["tenant_id", *target_columns]],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade():
    op.drop_constraint("ck_kb_upload_format", "knowledge_upload_sessions", type_="check")
    op.create_check_constraint(
        "ck_kb_upload_format",
        "knowledge_upload_sessions",
        allowed("declared_format", FORMATS + ("CSV", "XLSX")),
    )
    op.drop_constraint("ck_admin_operation_action", "admin_operation_receipts", type_="check")
    op.create_check_constraint(
        "ck_admin_operation_action",
        "admin_operation_receipts",
        allowed("operation", OPERATIONS + ("MANIFEST_IMPORT", "DOCUMENT_BIND")),
    )
    op.create_unique_constraint(
        "uq_kb_batch_item_scope", "knowledge_batch_items", ["tenant_id", "batch_id", "item_id"]
    )
    op.create_table(
        "knowledge_import_manifests",
        sa.Column("manifest_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("upload_session_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("inventory_digest", sa.String(64), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("mapping_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "batch_id", "manifest_id", name="uq_kb_manifest_scope"),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "idempotency_key", name="uq_kb_manifest_idempotency"
        ),
        scope_fk("fk_kb_manifest_batch", ["batch_id"], "knowledge_import_batches", ["batch_id"]),
        scope_fk(
            "fk_kb_manifest_upload",
            ["upload_session_id"],
            "knowledge_upload_sessions",
            ["upload_session_id"],
        ),
        sa.CheckConstraint("status IN ('COMPLETED','FAILED')", name="ck_kb_manifest_status"),
        sa.CheckConstraint("record_count >= 0", name="ck_kb_manifest_count"),
    )
    op.create_table(
        "knowledge_manifest_records",
        sa.Column("manifest_record_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("manifest_id", sa.String(36), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("canonical_path", sa.String(1024), nullable=True),
        sa.Column("matched_item_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("proposed_values_json", sa.JSON(), nullable=False),
        sa.Column("metadata_refs_json", sa.JSON(), nullable=False),
        sa.Column("issues_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_id", "manifest_id", "row_number", name="uq_kb_manifest_row"),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "manifest_record_id", name="uq_kb_manifest_record_scope"
        ),
        scope_fk(
            "fk_kb_manifest_record_parent",
            ["batch_id", "manifest_id"],
            "knowledge_import_manifests",
            ["batch_id", "manifest_id"],
        ),
        scope_fk(
            "fk_kb_manifest_record_item",
            ["batch_id", "matched_item_id"],
            "knowledge_batch_items",
            ["batch_id", "item_id"],
        ),
        sa.CheckConstraint("row_number >= 2", name="ck_kb_manifest_row_number"),
        sa.CheckConstraint(
            "status IN ('MAPPING_REQUIRED','FILE_MATCHED','FILE_MISSING')",
            name="ck_kb_manifest_row_status",
        ),
    )
    op.add_column(
        "knowledge_batch_items", sa.Column("manifest_record_id", sa.String(36), nullable=True)
    )
    op.create_foreign_key(
        "fk_kb_batch_confirmed_manifest",
        "knowledge_batch_items",
        "knowledge_manifest_records",
        ["tenant_id", "batch_id", "manifest_record_id"],
        ["tenant_id", "batch_id", "manifest_record_id"],
        ondelete="RESTRICT",
    )
    op.execute("""CREATE FUNCTION kb01_manifest_binding_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF OLD.manifest_record_id IS NOT NULL AND
           NEW.manifest_record_id IS DISTINCT FROM OLD.manifest_record_id THEN
          RAISE EXCEPTION 'KB01_CONFIRMED_MANIFEST_BINDING_IMMUTABLE';
        END IF;
        RETURN NEW; END $$""")
    op.execute(
        "CREATE TRIGGER kb01_confirmed_manifest_immutable BEFORE UPDATE ON knowledge_batch_items "
        "FOR EACH ROW EXECUTE FUNCTION kb01_manifest_binding_immutable()"
    )
    op.execute("""CREATE FUNCTION kb01_catalogue_receipt_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'KB01_MANIFEST_RECEIPT_IMMUTABLE'; END $$""")
    for table in ("knowledge_import_manifests", "knowledge_manifest_records"):
        op.execute(
            f"CREATE TRIGGER kb01_catalogue_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION kb01_catalogue_receipt_immutable()"
        )


def downgrade():
    connection = op.get_bind()
    for table in ("knowledge_import_manifests", "knowledge_manifest_records"):
        if connection.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")):
            raise RuntimeError("KB01_MANIFEST_GOVERNANCE_DOWNGRADE_REFUSED")
    if connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM knowledge_upload_sessions "
            "WHERE declared_format IN ('CSV','XLSX'))"
        )
    ) or connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM admin_operation_receipts "
            "WHERE operation IN ('MANIFEST_IMPORT','DOCUMENT_BIND'))"
        )
    ):
        raise RuntimeError("KB01_MANIFEST_GOVERNANCE_DOWNGRADE_REFUSED")
    op.execute("DROP TRIGGER kb01_confirmed_manifest_immutable ON knowledge_batch_items")
    op.execute("DROP FUNCTION kb01_manifest_binding_immutable()")
    op.drop_constraint(
        "fk_kb_batch_confirmed_manifest", "knowledge_batch_items", type_="foreignkey"
    )
    op.drop_column("knowledge_batch_items", "manifest_record_id")
    op.drop_table("knowledge_manifest_records")
    op.drop_table("knowledge_import_manifests")
    op.execute("DROP FUNCTION kb01_catalogue_receipt_immutable()")
    op.drop_constraint("uq_kb_batch_item_scope", "knowledge_batch_items", type_="unique")
    op.drop_constraint("ck_kb_upload_format", "knowledge_upload_sessions", type_="check")
    op.create_check_constraint(
        "ck_kb_upload_format", "knowledge_upload_sessions", allowed("declared_format", FORMATS)
    )
    op.drop_constraint("ck_admin_operation_action", "admin_operation_receipts", type_="check")
    op.create_check_constraint(
        "ck_admin_operation_action", "admin_operation_receipts", allowed("operation", OPERATIONS)
    )
