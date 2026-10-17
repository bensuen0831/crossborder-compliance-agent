"""Preserve complete original/pinned Knowledge provenance in the canonical Evidence reference."""

import sqlalchemy as sa

from alembic import op

revision = "0023_kb01_evidence_source_reference"
down_revision = "0022_kb01_binary_transport"
branch_labels = None
depends_on = None


def upgrade():
    # Lossless widening only: no row/identity/digest/pin rewrite and no new owner.
    op.alter_column(
        "evidence_references",
        "source_ref",
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=False,
    )
    # Frozen0002 bootstraps live model metadata on fresh databases. Its bytes
    # remain untouched; accept only this exact already-created forward check.
    existing_check = op.get_bind().scalar(
        sa.text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='evidence_references'::regclass "
            "AND conname='ck_evidence_source_reference_bytes'"
        )
    )
    if existing_check is None:
        op.create_check_constraint(
            "ck_evidence_source_reference_bytes",
            "evidence_references",
            "octet_length(source_ref) <= 32768",
        )
    elif (
        "".join(existing_check.split()).replace("(", "").replace(")", "")
        != "CHECKoctet_lengthsource_ref<=32768"
    ):
        raise RuntimeError("KB01_EVIDENCE_REFERENCE_CHECK_MISMATCH")
    # A full reference may exceed PostgreSQL's B-tree tuple size. This fixed
    # width non-unique accelerator is not Evidence identity/digest authority.
    op.drop_index("ix_evidence_source", table_name="evidence_references")
    op.create_index(
        "ix_evidence_source", "evidence_references", ["tenant_id", sa.text("md5(source_ref)")]
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM evidence_references WHERE char_length(source_ref) > 500)"
        )
    ):
        raise RuntimeError("KB01_EVIDENCE_REFERENCE_DOWNGRADE_REFUSED")
    op.drop_constraint("ck_evidence_source_reference_bytes", "evidence_references", type_="check")
    op.drop_index("ix_evidence_source", table_name="evidence_references")
    op.alter_column(
        "evidence_references",
        "source_ref",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=False,
    )
    op.create_index("ix_evidence_source", "evidence_references", ["tenant_id", "source_ref"])
