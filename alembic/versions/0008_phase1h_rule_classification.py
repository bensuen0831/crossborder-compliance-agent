"""Safe rule contract and formal provenance, extending canonical tables only.

Legacy Phase 1B/1C configuration rows remain readable and are not executable V1 rules.
Downgrade refuses to discard Phase 1H authoritative results/published rules.
"""
from alembic import op
import sqlalchemy as sa

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
        elif columns[column.name]["nullable"] != column.nullable or columns[column.name]["type"]._type_affinity is not column.type._type_affinity:
            raise RuntimeError(f"incompatible existing column: {table}.{column.name}")
    add("rule_versions", sa.Column("runtime_contract_json", sa.JSON(), nullable=True))
    add("rule_versions", sa.Column("governance_json", sa.JSON(), nullable=True))
    add("rule_hits", sa.Column("formal_provenance_json", sa.JSON(), nullable=True))
    add("classification_results", sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.project_id"), nullable=True))
    add("classification_results", sa.Column("analysis_snapshot_id", sa.String(36), sa.ForeignKey("analysis_snapshots.analysis_snapshot_id"), nullable=True))
    add("classification_results", sa.Column("formal_provenance_json", sa.JSON(), nullable=True))
    op.create_check_constraint("ck_rule_effective_interval", "rule_versions", "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from")
    op.create_check_constraint("ck_formal_classification_scope", "classification_results", "formal_provenance_json IS NULL OR (project_id IS NOT NULL AND analysis_snapshot_id IS NOT NULL)")
    op.create_index("ix_rule_runtime_scope", "rule_versions", ["tenant_id", "lifecycle_status", "effective_from", "effective_to"])
    op.create_index("ix_formal_classification_snapshot", "classification_results", ["tenant_id", "project_id", "analysis_snapshot_id"])
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
    """)


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM classification_results WHERE formal_provenance_json IS NOT NULL) OR EXISTS (SELECT 1 FROM rule_versions WHERE runtime_contract_json IS NOT NULL AND lifecycle_status <> 'DRAFT')")):
        raise RuntimeError("archive/export Phase 1H authoritative data before downgrade")
    op.execute("DROP TRIGGER phase1h_rule_immutable ON rule_versions; DROP FUNCTION phase1h_immutable_rule()")
    op.drop_index("ix_formal_classification_snapshot", table_name="classification_results")
    op.drop_index("ix_rule_runtime_scope", table_name="rule_versions")
    op.drop_constraint("ck_formal_classification_scope", "classification_results", type_="check")
    op.drop_constraint("ck_rule_effective_interval", "rule_versions", type_="check")
    for column in ("formal_provenance_json", "analysis_snapshot_id", "project_id"):
        op.drop_column("classification_results", column)
    op.drop_column("rule_hits", "formal_provenance_json")
    op.drop_column("rule_versions", "governance_json")
    op.drop_column("rule_versions", "runtime_contract_json")
