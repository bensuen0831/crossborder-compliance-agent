"""Exact intake/document-version relationship and upload audit, no parallel SoT."""
from alembic import op
import sqlalchemy as sa

revision = "0012_m2b_document_inputs"
down_revision = "0011_m2a_intake"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("project_version_document_links"):
        op.create_table("project_version_document_links",
            sa.Column("link_id",sa.String(36),primary_key=True),
            sa.Column("project_version_id",sa.String(36),sa.ForeignKey("project_versions.project_version_id",ondelete="RESTRICT"),nullable=False),
            sa.Column("document_version_id",sa.String(36),sa.ForeignKey("document_versions.document_version_id",ondelete="RESTRICT"),nullable=False),
            sa.Column("tenant_id",sa.String(36),nullable=False),
            sa.Column("record_version",sa.Integer(),nullable=False,server_default="1"),
            sa.Column("status",sa.String(40),nullable=False,server_default="ACTIVE"),
            sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
            sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
            sa.UniqueConstraint("tenant_id","project_version_id","document_version_id",name="uq_project_version_document_link"))
        op.create_index("ix_project_version_document_links_tenant_id","project_version_document_links",["tenant_id"])
    if "upload_provenance_json" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("document_version_intelligence")}:
        op.add_column("document_version_intelligence", sa.Column("upload_provenance_json", sa.JSON(), nullable=False, server_default="{}"))
    op.execute("""CREATE OR REPLACE FUNCTION guard_project_document_input() RETURNS trigger AS $$
    DECLARE p record; d record;
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'immutable intake/document input relationship'; END IF;
      SELECT tenant_id, project_id, status INTO p FROM project_versions WHERE project_version_id=NEW.project_version_id;
      SELECT dv.tenant_id, doc.project_id INTO d FROM document_versions dv JOIN documents doc ON doc.document_id=dv.document_id WHERE dv.document_version_id=NEW.document_version_id;
      IF p.tenant_id IS DISTINCT FROM NEW.tenant_id OR d.tenant_id IS DISTINCT FROM NEW.tenant_id OR p.project_id IS DISTINCT FROM d.project_id OR p.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'document input tenant/project/draft boundary violation';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    op.execute("DROP TRIGGER IF EXISTS guard_project_document_input ON project_version_document_links")
    op.execute("CREATE TRIGGER guard_project_document_input BEFORE INSERT OR UPDATE OR DELETE ON project_version_document_links FOR EACH ROW EXECUTE FUNCTION guard_project_document_input()")


def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text("SELECT EXISTS(SELECT 1 FROM project_version_document_links) OR EXISTS(SELECT 1 FROM document_version_intelligence WHERE upload_provenance_json::jsonb <> '{}'::jsonb)")).scalar():
        raise RuntimeError("M2-B authoritative document inputs retained; archive/export required before downgrade")
    op.drop_table("project_version_document_links")
    op.execute("DROP FUNCTION guard_project_document_input()")
    op.drop_column("document_version_intelligence", "upload_provenance_json")
