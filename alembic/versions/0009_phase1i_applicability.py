"""Canonical applicability result and governed configuration/pin protection only."""

import sqlalchemy as sa

from alembic import op

revision = "0009_phase1i"
down_revision = "0008_phase1h"
branch_labels = None
depends_on = None
KINDS = (
    "'COUNTRY_PROFILE','SCENARIO_ADJUSTMENT','COUNTRY_CAPABILITY',"
    "'APPLICABILITY_CONFIG','RULE_PACK'"
)


def upgrade():
    # Explicit frozen DDL: future model changes cannot alter this revision.
    op.create_table(
        "regulation_applicability_results",
        sa.Column("applicability_result_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.project_id"), nullable=False
        ),
        sa.Column(
            "analysis_snapshot_id",
            sa.String(36),
            sa.ForeignKey("analysis_snapshots.analysis_snapshot_id"),
            nullable=False,
        ),
        sa.Column(
            "jurisdiction_id",
            sa.String(36),
            sa.ForeignKey("jurisdictions.jurisdiction_id"),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column(
            "regulation_version_ref",
            sa.String(36),
            sa.ForeignKey("knowledge_document_versions.knowledge_version_id"),
            nullable=False,
        ),
        sa.Column(
            "applicability_config_version_id",
            sa.String(36),
            sa.ForeignKey("metadata_versions.version_id"),
            nullable=False,
        ),
        sa.Column(
            "country_profile_version_id",
            sa.String(36),
            sa.ForeignKey("metadata_versions.version_id"),
        ),
        sa.Column(
            "retrieval_run_id",
            sa.String(36),
            sa.ForeignKey("retrieval_runs.retrieval_run_id"),
            nullable=False,
        ),
        sa.Column("owner_actor_id", sa.String(160), nullable=False),
        sa.Column("applicability_status", sa.String(50), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
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
        sa.CheckConstraint(
            "subject_type IN ('DATA_ITEM','DATA_FLOW','SCENARIO')", name="ck_applicability_subject"
        ),
        sa.CheckConstraint(
            "applicability_status IN"
            " ('APPLICABLE','NOT_APPLICABLE','CONDITIONALLY_APPLICABLE',"
            "'INSUFFICIENT_EVIDENCE','CONFLICTED','REVIEW_REQUIRED')",
            name="ck_applicability_status",
        ),
    )
    op.create_index(
        "ix_applicability_snapshot",
        "regulation_applicability_results",
        ["tenant_id", "project_id", "analysis_snapshot_id"],
    )
    op.create_index(
        "ix_regulation_applicability_results_tenant_id",
        "regulation_applicability_results",
        ["tenant_id"],
    )
    op.execute(f"""
    CREATE FUNCTION phase1i_immutable_metadata() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE kind text;
    BEGIN
      SELECT d.kind INTO kind FROM metadata_definitions d WHERE d.definition_id=OLD.definition_id;
      IF kind IN ({KINDS}) THEN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain Phase1I configuration version'; END IF;
        IF NEW.definition_id IS DISTINCT FROM OLD.definition_id OR
          NEW.tenant_id IS DISTINCT FROM OLD.tenant_id OR
          NEW.version_no IS DISTINCT FROM OLD.version_no OR
          NEW.created_by IS DISTINCT FROM OLD.created_by THEN
          RAISE EXCEPTION 'immutable Phase1I version identity';
        END IF;
        IF (OLD.lifecycle_status <> 'DRAFT' OR OLD.published_at IS NOT NULL) AND (
          NEW.payload_json::jsonb IS DISTINCT FROM OLD.payload_json::jsonb OR
          NEW.definition_id IS DISTINCT FROM OLD.definition_id OR
          NEW.effective_from IS DISTINCT FROM OLD.effective_from OR
          NEW.effective_to IS DISTINCT FROM OLD.effective_to OR
          NEW.tenant_id IS DISTINCT FROM OLD.tenant_id OR
          NEW.version_no IS DISTINCT FROM OLD.version_no OR
          NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
          RAISE EXCEPTION 'immutable Phase1I configuration';
        END IF;
      END IF;
      IF kind IN ({KINDS}) AND OLD.published_at IS NOT NULL AND (
        NEW.approved_by IS DISTINCT FROM OLD.approved_by OR
        NEW.published_at IS DISTINCT FROM OLD.published_at) THEN
        RAISE EXCEPTION 'immutable Phase1I publication provenance';
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase1i_metadata_immutable BEFORE UPDATE OR DELETE ON metadata_versions
      FOR EACH ROW EXECUTE FUNCTION phase1i_immutable_metadata();
    CREATE FUNCTION phase1i_immutable_definition() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.kind IN ({KINDS}) THEN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain Phase1I configuration identity'; END IF;
        IF NEW.kind IS DISTINCT FROM OLD.kind OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
          OR NEW.code IS DISTINCT FROM OLD.code THEN
          RAISE EXCEPTION 'immutable Phase1I configuration identity';
        END IF;
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase1i_definition_immutable BEFORE UPDATE OR DELETE ON metadata_definitions
      FOR EACH ROW EXECUTE FUNCTION phase1i_immutable_definition();
    CREATE FUNCTION phase1i_immutable_result() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable Phase1I applicability result'; END $$;
    CREATE TRIGGER phase1i_applicability_immutable BEFORE UPDATE OR DELETE
      ON regulation_applicability_results FOR EACH ROW EXECUTE FUNCTION phase1i_immutable_result();
    CREATE FUNCTION phase1i_immutable_pin() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.pin_type LIKE 'PHASE1I_%' THEN
        RAISE EXCEPTION 'immutable Phase1I snapshot pin';
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase1i_pin_immutable BEFORE UPDATE OR DELETE ON analysis_snapshot_registry_pins
      FOR EACH ROW EXECUTE FUNCTION phase1i_immutable_pin();
    """)


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            f"""
        SELECT EXISTS (SELECT1 FROM regulation_applicability_results)
        OR EXISTS (SELECT1 FROM metadata_definitions WHERE kind IN ({KINDS}))
        OR EXISTS (SELECT1 FROM analysis_snapshot_registry_pins WHERE pin_type LIKE 'PHASE1I_%')
    """.replace("SELECT1", "SELECT 1")
        )
    ):
        raise RuntimeError(
            "archive/export Phase1I authoritative results/configuration/pins before downgrade"
        )
    op.execute(
        "DROP TRIGGER phase1i_metadata_immutable ON metadata_versions; DROP"
        " FUNCTION phase1i_immutable_metadata()"
    )
    op.execute(
        "DROP TRIGGER phase1i_pin_immutable ON analysis_snapshot_registry_pins;"
        " DROP FUNCTION phase1i_immutable_pin()"
    )
    op.execute(
        "DROP TRIGGER phase1i_definition_immutable ON metadata_definitions; DROP"
        " FUNCTION phase1i_immutable_definition()"
    )
    op.drop_table("regulation_applicability_results")
    op.execute("DROP FUNCTION phase1i_immutable_result()")
