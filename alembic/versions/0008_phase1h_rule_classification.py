"""Safe rule contract and formal provenance, extending canonical tables only.

Legacy Phase 1B/1C configuration rows remain readable and are not executable V1 rules.
Downgrade refuses to discard Phase 1H authoritative results/published rules.
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_phase1h"
down_revision = "0007_phase1g"
branch_labels = None
depends_on = None


def upgrade():
    # Frozen 0002 creates some tables from live Base.metadata. On a fresh database,
    # its tables already include additive ORM columns; existing 0007 databases do not.
    # Verify identical definitions and add missing columns without rewriting 0002.
    def add(table, column):
        columns = {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns(table)}
        if column.name not in columns:
            op.add_column(table, column)
        elif (
            columns[column.name]["nullable"] != column.nullable
            or columns[column.name]["type"]._type_affinity is not column.type._type_affinity
        ):
            raise RuntimeError(f"incompatible existing column: {table}.{column.name}")
        for foreign in column.foreign_keys:
            expected_table, expected_column = foreign.target_fullname.split(".")
            existing = sa.inspect(op.get_bind()).get_foreign_keys(table)
            if not any(
                f["constrained_columns"] == [column.name]
                and f["referred_table"] == expected_table
                and f["referred_columns"] == [expected_column]
                for f in existing
            ):
                raise RuntimeError(f"missing expected foreign key: {table}.{column.name}")

    add("rule_versions", sa.Column("runtime_contract_json", sa.JSON(), nullable=True))
    add("rule_versions", sa.Column("governance_json", sa.JSON(), nullable=True))
    add("rule_hits", sa.Column("formal_provenance_json", sa.JSON(), nullable=True))
    add(
        "classification_results",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id"), nullable=True),
    )
    add(
        "classification_results",
        sa.Column(
            "analysis_snapshot_id",
            sa.String(36),
            sa.ForeignKey("analysis_snapshots.analysis_snapshot_id"),
            nullable=True,
        ),
    )
    add("classification_results", sa.Column("formal_provenance_json", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "ck_rule_effective_interval",
        "rule_versions",
        "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
    )
    op.create_check_constraint(
        "ck_formal_classification_scope",
        "classification_results",
        "formal_provenance_json IS NULL OR (project_id IS NOT NULL AND "
        "analysis_snapshot_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_rule_v1_active_gate",
        "rule_versions",
        "runtime_contract_json IS NULL OR lifecycle_status <> 'ACTIVE' OR "
        "COALESCE((governance_json->'validation'->>'status' = 'PASS' AND "
        "governance_json->>'approved_by' IS NOT NULL AND "
        "governance_json->>'published_by' IS NOT NULL), false)",
    )
    op.create_check_constraint(
        "ck_scheme_effective_interval",
        "classification_scheme_versions",
        "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
    )
    op.create_index(
        "ix_rule_runtime_scope",
        "rule_versions",
        ["tenant_id", "lifecycle_status", "effective_from", "effective_to"],
    )
    op.create_index(
        "ix_formal_classification_snapshot",
        "classification_results",
        ["tenant_id", "project_id", "analysis_snapshot_id"],
    )
    op.create_index(
        "uq_formal_classification_snapshot",
        "classification_results",
        ["tenant_id", "project_id", "analysis_snapshot_id", "subject_id", "scheme_version_id"],
        unique=True,
        postgresql_where=sa.text("formal_provenance_json IS NOT NULL"),
    )
    op.execute("""
    CREATE FUNCTION phase1h_immutable_rule() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.runtime_contract_json IS NOT NULL AND OLD.lifecycle_status <> 'DRAFT'
        AND (NEW.runtime_contract_json::jsonb IS DISTINCT FROM OLD.runtime_contract_json::jsonb
          OR NEW.safe_dsl_json::jsonb IS DISTINCT FROM OLD.safe_dsl_json::jsonb
          OR NEW.scope_json::jsonb IS DISTINCT FROM OLD.scope_json::jsonb
          OR NEW.priority IS DISTINCT FROM OLD.priority
          OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
          OR NEW.effective_to IS DISTINCT FROM OLD.effective_to) THEN
        RAISE EXCEPTION 'immutable Phase 1H rule version';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase1h_rule_immutable BEFORE UPDATE ON rule_versions
      FOR EACH ROW EXECUTE FUNCTION phase1h_immutable_rule();
    CREATE FUNCTION phase1h_immutable_tests() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent rule_versions; ident text; tenant text;
    BEGIN
      IF TG_OP = 'UPDATE' THEN
        SELECT * INTO parent FROM rule_versions
          WHERE rule_version_id=OLD.rule_version_id FOR UPDATE;
        IF parent.runtime_contract_json IS NOT NULL AND parent.lifecycle_status <> 'DRAFT' THEN
          RAISE EXCEPTION 'immutable Phase 1H rule tests';
        END IF;
      END IF;
      IF TG_OP = 'DELETE' THEN ident := OLD.rule_version_id; tenant := OLD.tenant_id;
      ELSE ident := NEW.rule_version_id; tenant := NEW.tenant_id; END IF;
      SELECT * INTO parent FROM rule_versions WHERE rule_version_id=ident FOR UPDATE;
      IF FOUND AND (parent.tenant_id <> tenant OR
          (parent.runtime_contract_json IS NOT NULL AND parent.lifecycle_status <> 'DRAFT')) THEN
        RAISE EXCEPTION 'immutable or inaccessible Phase 1H rule tests';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase1h_rule_tests_immutable BEFORE INSERT OR UPDATE OR DELETE ON rule_test_cases
      FOR EACH ROW EXECUTE FUNCTION phase1h_immutable_tests();
    CREATE FUNCTION phase1h_immutable_scheme() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.applicability_json->'phase1h' IS NOT NULL AND OLD.lifecycle_status <> 'DRAFT'
        AND (NEW.applicability_json::jsonb IS DISTINCT FROM OLD.applicability_json::jsonb
          OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
          OR NEW.effective_to IS DISTINCT FROM OLD.effective_to) THEN
        RAISE EXCEPTION 'immutable Phase 1H scheme version';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase1h_scheme_immutable BEFORE UPDATE ON classification_scheme_versions
      FOR EACH ROW EXECUTE FUNCTION phase1h_immutable_scheme();
    CREATE FUNCTION phase1h_immutable_formal_result() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.formal_provenance_json IS NOT NULL THEN
        RAISE EXCEPTION 'immutable Phase 1H formal result; create a new version';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase1h_classification_immutable
      BEFORE UPDATE OR DELETE ON classification_results
      FOR EACH ROW EXECUTE FUNCTION phase1h_immutable_formal_result();
    CREATE TRIGGER phase1h_rulehit_immutable BEFORE UPDATE OR DELETE ON rule_hits
      FOR EACH ROW EXECUTE FUNCTION phase1h_immutable_formal_result();
    """)


def downgrade():
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM classification_results WHERE "
            "formal_provenance_json IS NOT NULL) OR EXISTS (SELECT 1 FROM rule_hits WHERE "
            "formal_provenance_json IS NOT NULL) OR EXISTS (SELECT 1 FROM rule_versions "
            "WHERE runtime_contract_json IS NOT NULL) OR EXISTS (SELECT 1 FROM "
            "classification_scheme_versions WHERE applicability_json->'phase1h' IS NOT NULL)"
        )
    ):
        raise RuntimeError("archive/export Phase 1H authoritative data before downgrade")
    op.execute(
        "DROP TRIGGER phase1h_rule_immutable ON rule_versions; DROP FUNCTION "
        "phase1h_immutable_rule()"
    )
    op.execute(
        "DROP TRIGGER phase1h_rule_tests_immutable ON rule_test_cases; DROP FUNCTION "
        "phase1h_immutable_tests()"
    )
    op.execute(
        "DROP TRIGGER phase1h_scheme_immutable ON classification_scheme_versions; DROP "
        "FUNCTION phase1h_immutable_scheme()"
    )
    op.execute(
        "DROP TRIGGER phase1h_classification_immutable ON classification_results; DROP "
        "TRIGGER phase1h_rulehit_immutable ON rule_hits; DROP FUNCTION "
        "phase1h_immutable_formal_result()"
    )
    op.drop_index("ix_formal_classification_snapshot", table_name="classification_results")
    op.drop_index("uq_formal_classification_snapshot", table_name="classification_results")
    op.drop_index("ix_rule_runtime_scope", table_name="rule_versions")
    op.drop_constraint("ck_formal_classification_scope", "classification_results", type_="check")
    op.drop_constraint("ck_rule_effective_interval", "rule_versions", type_="check")
    op.drop_constraint("ck_rule_v1_active_gate", "rule_versions", type_="check")
    op.drop_constraint(
        "ck_scheme_effective_interval", "classification_scheme_versions", type_="check"
    )
    for column in ("formal_provenance_json", "analysis_snapshot_id", "project_id"):
        op.drop_column("classification_results", column)
    op.drop_column("rule_hits", "formal_provenance_json")
    op.drop_column("rule_versions", "governance_json")
    op.drop_column("rule_versions", "runtime_contract_json")
