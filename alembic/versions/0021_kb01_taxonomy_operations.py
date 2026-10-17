"""Canonical admin mutation receipts for KB01 taxonomy management; no legal owner changes."""

import sqlalchemy as sa

from alembic import op

revision = "0021_kb01_taxonomy_operations"
down_revision = "0020_stage1_formal_decision_engine_compatibility"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_admin_change_scope", "admin_change_sets", ["tenant_id", "change_set_id"]
    )
    op.create_unique_constraint(
        "uq_metadata_scope", "metadata_definitions", ["tenant_id", "definition_id"]
    )
    op.create_unique_constraint(
        "uq_knowledge_document_scope", "knowledge_documents", ["tenant_id", "document_id"]
    )
    op.create_unique_constraint(
        "uq_knowledge_version_scope",
        "knowledge_document_versions",
        ["tenant_id", "knowledge_version_id"],
    )
    op.create_unique_constraint(
        "uq_metadata_version_definition_scope",
        "metadata_versions",
        ["tenant_id", "definition_id", "version_id"],
    )
    op.create_table(
        "knowledge_document_labels",
        sa.Column("label_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("knowledge_version_id", sa.String(36), nullable=False),
        sa.Column("definition_id", sa.String(36), nullable=False),
        sa.Column("metadata_version_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "knowledge_version_id"],
            [
                "knowledge_document_versions.tenant_id",
                "knowledge_document_versions.knowledge_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_label_version_scope",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "definition_id", "metadata_version_id"],
            [
                "metadata_versions.tenant_id",
                "metadata_versions.definition_id",
                "metadata_versions.version_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_label_metadata_scope",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "knowledge_version_id",
            "kind",
            "definition_id",
            name="uq_knowledge_version_label",
        ),
        sa.CheckConstraint(
            "kind IN ('JURISDICTION_CONFIG','REGULATION_CATEGORY','RESEARCH_TOPIC','LANGUAGE','ISSUING_AUTHORITY','KNOWLEDGE_SOURCE_TYPE','LEGAL_EFFECT')",
            name="ck_knowledge_label_kind",
        ),
    )
    op.create_index(
        "ix_knowledge_document_labels_tenant_id", "knowledge_document_labels", ["tenant_id"]
    )
    op.create_index(
        "ix_knowledge_document_labels_facets",
        "knowledge_document_labels",
        ["tenant_id", "kind", "definition_id", "knowledge_version_id"],
    )
    op.execute("""CREATE FUNCTION kb01_label_draft_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE label_row knowledge_document_labels; state text; registry_kind text;
    BEGIN
      IF TG_OP = 'UPDATE' THEN
        SELECT lifecycle INTO state FROM knowledge_document_versions
        WHERE tenant_id=OLD.tenant_id AND knowledge_version_id=OLD.knowledge_version_id;
        IF state IS DISTINCT FROM 'DRAFT' THEN RAISE EXCEPTION 'KB01_PUBLISHED_LABEL_IMMUTABLE'; END IF;
      END IF;
      IF TG_OP = 'DELETE' THEN label_row := OLD; ELSE label_row := NEW; END IF;
      SELECT lifecycle INTO state FROM knowledge_document_versions
      WHERE tenant_id=label_row.tenant_id AND knowledge_version_id=label_row.knowledge_version_id;
      IF state IS DISTINCT FROM 'DRAFT' THEN RAISE EXCEPTION 'KB01_PUBLISHED_LABEL_IMMUTABLE'; END IF;
      IF TG_OP <> 'DELETE' THEN
        SELECT kind INTO registry_kind FROM metadata_definitions
        WHERE tenant_id=label_row.tenant_id AND definition_id=label_row.definition_id;
        IF registry_kind IS DISTINCT FROM label_row.kind THEN RAISE EXCEPTION 'KB01_LABEL_KIND_MISMATCH'; END IF;
      END IF;
      RETURN label_row;
    END $$""")
    op.execute("""CREATE TRIGGER kb01_label_draft_guard BEFORE INSERT OR UPDATE OR DELETE
    ON knowledge_document_labels FOR EACH ROW EXECUTE FUNCTION kb01_label_draft_guard()""")

    op.create_table(
        "admin_operation_receipts",
        sa.Column("receipt_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("change_set_id", sa.String(36), nullable=False),
        sa.Column("resource_kind", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "change_set_id"],
            ["admin_change_sets.tenant_id", "admin_change_sets.change_set_id"],
            ondelete="RESTRICT",
            name="fk_admin_operation_change_scope",
        ),
        sa.UniqueConstraint("change_set_id", name="uq_admin_operation_change"),
        sa.CheckConstraint(
            "operation IN ('CREATE','EDIT_DRAFT','NEW_VERSION','SUBMIT_REVIEW','APPROVE','REJECT','PUBLISH','DELETE_DRAFT','MERGE_PROPOSAL','DEACTIVATE','REACTIVATE','ARCHIVE','HOLD_CREATE','HOLD_RELEASE','DOCUMENT_CREATE','DOCUMENT_NEW_VERSION','DOCUMENT_EDIT_DRAFT','DOCUMENT_DELETE_DRAFT','DOCUMENT_VALIDATE','DOCUMENT_SUBMIT_REVIEW','DOCUMENT_APPROVE','DOCUMENT_PUBLISH','DOCUMENT_SUPERSEDE','DOCUMENT_EXPIRE','DOCUMENT_ARCHIVE')",
            name="ck_admin_operation_action",
        ),
    )
    op.create_index(
        "ix_admin_operation_receipts_tenant_id", "admin_operation_receipts", ["tenant_id"]
    )
    op.execute("""CREATE FUNCTION kb01_receipt_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'KB01_ADMIN_AUDIT_IMMUTABLE'; END $$""")
    op.execute("""CREATE TRIGGER kb01_receipt_immutable BEFORE UPDATE OR DELETE ON admin_operation_receipts
    FOR EACH ROW EXECUTE FUNCTION kb01_receipt_immutable()""")
    op.create_table(
        "knowledge_management_holds",
        sa.Column("hold_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("metadata_definition_id", sa.String(36), nullable=True),
        sa.Column("knowledge_document_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.String(160), nullable=True),
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "metadata_definition_id"],
            ["metadata_definitions.tenant_id", "metadata_definitions.definition_id"],
            ondelete="RESTRICT",
            name="fk_kb_hold_metadata_scope",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "knowledge_document_id"],
            ["knowledge_documents.tenant_id", "knowledge_documents.document_id"],
            ondelete="RESTRICT",
            name="fk_kb_hold_document_scope",
        ),
        sa.CheckConstraint(
            "(metadata_definition_id IS NOT NULL AND knowledge_document_id IS NULL) OR (metadata_definition_id IS NULL AND knowledge_document_id IS NOT NULL)",
            name="ck_kb_hold_resource",
        ),
        sa.CheckConstraint(
            "(released_at IS NULL AND released_by IS NULL) OR (released_at IS NOT NULL AND released_by IS NOT NULL)",
            name="ck_kb_hold_release_actor",
        ),
    )
    op.create_index(
        "ix_knowledge_management_holds_tenant_id", "knowledge_management_holds", ["tenant_id"]
    )

    op.execute("""CREATE FUNCTION kb01_hold_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'KB01_HOLD_HISTORY_IMMUTABLE'; END IF;
      IF OLD.released_at IS NOT NULL OR NEW.released_at IS NULL OR NEW.released_by IS NULL
         OR NEW.record_version <> OLD.record_version + 1 OR NEW.status <> 'RELEASED'
         OR (to_jsonb(NEW) - ARRAY['released_at','released_by','record_version','status','updated_at'])
            IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['released_at','released_by','record_version','status','updated_at'])
      THEN RAISE EXCEPTION 'KB01_HOLD_HISTORY_IMMUTABLE'; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER kb01_hold_history_guard BEFORE UPDATE OR DELETE
    ON knowledge_management_holds FOR EACH ROW EXECUTE FUNCTION kb01_hold_history_guard()""")


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM admin_operation_receipts) OR EXISTS(SELECT 1 FROM knowledge_management_holds) OR EXISTS(SELECT 1 FROM knowledge_document_labels)"
        )
    ):
        raise RuntimeError(
            "KB01_TAXONOMY_DOWNGRADE_REFUSED: administration audit evidence would be lost"
        )
    op.execute("DROP TRIGGER kb01_receipt_immutable ON admin_operation_receipts")
    op.execute("DROP FUNCTION kb01_receipt_immutable()")
    op.execute("DROP TRIGGER kb01_hold_history_guard ON knowledge_management_holds")
    op.execute("DROP FUNCTION kb01_hold_history_guard()")
    op.execute("DROP TRIGGER kb01_label_draft_guard ON knowledge_document_labels")
    op.execute("DROP FUNCTION kb01_label_draft_guard()")
    op.drop_table("knowledge_document_labels")
    op.drop_constraint("uq_metadata_version_definition_scope", "metadata_versions", type_="unique")
    op.drop_constraint("uq_knowledge_version_scope", "knowledge_document_versions", type_="unique")
    op.drop_table("knowledge_management_holds")
    op.drop_table("admin_operation_receipts")
    op.drop_constraint("uq_knowledge_document_scope", "knowledge_documents", type_="unique")
    op.drop_constraint("uq_metadata_scope", "metadata_definitions", type_="unique")
    op.drop_constraint("uq_admin_change_scope", "admin_change_sets", type_="unique")
