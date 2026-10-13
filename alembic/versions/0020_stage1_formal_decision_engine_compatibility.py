"""Explicit historical/current engine versions on the five existing authorities."""
from alembic import op
import sqlalchemy as sa

revision = "0020_stage1_formal_decision_engine_compatibility"
down_revision = "0019_stage1_candidate_governance"
branch_labels = None
depends_on = None

TABLES = {
    "obligation": "compliance_obligation_results",
    "candidate_path": "candidate_compliance_path_results",
    "risk": "risk_assessment_results",
    "recommendation": "compliance_recommendation_results",
    "final_path": "final_compliance_path_results",
}

def upgrade():
    for kind,table in TABLES.items():
        name="ck_j_"+kind+"_version"
        op.drop_constraint(name,table,type_="check")
        op.create_check_constraint(name,table,"contract_version='2.0' AND engine_version IN ('FORMAL_DECISION_V2','FORMAL_DECISION_V2_1')")

def downgrade():
    bind=op.get_bind()
    # Check all authorities before changing any constraint or deleting anything.
    for table in TABLES.values():
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE engine_version='FORMAL_DECISION_V2_1')")).scalar():
            raise RuntimeError("STAGE1_FORMAL_DECISION_COMPATIBILITY_DOWNGRADE_REFUSED: corrected decision authority would become invalid")
    for kind,table in TABLES.items():
        name="ck_j_"+kind+"_version"
        op.drop_constraint(name,table,type_="check")
        op.create_check_constraint(name,table,"contract_version='2.0' AND engine_version='FORMAL_DECISION_V2'")
