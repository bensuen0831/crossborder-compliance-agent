"""Actual frozen 0010 and fresh PostgreSQL catalogs, including provenance guards."""

import json
import os
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_phase1h_migrations import migrate
from test_phase1j_migrations import catalog as historical_catalog
from test_phase1j_migrations import seed_scope

from crossborder_compliance.config import get_settings
from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import models as b

pytestmark = pytest.mark.runtime_smoke
BASE = "83d79c7854b9eca44e85bd15f6ebb0fc9eb9b0a1"
ROOT = Path(__file__).resolve().parents[1]
from alembic.config import Config
from alembic.script import ScriptDirectory
from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after
HEAD = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
assert revision_at_or_after(HEAD, "0011_m2a_intake")


def catalog(url):
    result = historical_catalog(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        result["m2a_functions"] = conn.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p "
                "JOIN pg_namespace n ON p.pronamespace=n.oid "
                "WHERE n.nspname='public' AND proname LIKE 'm2a_%' ORDER BY proname"
            )
        ).all()
    engine.dispose()
    return result


def test_m2a_fresh_exact_0010_equivalence_downgrade_and_refusal(tmp_path):
    archive, source = tmp_path / "baseline.tar", tmp_path / "baseline"
    source.mkdir()
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    baseurl = make_url(get_settings().database_url)
    admin = create_engine(baseurl.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["m2a_migration_" + uuid4().hex for _ in range(2)]
    urls = [baseurl.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = {"baseline": BASE, "baseline_revision": "0010_phase1j", "head": HEAD}
    try:
        with admin.connect() as conn:
            for n in names:
                conn.execute(text('CREATE DATABASE "' + n + '"'))
        fresh = migrate(ROOT, urls[0], "upgrade", "head")
        assert fresh.returncode == 0, fresh.stderr
        frozen = migrate(source, urls[1], "upgrade", "head")
        assert frozen.returncode == 0, frozen.stderr
        engine = create_engine(urls[1])
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0010_phase1j"
            assert not conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='business_facts' AND column_name='structured_provenance_json'"
                )
            )
        engine.dispose()
        upgrade = migrate(ROOT, urls[1], "upgrade", "head")
        assert upgrade.returncode == 0, upgrade.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence.update(fresh=True, exact_0010_upgrade=True, schema_equivalence=True)
        for url in urls:
            down = migrate(ROOT, url, "downgrade", "0010_phase1j")
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, url, "upgrade", "head")
            assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence["empty_downgrade_reupgrade"] = True
        engine, sf, ids = seed_scope(urls[0])
        tenant, project, version, snapshot, _ = ids
        now = datetime.now(UTC).isoformat()
        with sf() as s, s.begin():
            row = s.get(b.ProjectVersionEntity, version)
            row.status = "CONFIRMED"
            row.intake_json = {"business_purpose": "user fact"}
            snap = s.get(b.AnalysisSnapshotEntity, snapshot)
            snap.provenance_json = {
                "intake_version": 1,
                "confirmed_by": "author",
                "confirmed_at": now,
            }
            s.flush()
            s.add(
                e.BusinessFactEntity(
                    fact_id=str(uuid4()),
                    tenant_id=tenant,
                    project_id=project,
                    fact_type="TEST_FACT",
                    normalized_value_json="user fact",
                    original_values_json=["user fact"],
                    source_document_ids_json=[],
                    normalized_key="user fact",
                    resolution_method="STRUCTURED_CONFIRMED",
                    confidence=1,
                    validation_status="VALIDATED",
                    review_required=False,
                    version=1,
                    structured_provenance_json=[
                        dict(
                            source_type="USER_INPUT",
                            source_ref=version,
                            source_version="1",
                            source_locator="business_purpose",
                            actor_ref="author",
                            request_id=snapshot,
                            generated_by="StructuredIntakeFormalization",
                            generated_at=now,
                        )
                    ],
                )
            )
        before = catalog(urls[0])
        refusal = migrate(ROOT, urls[0], "downgrade", "0010_phase1j")
        assert refusal.returncode != 0 and "archive/export" in refusal.stderr
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        assert catalog(urls[0]) == before
        evidence["authoritative_data_transactional_refusal"] = True
        engine.dispose()
        output = Path(os.getenv("EVIDENCE_DIR", str(ROOT / "artifacts/m2a")))
        output.mkdir(parents=True, exist_ok=True)
        (output / "m2a_migration_dual_path.json").write_text(json.dumps(evidence, indent=2) + "\n")
    finally:
        with admin.connect() as conn:
            for n in names:
                conn.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": n},
                )
                conn.execute(text('DROP DATABASE IF EXISTS "' + n + '"'))
        admin.dispose()
