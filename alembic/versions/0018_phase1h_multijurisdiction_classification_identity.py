"""Align Phase1H formal result uniqueness with its jurisdiction-scoped identity."""

import sqlalchemy as sa

from alembic import op

revision = "0018_phase1h_multijurisdiction_classification_identity"
down_revision = "0017_m2e_external_agent_api"
branch_labels = None
depends_on = None

INDEX = "uq_formal_classification_snapshot"
LEGACY_KEY = ["tenant_id", "project_id", "analysis_snapshot_id", "subject_id", "scheme_version_id"]
FORMAL_PREDICATE = sa.text("formal_provenance_json IS NOT NULL")


def upgrade():
    # Transactional DDL and an exclusive table lock prevent competing writes
    # throughout replacement. No result identity or payload is rewritten.
    op.execute("LOCK TABLE classification_results IN ACCESS EXCLUSIVE MODE")
    op.drop_index(INDEX, table_name="classification_results")
    op.create_index(
        INDEX,
        "classification_results",
        [*LEGACY_KEY[:-1], "jurisdiction_id", LEGACY_KEY[-1]],
        unique=True,
        postgresql_where=FORMAL_PREDICATE,
    )


def downgrade():
    # Hold the same lock before checking, so a new A/B pair cannot race the
    # refusal check. Refuse before touching the index; rollback preserves rows.
    op.execute("LOCK TABLE classification_results IN ACCESS EXCLUSIVE MODE")
    collision = op.get_bind().scalar(
        sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM classification_results
            WHERE formal_provenance_json IS NOT NULL
            GROUP BY tenant_id, project_id, analysis_snapshot_id, subject_id, scheme_version_id
            HAVING COUNT(*) > 1
        )
    """)
    )
    if collision:
        raise RuntimeError(
            "R1 classification identity downgrade refused: multi-jurisdiction formal "
            "classification results would violate legacy uniqueness"
        )
    op.drop_index(INDEX, table_name="classification_results")
    op.create_index(
        INDEX, "classification_results", LEGACY_KEY, unique=True, postgresql_where=FORMAL_PREDICATE
    )
