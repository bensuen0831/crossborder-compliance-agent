"""Frozen0018 and fresh PostgreSQL paths, retained consent refusal, exact DDL."""

import json
import os
import subprocess
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_m2b_migrations import complete_catalog
from test_phase1h_migrations import migrate
from test_phase1j_migrations import seed_scope

from crossborder_compliance.config import get_settings

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
BASE = "df3a10923734495d728981f4f319b66afadf8c71"
OLD = "0018_phase1h_multijurisdiction_classification_identity"
HEAD = "0019_stage1_candidate_governance"


def catalog(url):
    result = complete_catalog(url)
    engine = create_engine(url)
    with engine.connect() as c:
        result["candidate_functions"] = c.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND proname LIKE 'stage1_%' ORDER BY proname"
            )
        ).all()
    engine.dispose()
    return result


def test_frozen_migration_bytes_and_single_lineage():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert scripts.get_heads() == [HEAD]
    assert scripts.get_revision(HEAD).down_revision == OLD
    for path in (ROOT / "alembic/versions").glob("*.py"):
        if path.name[:4].isdigit() and int(path.name[:4]) <= 18:
            assert path.read_bytes() == subprocess.check_output(
                ["git", "show", BASE + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            )


def test_fresh_exact0018_equivalence_empty_roundtrip_and_retained_authority(tmp_path):
    source = tmp_path / "frozen0018"
    source.mkdir()
    archive = tmp_path / "source.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["r11_candidate_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = {"head": HEAD, "parent": OLD, "baseline": BASE}
    engines = []
    try:
        with admin.connect() as c:
            for n in names:
                c.execute(text('CREATE DATABASE "' + n + '"'))
        result = migrate(ROOT, urls[0], "upgrade", "head")
        assert result.returncode == 0, result.stderr
        result = migrate(source, urls[1], "upgrade", "head")
        assert result.returncode == 0, result.stderr
        engine, sf, ids = seed_scope(urls[1])
        engines.append(engine)
        tenant, project, version, snapshot, _ = ids
        audit = str(uuid4())
        with engine.begin() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == OLD
            c.execute(
                text(
                    "INSERT INTO audit_events(audit_event_id,tenant_id,workflow_run_id,analysis_snapshot_id,event_type,provenance_json,occurred_at) VALUES(:a,:t,:w,:s,'LEGACY_CONTRACT',CAST(:payload AS json),CURRENT_TIMESTAMP)"
                ),
                {
                    "a": audit,
                    "t": tenant,
                    "w": str(uuid4()),
                    "s": snapshot,
                    "payload": json.dumps({"retained": "exact original authority"}),
                },
            )
            before = dict(
                c.execute(text("SELECT * FROM audit_events WHERE audit_event_id=:a"), {"a": audit})
                .mappings()
                .one()
            )
            old_snapshot = dict(
                c.execute(
                    text("SELECT * FROM analysis_snapshots WHERE analysis_snapshot_id=:id"),
                    {"id": snapshot},
                )
                .mappings()
                .one()
            )
        result = migrate(ROOT, urls[1], "upgrade", "head")
        assert result.returncode == 0, result.stderr
        with engine.connect() as c:
            after = dict(
                c.execute(text("SELECT * FROM audit_events WHERE audit_event_id=:a"), {"a": audit})
                .mappings()
                .one()
            )
            assert {k: after[k] for k in before} == before
            assert (
                after["invocation_scope"] == "LEGACY" and after["candidate_preparation_id"] is None
            )
            assert (
                dict(
                    c.execute(
                        text("SELECT * FROM analysis_snapshots WHERE analysis_snapshot_id=:id"),
                        {"id": snapshot},
                    )
                    .mappings()
                    .one()
                )
                == old_snapshot
            )
        assert catalog(urls[0]) == catalog(urls[1])
        result = migrate(ROOT, urls[1], "downgrade", OLD)
        assert result.returncode == 0, result.stderr
        result = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert result.returncode == 0, result.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        prep = str(uuid4())
        with engine.begin() as c:
            c.execute(
                text("UPDATE project_versions SET status='DRAFT' WHERE project_version_id=:v"),
                {"v": version},
            )
            c.execute(
                text("UPDATE projects SET active_version_id=:v WHERE project_id=:p"),
                {"v": version, "p": project},
            )
            c.execute(
                text(
                    "INSERT INTO candidate_preparations(candidate_preparation_id,tenant_id,project_id,project_version_id,analysis_as_of_date,input_universe_digest,configuration_digest,created_by,created_at,status,record_version,idempotency_key,request_digest) VALUES(:id,:t,:p,:v,'2026-01-01',:d,:d,'real-migration-test-actor',CURRENT_TIMESTAMP,'PREPARING',1,'retained-governance',:d)"
                ),
                {"id": prep, "t": tenant, "p": project, "v": version, "d": "a" * 64},
            )
        before_schema = catalog(urls[1])
        refused = migrate(ROOT, urls[1], "downgrade", OLD)
        assert (
            refused.returncode != 0
            and "STAGE1_CANDIDATE_GOVERNANCE_DOWNGRADE_REFUSED" in refused.stderr
        )
        assert catalog(urls[1]) == before_schema
        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            assert c.scalar(text("SELECT count(*) FROM candidate_preparations")) == 1
        evidence.update(
            fresh=True,
            exact0018_upgrade=True,
            schema_equivalence=True,
            legacy_audit_unchanged=True,
            historical_snapshot_unchanged=True,
            safe_downgrade=True,
            safe_reupgrade=True,
            retained_authority_downgrade_refused=True,
            frozen_migrations_unchanged=True,
        )
        directory = Path(os.environ.get("EVIDENCE_DIR", ROOT / "artifacts/stage1-r1"))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "candidate_governance_migration_measured.json").write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
    finally:
        for e in engines:
            e.dispose()
        with admin.connect() as c:
            for n in names:
                c.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": n},
                )
                c.execute(text('DROP DATABASE IF EXISTS "' + n + '"'))
        admin.dispose()
