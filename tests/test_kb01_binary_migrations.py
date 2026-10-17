"""Transport migration preserves canonical rows and refuses operational/audit loss."""

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
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_kb01_taxonomy_migrations import catalog
from test_phase1h_migrations import migrate

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.knowledge_management import CreateTaxonomy
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    PostgresKnowledgeTaxonomyRepository,
)

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_SOURCE = "28bd4203ec54d81f54e140b652a85401d87deeec"
MAIN = "060cbb5a20a9f8f70fa88dbefb8b5feb404c460d"
FIRST_KB_SOURCE = "6f0f448fbe5d72494d2756bca30a3f74437e1f63"
HEAD = "0022_kb01_binary_transport"
PARENT = "0021_kb01_taxonomy_operations"


def test_kb01_binary_single_head_and_frozen_0001_0021():
    scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert scripts.get_heads() == ["0024_kb01_import_manifest_records"]
    assert (
        scripts.get_revision("0024_kb01_import_manifest_records").down_revision
        == "0023_kb01_evidence_source_reference"
    )
    assert scripts.get_revision("0023_kb01_evidence_source_reference").down_revision == HEAD
    assert scripts.get_revision(HEAD).down_revision == PARENT
    protected = [
        p
        for p in (ROOT / "alembic/versions").glob("*.py")
        if p.name[:4].isdigit() and int(p.name[:4]) <= 21
    ]
    assert len(protected) == 21
    for path in protected:
        source = MAIN if int(path.name[:4]) <= 20 else FIRST_KB_SOURCE
        assert path.read_bytes() == subprocess.check_output(
            ["git", "show", source + ":" + str(path.relative_to(ROOT))],
            cwd=ROOT,
        )


def preserved_metadata_digest(url):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            rows = {
                name: [
                    dict(row._mapping)
                    for row in conn.execute(text("SELECT * FROM " + name + " ORDER BY 1"))
                ]
                for name in (
                    "metadata_definitions",
                    "metadata_versions",
                    "admin_change_sets",
                    "admin_operation_receipts",
                )
            }
        return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    finally:
        engine.dispose()


def test_binary_fresh_exact0021_equivalence_preservation_and_refusal(tmp_path):
    from kb01_historical_schema import historical_bootstrap_source

    bootstrap = historical_bootstrap_source(tmp_path / "historical0022", HEAD)
    previous = tmp_path / "previous"
    previous.mkdir()
    archive = tmp_path / "previous.tar"
    with archive.open("wb") as output:
        subprocess.run(["git", "archive", PREVIOUS_SOURCE], cwd=ROOT, stdout=output, check=True)
    with tarfile.open(archive) as source:
        source.extractall(previous, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["kb01_binary_migration_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=name).render_as_string(hide_password=False) for name in names]
    engine = None
    try:
        with admin.connect() as conn:
            for name in names:
                conn.execute(text('CREATE DATABASE "' + name + '"'))
        fresh = migrate(bootstrap, urls[0], "upgrade", HEAD)
        assert fresh.returncode == 0, fresh.stderr
        exact = migrate(previous, urls[1], "upgrade", "head")
        assert exact.returncode == 0, exact.stderr
        assert catalog(urls[1]) != catalog(urls[0])
        engine, sessions = build_session_factory(urls[1])
        tenant = uuid4()
        with sessions() as s, s.begin():
            s.add(b.TenantEntity(tenant_id=str(tenant), name="Migration synthetic metadata"))
        context = RepositoryContext.user(
            tenant, "metadata-original-author", {"knowledge:taxonomy:write"}
        )
        PostgresKnowledgeTaxonomyRepository(sessions, context).mutate(
            "CREATE",
            None,
            CreateTaxonomy(
                kind="REGULATION_CATEGORY",
                code="PREEXISTING",
                display_name="Existing",
                idempotency_key="old-taxonomy",
            ),
        )
        before = preserved_metadata_digest(urls[1])
        upgrade = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert upgrade.returncode == 0, upgrade.stderr
        assert before == preserved_metadata_digest(urls[1])
        assert catalog(urls[0]) == catalog(urls[1])
        for url in urls:
            down = migrate(ROOT, url, "downgrade", PARENT)
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, url, "upgrade", HEAD)
            assert up.returncode == 0, up.stderr
        assert before == preserved_metadata_digest(urls[1])
        # Genuine canonical AdminChangeSet receipt protects even a failed/cancelled intent.
        from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
            AdminOperationReceiptEntity,
        )
        from crossborder_compliance.infrastructure.persistence.metadata_models import (
            AdminChangeSetEntity,
        )

        change, receipt = str(uuid4()), str(uuid4())
        with sessions() as s, s.begin():
            s.add(
                AdminChangeSetEntity(
                    change_set_id=change,
                    tenant_id=str(tenant),
                    actor_id="upload-operator",
                    summary="Transport safety fixture",
                    lifecycle_status="DRAFT",
                )
            )
            s.flush()
            s.add(
                AdminOperationReceiptEntity(
                    receipt_id=receipt,
                    tenant_id=str(tenant),
                    change_set_id=change,
                    resource_kind="KNOWLEDGE_UPLOAD",
                    resource_id=str(uuid4()),
                    operation="UPLOAD_CREATE",
                    reason="Preserve operational authorization evidence",
                    request_hash="a" * 64,
                    result_json={"status": "CREATING"},
                )
            )
        schema = catalog(urls[1])
        refusal = migrate(ROOT, urls[1], "downgrade", PARENT)
        assert refusal.returncode != 0
        assert "KB01_BINARY_TRANSPORT_DOWNGRADE_REFUSED" in refusal.stderr
        assert catalog(urls[1]) == schema
        with sessions() as s:
            assert s.get(AdminOperationReceiptEntity, receipt).operation == "UPLOAD_CREATE"
        out = Path(os.getenv("EVIDENCE_DIR", "artifacts/kb01"))
        out.mkdir(parents=True, exist_ok=True)
        (out / "kb01_binary_migration_measured.json").write_text(
            json.dumps(
                {
                    "previous_source": PREVIOUS_SOURCE,
                    "head": HEAD,
                    "parent": PARENT,
                    "fresh_upgrade": True,
                    "exact0021_upgrade": True,
                    "schema_equivalence": True,
                    "old_metadata_and_admin_receipts_preserved": True,
                    "safe_downgrade": True,
                    "safe_reupgrade": True,
                    "unsafe_downgrade_refused": True,
                    "initial_row_digest": before,
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as conn:
            for name in names:
                conn.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": name},
                )
                conn.execute(text('DROP DATABASE IF EXISTS "' + name + '"'))
        admin.dispose()
