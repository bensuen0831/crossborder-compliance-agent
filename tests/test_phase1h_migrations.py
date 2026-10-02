"""Verify frozen-baseline and fresh upgrade paths on distinct disposable PostgreSQL DBs."""

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b

pytestmark = pytest.mark.runtime_smoke
BASE = "f563e5067308e7eab6d3f89321b8b30da7c39044"
ROOT = Path(__file__).resolve().parents[1]


def migrate(root, url, *arguments):
    variables = dict(os.environ, DATABASE_URL=url, PYTHONPATH=f"{root / 'src'}:{root}")
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=root,
        env=variables,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return completed


def schema(url):
    engine = create_engine(url)
    inspector = inspect(engine)
    result = {}
    for table in sorted(inspector.get_table_names()):
        result[table] = {
            "columns": sorted(
                (c["name"], str(c["type"]), c["nullable"], c["default"])
                for c in inspector.get_columns(table)
            ),
            "pk": inspector.get_pk_constraint(table)["constrained_columns"],
            "foreign_keys": sorted(
                (
                    tuple(k["constrained_columns"]),
                    k["referred_table"],
                    tuple(k["referred_columns"]),
                    json.dumps(k["options"], sort_keys=True),
                )
                for k in inspector.get_foreign_keys(table)
            ),
            "unique": sorted(
                (k["name"], tuple(k["column_names"]))
                for k in inspector.get_unique_constraints(table)
            ),
            "checks": sorted(
                (k["name"], k["sqltext"]) for k in inspector.get_check_constraints(table)
            ),
            "indexes": sorted(
                (k["name"], tuple(k["column_names"]), k["unique"])
                for k in inspector.get_indexes(table)
            ),
        }
    with engine.connect() as conn:
        # PostgreSQL's catalog retains exact pgvector type/dimension information
        # that SQLAlchemy's generic inspector cannot reflect without an adapter.
        result["catalog_columns"] = conn.execute(
            text(
                "SELECT "
                "c.relname, a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull, "
                "a.attidentity, a.attgenerated FROM pg_attribute a JOIN pg_class c ON "
                "c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE "
                "n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT "
                "a.attisdropped ORDER BY c.relname,a.attname"
            )
        ).all()
        result["triggers"] = conn.execute(
            text(
                "SELECT "
                "event_object_table, trigger_name, action_timing, event_manipulation, "
                "action_statement FROM information_schema.triggers WHERE trigger_schema='public' "
                "ORDER BY 1,2,4"
            )
        ).all()
        result["functions"] = conn.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON "
                "n.oid=p.pronamespace WHERE n.nspname='public' AND proname LIKE 'phase1h_%' "
                "ORDER BY proname"
            )
        ).all()
    engine.dispose()
    return result


def test_fresh_and_frozen_0007_paths_equivalent_and_downgrade(tmp_path):
    source = tmp_path / "verified-baseline"
    source.mkdir()
    archive = tmp_path / "baseline.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    url = make_url(get_settings().database_url)
    assert url.drivername.startswith("postgresql"), "migration dual-path check requires PostgreSQL"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["phase1h_fresh_" + uuid4().hex, "phase1h_upgrade_" + uuid4().hex]
    urls = [url.set(database=name).render_as_string(hide_password=False) for name in names]
    evidence = {
        "verified_baseline": BASE,
        "fresh_upgrade": False,
        "baseline_upgrade": False,
        "schema_equivalence": False,
        "empty_downgrade_roundtrip": False,
        "authoritative_data_downgrade_refused": False,
    }
    try:
        with admin.connect() as conn:
            for name in names:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
        fresh = migrate(ROOT, urls[0], "upgrade", "head")
        assert fresh.returncode == 0, fresh.stderr
        evidence["fresh_upgrade"] = True
        frozen = migrate(source, urls[1], "upgrade", "head")
        assert frozen.returncode == 0, frozen.stderr
        old_engine = create_engine(urls[1])
        with old_engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0007_phase1g"
        assert "formal_provenance_json" not in {
            c["name"] for c in inspect(old_engine).get_columns("rule_hits")
        }
        old_engine.dispose()
        upgraded = migrate(ROOT, urls[1], "upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr
        evidence["baseline_upgrade"] = True
        assert schema(urls[0]) == schema(urls[1])
        evidence["schema_equivalence"] = True
        for database_url in urls:
            result = migrate(ROOT, database_url, "downgrade", "0007_phase1g")
            assert result.returncode == 0, result.stderr
            result = migrate(ROOT, database_url, "upgrade", "head")
            assert result.returncode == 0, result.stderr
        assert schema(urls[0]) == schema(urls[1])
        evidence["empty_downgrade_roundtrip"] = True
        engine = create_engine(urls[0])
        # A governed version represents retained authoritative data, even before ACTIVE.
        with engine.begin() as conn:
            tenant, definition, version = [str(uuid4()) for _ in range(3)]
            conn.execute(
                b.TenantEntity.__table__.insert().values(tenant_id=tenant, name="downgrade guard")
            )
            conn.execute(
                m.RuleDefinitionEntity.__table__.insert().values(
                    rule_definition_id=definition,
                    tenant_id=tenant,
                    code=definition,
                    display_name="guard",
                )
            )
            conn.execute(
                m.RuleVersionEntity.__table__.insert().values(
                    rule_version_id=version,
                    rule_definition_id=definition,
                    tenant_id=tenant,
                    version_no=1,
                    lifecycle_status="APPROVED",
                    safe_dsl_json={},
                    scope_json={},
                    priority=1,
                    runtime_contract_json={},
                )
            )
        refusal = migrate(ROOT, urls[0], "downgrade", "0007_phase1g")
        assert refusal.returncode != 0 and "archive/export" in refusal.stderr
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0008_phase1h"
            assert conn.scalar(text("SELECT count(*) FROM rule_versions")) == 1
        engine.dispose()
        evidence["authoritative_data_downgrade_refused"] = True
        output = Path(os.getenv("EVIDENCE_DIR", str(ROOT / "artifacts/phase1h-migrations")))
        output.mkdir(parents=True, exist_ok=True)
        (output / "phase1h_migration_dual_path.json").write_text(json.dumps(evidence, indent=2))
    finally:
        with admin.connect() as conn:
            for name in names:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name"
                    ),
                    {"name": name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()
