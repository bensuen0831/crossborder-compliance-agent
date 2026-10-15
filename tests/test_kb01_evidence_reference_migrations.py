"""Lossless canonical source-reference widening, exact pins and safe downgrade refusal."""

import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_kb01_taxonomy_migrations import catalog
from test_phase1h_migrations import migrate

from crossborder_compliance.config import get_settings

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_SOURCE = "e012d2a35c68e1c1ad9ccec879d78e5a45ffc208"
PARENT = "0022_kb01_binary_transport"
HEAD = "0023_kb01_evidence_source_reference"
INSERT_EVIDENCE = (
    "INSERT INTO evidence_references(evidence_id,tenant_id,evidence_type,source_ref,"
    "validation_status,record_version,status,created_at,updated_at) "
    "VALUES(:id,:tenant,'SYNTHETIC_MIGRATION_DATA',:ref,'UNVALIDATED',1,'ACTIVE',now(),now())"
)


def test_evidence_source_reference_has_single_head_and_frozen_0001_0022():
    scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert scripts.get_heads() == [HEAD]
    assert scripts.get_revision(HEAD).down_revision == PARENT
    for path in sorted((ROOT / "alembic/versions").glob("*.py")):
        if path.name[:4].isdigit() and int(path.name[:4]) <= 22:
            assert path.read_bytes() == subprocess.check_output(
                ["git", "show", PREVIOUS_SOURCE + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            )


def evidence_digest(engine):
    with engine.connect() as connection:
        rows = [
            dict(row._mapping)
            for row in connection.execute(
                text("SELECT * FROM evidence_references ORDER BY evidence_id")
            )
        ]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def test_reference_fresh_exact0022_preservation_equivalence_and_downgrade(tmp_path):
    previous = tmp_path / "previous"
    previous.mkdir()
    archive = tmp_path / "previous.tar"
    with archive.open("wb") as output:
        subprocess.run(["git", "archive", PREVIOUS_SOURCE], cwd=ROOT, stdout=output, check=True)
    with tarfile.open(archive) as source:
        source.extractall(previous, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["kb01_reference_matrix_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=name).render_as_string(hide_password=False) for name in names]
    engine = None
    try:
        with admin.connect() as connection:
            for name in names:
                connection.execute(text('CREATE DATABASE "' + name + '"'))
        fresh = migrate(ROOT, urls[0], "upgrade", HEAD)
        assert fresh.returncode == 0, fresh.stderr
        exact = migrate(previous, urls[1], "upgrade", PARENT)
        assert exact.returncode == 0, exact.stderr
        engine = create_engine(urls[1])
        identity, tenant = str(uuid4()), str(uuid4())
        old = json.dumps(
            {
                "source_class": "SYNTHETIC_MIGRATION_DATA",
                "locator": "/article/1",
                "content_sha256": "a" * 64,
            },
            sort_keys=True,
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tenants(tenant_id,name,record_version,status,"
                    "created_at,updated_at) "
                    "VALUES(:id,'Synthetic reference preservation',1,'ACTIVE',now(),now())"
                ),
                {"id": tenant},
            )
            connection.execute(
                text(INSERT_EVIDENCE),
                {"id": identity, "tenant": tenant, "ref": old},
            )
        before = evidence_digest(engine)
        upgraded = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert upgraded.returncode == 0, upgraded.stderr
        assert evidence_digest(engine) == before
        assert catalog(urls[0]) == catalog(urls[1])
        down = migrate(ROOT, urls[1], "downgrade", PARENT)
        assert down.returncode == 0, down.stderr
        assert evidence_digest(engine) == before
        up = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert up.returncode == 0, up.stderr
        assert evidence_digest(engine) == before
        long_reference = json.dumps(
            {
                "source_class": "SYNTHETIC_MIGRATION_DATA",
                "pinned_source_refs": [str(uuid4()) for _ in range(200)],
            },
            sort_keys=True,
        )
        assert 2704 < len(long_reference.encode()) < 32768
        with engine.begin() as connection:
            connection.execute(
                text(INSERT_EVIDENCE),
                {"id": str(uuid4()), "tenant": tenant, "ref": long_reference},
            )
        # Full source bytes remain authority; a fixed-width non-unique index is
        # only an accelerator and does not replace/alter the persisted reference.
        digest = evidence_digest(engine)
        refusal = migrate(ROOT, urls[1], "downgrade", PARENT)
        assert refusal.returncode != 0
        assert "KB01_EVIDENCE_REFERENCE_DOWNGRADE_REFUSED" in refusal.stderr
        assert evidence_digest(engine) == digest
        assert catalog(urls[0]) == catalog(urls[1])
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as connection:
            for name in names:
                connection.execute(text('DROP DATABASE IF EXISTS "' + name + '" WITH (FORCE)'))
        admin.dispose()
