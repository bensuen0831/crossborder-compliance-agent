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
from crossborder_compliance.infrastructure.persistence import metadata_models as m

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
BASE = "42571c7148456f41adb64d2528c169a357214a25"
from alembic.script import ScriptDirectory
from crossborder_compliance.infrastructure.persistence.migration_lineage import revision_at_or_after
HEAD = ScriptDirectory(str(ROOT / "alembic")).get_current_head()
assert revision_at_or_after(HEAD, "0014_m2c_formal_result_authority")


def catalog(url):
    result = complete_catalog(url)
    with create_engine(url).connect() as conn:
        result["c0_functions"] = conn.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p "
                "JOIN pg_namespace n ON p.pronamespace=n.oid "
                "WHERE n.nspname='public' AND proname LIKE 'phase1c0_%' ORDER BY proname"
            )
        ).all()
    return result


def test_fresh_exact_0013_equivalence_empty_down_up_retention(tmp_path):
    source = tmp_path / "verified0013"
    source.mkdir()
    archive = tmp_path / "source.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["m2c_migration_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = dict(base_sha=BASE, from_revision="0013_m2b_context_temporal_contract", head=HEAD)
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
                == "0013_m2b_context_temporal_contract"
            )
        up = migrate(ROOT, urls[1], "upgrade", "head")
        assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence.update(fresh=True, exact_0013_upgrade=True, schema_equivalence=True)
        for url in urls:
            down = migrate(ROOT, url, "downgrade", "0013_m2b_context_temporal_contract")
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, url, "upgrade", "head")
            assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence["empty_downgrade_reupgrade"] = True
        engine, sf, ids = seed_scope(urls[0])
        definition, version = str(uuid4()), str(uuid4())
        with sf() as s, s.begin():
            s.add(
                m.MetadataDefinitionEntity(
                    definition_id=definition,
                    tenant_id=ids[0],
                    kind="CROSS_BORDER_ASSESSMENT_POLICY",
                    code="RETAINED",
                    display_name="Retained policy draft",
                )
            )
            s.flush()
            s.add(
                m.MetadataVersionEntity(
                    version_id=version,
                    tenant_id=ids[0],
                    definition_id=definition,
                    version_no=1,
                    lifecycle_status="DRAFT",
                    payload_json={},
                    created_by="author",
                )
            )
        before = catalog(urls[0])
        refusal = migrate(ROOT, urls[0], "downgrade", "0013_m2b_context_temporal_contract")
        assert refusal.returncode != 0 and "archive/export" in refusal.stderr
        assert catalog(urls[0]) == before
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        evidence["retained_authority_transactional_refusal"] = True
        output = ROOT / "artifacts/m2c"
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
