"""Canonical review context/history and forward-only correction lineage."""
from alembic import op
from sqlalchemy import inspect, text

revision = "0015_m2d_review_governance"
down_revision = "0014_m2c_formal_result_authority"
branch_labels = None
depends_on = None

COLUMNS = {
    "owning_stage": "varchar(40)",
    "reason_codes_json": "json NOT NULL DEFAULT '[]'",
    "evidence_ids_json": "json NOT NULL DEFAULT '[]'",
    "legal_basis_ids_json": "json NOT NULL DEFAULT '[]'",
    "required_role": "varchar(120) NOT NULL DEFAULT 'workflow:review'",
    "requirement_confirmation": "boolean NOT NULL DEFAULT false",
}


def upgrade():
    columns = {c["name"] for c in inspect(op.get_bind()).get_columns("review_tasks")}
    for name, definition in COLUMNS.items():
        if name not in columns:
            op.execute(f"ALTER TABLE review_tasks ADD COLUMN {name} {definition}")
    history_columns = {c["name"] for c in inspect(op.get_bind()).get_columns("review_decisions")}
    if "decision_payload_json" not in history_columns:
        op.execute("ALTER TABLE review_decisions ADD COLUMN decision_payload_json json NOT NULL DEFAULT '{}' ")
    # Historical0002 reads live metadata: reuse the exact mapped table for both paths.
    from crossborder_compliance.infrastructure.persistence.review_models import ReviewCorrectionEntity
    ReviewCorrectionEntity.__table__.create(op.get_bind(), checkfirst=True)
    op.execute("""CREATE OR REPLACE FUNCTION m2d_review_history_immutable() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable review governance history'; END $$""")
    for table in ("review_decisions", "review_corrections"):
        op.execute(f"DROP TRIGGER IF EXISTS m2d_history_immutable ON {table}")
        op.execute(f"CREATE TRIGGER m2d_history_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION m2d_review_history_immutable()")


def downgrade():
    conn = op.get_bind()
    if conn.scalar(text("SELECT EXISTS(SELECT 1 FROM review_corrections) OR EXISTS(SELECT 1 FROM review_decisions) OR EXISTS(SELECT 1 FROM review_tasks WHERE owning_stage IS NOT NULL)")):
        raise RuntimeError("M2-D authority retained: archive/export required before downgrade")
    for table in ("review_decisions", "review_corrections"):
        op.execute(f"DROP TRIGGER IF EXISTS m2d_history_immutable ON {table}")
    op.execute("DROP FUNCTION m2d_review_history_immutable()")
    op.drop_table("review_corrections")
    op.drop_column("review_decisions", "decision_payload_json")
    for name in reversed(COLUMNS):
        op.drop_column("review_tasks", name)
