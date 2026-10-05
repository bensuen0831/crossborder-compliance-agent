"""Exact Phase1H archive -> Phase1I compared with an independent empty DB."""

import json
import os
import subprocess
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from test_phase1h_migrations import migrate, schema

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b

pytestmark = pytest.mark.runtime_smoke
BASE = "700951ebb9ebdf33e399158fd3fb53bb4a6c87e7"
ROOT = Path(__file__).resolve().parents[1]


def catalog(url):
    result = schema(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        result["phase1i_functions"] = conn.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace"
                " n ON n.oid=p.pronamespace WHERE n.nspname='public' AND proname LIKE"
                " 'phase1i_%' ORDER BY proname"
            )
        ).all()
        result["all_index_definitions"] = conn.execute(
            text(
                "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE"
                " schemaname='public' ORDER BY tablename,indexname"
            )
        ).all()
    engine.dispose()
    return result


def test_phase1i_fresh_verified_0008_equivalence_and_downgrade(tmp_path):
    source = tmp_path / "verified-phase1h"
    source.mkdir()
    archive = tmp_path / "baseline.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    url = make_url(get_settings().database_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["phase1i_fresh_" + uuid4().hex, "phase1i_upgrade_" + uuid4().hex]
    urls = [url.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = {"baseline": BASE, "baseline_revision": "0008_phase1h", "head": "0009_phase1i"}
    try:
        with admin.connect() as conn:
            for n in names:
                conn.execute(text(f'CREATE DATABASE "{n}"'))
        fresh = migrate(ROOT, urls[0], "upgrade", "head")
        assert fresh.returncode == 0, fresh.stderr
        frozen = migrate(source, urls[1], "upgrade", "head")
        assert frozen.returncode == 0, frozen.stderr
        engine = create_engine(urls[1])
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0008_phase1h"
        assert "regulation_applicability_results" not in inspect(engine).get_table_names()
        engine.dispose()
        upgrade = migrate(ROOT, urls[1], "upgrade", "0009_phase1i")
        assert upgrade.returncode == 0, upgrade.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence.update(fresh_upgrade=True, verified_0008_upgrade=True, schema_equivalence=True)
        for u in urls:
            down = migrate(ROOT, u, "downgrade", "0008_phase1h")
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, u, "upgrade", "head")
            assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence["empty_downgrade_roundtrip"] = True
        engine = create_engine(urls[0])
        with engine.begin() as conn:
            tenant, definition = str(uuid4()), str(uuid4())
            conn.execute(
                b.TenantEntity.__table__.insert().values(tenant_id=tenant, name="archive guard")
            )
            conn.execute(
                m.MetadataDefinitionEntity.__table__.insert().values(
                    tenant_id=tenant,
                    definition_id=definition,
                    kind="COUNTRY_PROFILE",
                    code=definition,
                    display_name="retained identity",
                )
            )
        down = migrate(ROOT, urls[0], "downgrade", "0008_phase1h")
        assert down.returncode != 0 and "archive/export" in down.stderr
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0009_phase1i"
            assert conn.scalar(text("SELECT count(*) FROM metadata_definitions")) == 1
        engine.dispose()
        evidence["authoritative_downgrade_refused"] = True
        output = Path(os.getenv("EVIDENCE_DIR", str(ROOT / "artifacts/phase1i-migrations")))
        output.mkdir(parents=True, exist_ok=True)
        (output / "phase1i_migration_dual_path.json").write_text(json.dumps(evidence, indent=2))
    finally:
        with admin.connect() as conn:
            for n in names:
                conn.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": n},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{n}"'))
        admin.dispose()
