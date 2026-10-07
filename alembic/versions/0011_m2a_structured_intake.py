"""Canonical structured BusinessFact provenance; document path is unchanged."""

import sqlalchemy as sa

from alembic import op

revision = "0011_m2a_intake"
down_revision = "0010_phase1j"
branch_labels = None
depends_on = None


def upgrade():
    # Historical0002 uses live Base.metadata. On a fresh DB the additive column
    # may already exist; frozen0010->0011 must arrive at the identical catalog.
    columns = {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns("business_facts")}
    if "structured_provenance_json" not in columns:
        op.add_column(
            "business_facts",
            sa.Column("structured_provenance_json", sa.JSON(), nullable=False, server_default="[]"),
        )
    elif not isinstance(columns["structured_provenance_json"]["type"], sa.JSON):
        raise RuntimeError("unexpected structured provenance column")
    op.execute("""CREATE FUNCTION m2a_fact_provenance_guard() RETURNS trigger
    LANGUAGE plpgsql AS $$ DECLARE p json; valid boolean; BEGIN
      IF json_typeof(NEW.structured_provenance_json) IS DISTINCT FROM 'array'
        THEN RAISE EXCEPTION 'structured provenance must be an array'; END IF;
      IF TG_OP='UPDATE' AND json_array_length(OLD.structured_provenance_json)>0 AND (
        OLD.structured_provenance_json::jsonb IS DISTINCT FROM NEW.structured_provenance_json::jsonb
        OR OLD.normalized_value_json::jsonb IS DISTINCT FROM NEW.normalized_value_json::jsonb
        OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
        OR OLD.project_id IS DISTINCT FROM NEW.project_id
        OR OLD.fact_type IS DISTINCT FROM NEW.fact_type OR OLD.version IS DISTINCT FROM NEW.version)
        THEN RAISE EXCEPTION 'immutable structured input provenance/value'; END IF;
      FOR p IN SELECT value FROM json_array_elements(NEW.structured_provenance_json) LOOP
        SELECT EXISTS(SELECT 1 FROM project_versions v JOIN analysis_snapshots sn
          ON sn.project_version_id=v.project_version_id
          WHERE v.project_version_id=p->>'source_ref' AND v.tenant_id=NEW.tenant_id
          AND v.project_id=NEW.project_id AND sn.tenant_id=NEW.tenant_id
          AND v.status IN ('CONFIRMED','SUPERSEDED') AND v.version_no::text=p->>'source_version'
          AND p->>'source_type'='USER_INPUT' AND p->>'generated_by'='StructuredIntakeFormalization'
          AND p->>'request_id'=sn.analysis_snapshot_id
          AND p->>'actor_ref'=sn.provenance_json->>'confirmed_by'
          AND (p->>'generated_at')::timestamptz=(sn.provenance_json->>'confirmed_at')::timestamptz
          AND v.intake_json->(p->>'source_locator') IS NOT NULL
          AND NEW.original_values_json::jsonb @>
          jsonb_build_array(v.intake_json->(p->>'source_locator')))
          INTO valid;
        IF NOT valid THEN RAISE EXCEPTION 'structured input provenance scope mismatch'; END IF;
      END LOOP; RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER tr_m2a_fact_provenance BEFORE INSERT OR UPDATE ON business_facts "
        "FOR EACH ROW EXECUTE FUNCTION m2a_fact_provenance_guard()"
    )


def downgrade():
    # No silent authority/provenance loss. Archive/export is a separate action.
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM business_facts "
            "WHERE json_array_length(structured_provenance_json)>0)"
        )
    ):
        raise RuntimeError(
            "M2A_DOWNGRADE_REFUSED_STRUCTURED_FACT_PROVENANCE: archive/export required"
        )
    op.execute("DROP TRIGGER tr_m2a_fact_provenance ON business_facts")
    op.execute("DROP FUNCTION m2a_fact_provenance_guard()")
    op.drop_column("business_facts", "structured_provenance_json")
