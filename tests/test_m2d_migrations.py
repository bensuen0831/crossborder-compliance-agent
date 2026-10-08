"""Actual frozen0013/fresh paths, catalogs, reversible empty schema, retention."""

import json
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
BASE = "0dc005e583465a4604a5d40a369cb5fc2f0ccbef"
from alembic.script import ScriptDirectory

from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after

HEAD = ScriptDirectory(str(ROOT / "alembic")).get_current_head()
assert revision_at_or_after(HEAD, "0015_m2d_review_governance")


def catalog(url):
    result = complete_catalog(url)
    with create_engine(url).connect() as conn:
        result["review_functions"] = conn.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p "
                "JOIN pg_namespace n ON p.pronamespace=n.oid "
                "WHERE n.nspname='public' AND proname LIKE 'm2d_%' ORDER BY proname"
            )
        ).all()
    return result


def test_fresh_exact_0014_equivalence_empty_down_up_retention(tmp_path):
    source = tmp_path / "verified0014"
    source.mkdir()
    archive = tmp_path / "source.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["m2d_migration_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = dict(base_sha=BASE, from_revision="0014_m2c_formal_result_authority", head=HEAD)
    try:
        with admin.connect() as conn:
            for n in names:
                conn.execute(text('CREATE DATABASE "' + n + '"'))
        fresh = migrate(ROOT, urls[0], "upgrade", "head")
        assert fresh.returncode == 0, fresh.stderr
        frozen = migrate(source, urls[1], "upgrade", "head")
        assert frozen.returncode == 0, frozen.stderr
        with create_engine(urls[1]).connect() as conn:
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version"))
                == "0014_m2c_formal_result_authority"
            )
        up = migrate(ROOT, urls[1], "upgrade", "head")
        assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence.update(fresh=True, exact_0014_upgrade=True, schema_equivalence=True)
        for url in urls:
            down = migrate(ROOT, url, "downgrade", "0014_m2c_formal_result_authority")
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, url, "upgrade", "head")
            assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence["empty_downgrade_reupgrade"] = True
        engine, sf, ids = seed_scope(urls[0])
        from crossborder_compliance.infrastructure.persistence import models as b

        review, run = str(uuid4()), str(uuid4())
        with sf() as s, s.begin():
            s.add(
                b.WorkflowRunEntity(
                    workflow_run_id=run,
                    thread_id=run,
                    tenant_id=ids[0],
                    analysis_snapshot_id=ids[3],
                    status="REVIEW_REQUIRED",
                    graph_definition_version="phase1l-a-canonical-v2",
                    state_schema_version="2.0",
                    langgraph_runtime_version="test",
                    checkpointer_version="test",
                )
            )
            s.flush()
            s.add(
                b.ReviewTaskEntity(
                    review_id=review,
                    workflow_run_id=run,
                    thread_id=run,
                    tenant_id=ids[0],
                    review_type="WORKFLOW_STAGE_REVIEW",
                    object_type="WORKFLOW_RUN",
                    object_id=run,
                    reason="Retained review",
                    owning_stage="requirement",
                    status="PENDING",
                    idempotency_key=review,
                )
            )
        before = catalog(urls[0])
        refusal = migrate(ROOT, urls[0], "downgrade", "0014_m2c_formal_result_authority")
        assert refusal.returncode != 0 and "archive/export" in refusal.stderr
        assert catalog(urls[0]) == before
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        evidence["retained_authority_transactional_refusal"] = True
        output = ROOT / "artifacts/m2d"
        output.mkdir(parents=True, exist_ok=True)
        (output / "migration_dual_path.json").write_text(json.dumps(evidence, indent=2) + "\n")
        engine.dispose()
    finally:
        with admin.connect() as conn:
            for n in names:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name"
                    ),
                    dict(name=n),
                )
                conn.execute(text('DROP DATABASE IF EXISTS "' + n + '"'))
        admin.dispose()
