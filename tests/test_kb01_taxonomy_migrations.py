"""Fresh and exact release-schema upgrades preserve authority and refuse audit loss."""

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from test_m2b_migrations import complete_catalog
from test_phase1h_migrations import migrate

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.knowledge_management import CreateTaxonomy
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    PostgresKnowledgeTaxonomyRepository,
)

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
BASE = "060cbb5a20a9f8f70fa88dbefb8b5feb404c460d"
HEAD = "0021_kb01_taxonomy_operations"
PARENT = "0020_stage1_formal_decision_engine_compatibility"


def test_kb01_single_head_and_frozen_0001_0020():
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert script.get_heads() == ["0023_kb01_evidence_source_reference"]
    assert (
        script.get_revision("0023_kb01_evidence_source_reference").down_revision
        == "0022_kb01_binary_transport"
    )
    assert script.get_revision("0022_kb01_binary_transport").down_revision == HEAD
    assert script.get_revision(HEAD).down_revision == PARENT
    paths = [
        p
        for p in (ROOT / "alembic/versions").glob("*.py")
        if p.name[:4].isdigit() and int(p.name[:4]) <= 20
    ]
    assert len(paths) == 20
    for path in paths:
        assert path.read_bytes() == subprocess.check_output(
            ["git", "show", BASE + ":" + str(path.relative_to(ROOT))], cwd=ROOT
        )


def catalog(url):
    value = complete_catalog(url)
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            value["kb01_functions"] = conn.execute(
                text(
                    "SELECT proname, pg_get_functiondef(p.oid) FROM pg_proc p "
                    "JOIN pg_namespace n ON p.pronamespace=n.oid "
                    "WHERE n.nspname='public' AND proname LIKE 'kb01_%' ORDER BY proname"
                )
            ).all()
            value["kb01_triggers"] = conn.execute(
                text(
                    "SELECT tgname, pg_get_triggerdef(t.oid) FROM pg_trigger t "
                    "WHERE NOT t.tgisinternal AND t.tgname LIKE 'kb01_%' ORDER BY tgname"
                )
            ).all()
        return value
    finally:
        engine.dispose()


def row_digest(sf, identity):
    with sf() as session:
        row = session.get(m.MetadataVersionEntity, identity)
        data = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def test_kb01_fresh_exact0020_equivalence_safe_down_up_and_audit_refusal(tmp_path):
    from kb01_historical_schema import historical_bootstrap_source

    bootstrap = historical_bootstrap_source(tmp_path / "historical0021", HEAD)
    source = tmp_path / "exact-release"
    source.mkdir()
    archive = tmp_path / "release.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["kb01_migration_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=name).render_as_string(hide_password=False) for name in names]
    engines = []
    measured = {"base_sha": BASE, "head": HEAD, "parent": PARENT}
    try:
        with admin.connect() as conn:
            for name in names:
                conn.execute(text('CREATE DATABASE "' + name + '"'))
        fresh = migrate(bootstrap, urls[0], "upgrade", HEAD)
        assert fresh.returncode == 0, fresh.stderr
        previous = migrate(source, urls[1], "upgrade", "head")
        assert previous.returncode == 0, previous.stderr
        engine, sf = build_session_factory(urls[1])
        engines.append(engine)
        tenant, definition, version = (str(uuid4()) for _ in range(3))
        # Existing 0020 canonical metadata, including an opaque exact pin,
        # must survive byte-for-byte; migration does not fabricate review.
        with sf() as s, s.begin():
            s.add(b.TenantEntity(tenant_id=tenant, name="Migration technical fixture"))
            s.flush()
            s.add(
                m.MetadataDefinitionEntity(
                    definition_id=definition,
                    tenant_id=tenant,
                    kind="SCENARIO",
                    code="PRESERVE",
                    display_name="Preserved",
                )
            )
            s.flush()
            s.add(
                m.MetadataVersionEntity(
                    version_id=version,
                    tenant_id=tenant,
                    definition_id=definition,
                    version_no=1,
                    lifecycle_status="DRAFT",
                    payload_json={"source_pin": str(uuid4())},
                    created_by="original-author",
                )
            )
        before = row_digest(sf, version)
        upgraded = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert upgraded.returncode == 0, upgraded.stderr
        assert row_digest(sf, version) == before
        assert catalog(urls[0]) == catalog(urls[1])
        for url in urls:
            down = migrate(ROOT, url, "downgrade", PARENT)
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, url, "upgrade", HEAD)
            assert up.returncode == 0, up.stderr
        assert row_digest(sf, version) == before
        context = RepositoryContext.user(tenant, "taxonomy-author", {"knowledge:taxonomy:write"})
        created = PostgresKnowledgeTaxonomyRepository(sf, context).mutate(
            "CREATE",
            None,
            CreateTaxonomy(
                kind="REGULATION_CATEGORY",
                code="TEST-ONLY",
                display_name="Technical",
                idempotency_key="migration-probe",
            ),
        )
        schema = catalog(urls[1])
        refusal = migrate(ROOT, urls[1], "downgrade", PARENT)
        assert refusal.returncode != 0 and "KB01_TAXONOMY_DOWNGRADE_REFUSED" in refusal.stderr
        assert catalog(urls[1]) == schema
        assert row_digest(sf, version) == before
        from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
            AdminOperationReceiptEntity,
        )

        with sf() as s:
            assert s.scalar(
                select(AdminOperationReceiptEntity.receipt_id).where(
                    AdminOperationReceiptEntity.receipt_id == created["receipt_id"]
                )
            )
        measured.update(
            fresh=True,
            exact0020_upgrade=True,
            schema_equivalence=True,
            old_metadata_digest_preserved=True,
            safe_downgrade=True,
            safe_reupgrade=True,
            audit_downgrade_refused=True,
            no_fabricated_history=True,
            preserved_row_digest=before,
        )
        directory = Path(os.getenv("EVIDENCE_DIR", "artifacts/kb01"))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "kb01_taxonomy_migration_measured.json").write_text(
            json.dumps(measured, indent=2) + "\n"
        )
    finally:
        for engine in engines:
            engine.dispose()
        with admin.connect() as conn:
            for name in names:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name"
                    ),
                    {"name": name},
                )
                conn.execute(text('DROP DATABASE IF EXISTS "' + name + '"'))
        admin.dispose()
