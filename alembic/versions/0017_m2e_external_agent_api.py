"""Northbound integration identity and durable technical delivery authority."""
from sqlalchemy import text
from alembic import op
from crossborder_compliance.infrastructure.persistence.integration_models import MODELS

revision = "0017_m2e_external_agent_api"
down_revision = "0016_phase1kb_multi_provider_llm_governance"
branch_labels = None
depends_on = None


def upgrade():
    #0002 imports live metadata: create(checkfirst) keeps fresh/exact0016 equivalent.
    for model in MODELS:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Do not drop identities, revocation records, subscriptions or delivery audit.
    if any(op.get_bind().scalar(text(f'SELECT EXISTS(SELECT 1 FROM "{m.__tablename__}")')) for m in MODELS):
        raise RuntimeError("M2-E integration records retained: archive/export before downgrade")
    for model in reversed(MODELS):
        model.__table__.drop(op.get_bind(), checkfirst=True)
