"""Real frozen0015/fresh PostgreSQL equivalence, reversibility and authority retention."""

import json
import subprocess
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_m2d_migrations import catalog as previous_catalog
from test_phase1h_migrations import migrate
from test_phase1j_migrations import seed_scope

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
BASE = "efda0955342de8d1ea36aa0f754d63c9b421fec8"
HEAD = ScriptDirectory(str(ROOT / "alembic")).get_current_head()
assert revision_at_or_after(HEAD, "0016_phase1kb_multi_provider_llm_governance")


def catalog(url):
    result = previous_catalog(url)
    with create_engine(url).connect() as c:
        result["phase1kb_functions"] = c.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p "
                "JOIN pg_namespace n ON p.pronamespace=n.oid "
                "WHERE n.nspname='public' AND proname LIKE 'phase1kb_%' ORDER BY proname"
            )
        ).all()
    return result


def test_fresh_exact0015_equivalence_empty_downgrade_reupgrade_and_retention(tmp_path):
    source = tmp_path / "verified0015"
    source.mkdir()
    archive = tmp_path / "source.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    for frozen in (source / "alembic/versions").glob("*.py"):
        assert frozen.read_bytes() == (ROOT / "alembic/versions" / frozen.name).read_bytes()
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["phase1kb_migration_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=n).render_as_string(hide_password=False) for n in names]
    measured = dict(base_sha=BASE, from_revision="0015_m2d_review_governance", head=HEAD)
    try:
        with admin.connect() as c:
            for n in names:
                c.execute(text('CREATE DATABASE "' + n + '"'))
        fresh = migrate(ROOT, urls[0], "upgrade", "head")
        assert fresh.returncode == 0, fresh.stderr
        frozen = migrate(source, urls[1], "upgrade", "head")
        assert frozen.returncode == 0, frozen.stderr
        with create_engine(urls[1]).connect() as c:
            assert (
                c.scalar(text("SELECT version_num FROM alembic_version"))
                == measured["from_revision"]
            )
        upgraded = migrate(ROOT, urls[1], "upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        measured.update(
            fresh=True,
            exact0015_upgrade=True,
            schema_equivalence=True,
            frozen_migrations_unchanged=True,
        )
        for url in urls:
            down = migrate(ROOT, url, "downgrade", measured["from_revision"])
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, url, "upgrade", "head")
            assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        measured["empty_downgrade_reupgrade"] = True
        engine, sessions, ids = seed_scope(urls[0])
        with sessions() as s, s.begin():
            s.add(
                m.AnalysisSnapshotRegistryPinEntity(
                    pin_id=str(uuid4()),
                    tenant_id=ids[0],
                    analysis_snapshot_id=ids[3],
                    pin_type="LLM_SELECTION",
                    logical_key="configured",
                    object_id=str(uuid4()),
                    version_id=str(uuid4()),
                    version_no=1,
                )
            )
        before = catalog(urls[0])
        refused = migrate(ROOT, urls[0], "downgrade", measured["from_revision"])
        assert refused.returncode != 0 and "archive/export" in refused.stderr
        assert catalog(urls[0]) == before
        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        measured["authoritative_pins_transactional_refusal"] = True
        engine.dispose()
        output = ROOT / "artifacts/phase1kb"
        output.mkdir(parents=True, exist_ok=True)
        (output / "migration_dual_path.json").write_text(json.dumps(measured, indent=2) + "\n")
    finally:
        with admin.connect() as c:
            for n in names:
                c.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": n},
                )
                c.execute(text('DROP DATABASE IF EXISTS "' + n + '"'))
        admin.dispose()
