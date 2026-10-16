"""Exact0023 upgrade preserves prior identities; catalogue evidence cannot be downgraded away."""

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_kb01_taxonomy_migrations import catalog
from test_kb01_taxonomy_postgres import deletion_policy
from test_phase1h_migrations import migrate

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.knowledge_upload import StartKnowledgeUpload
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.knowledge_uploads import (
    PostgresKnowledgeUploads,
)

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = "2e4acdc3f355ed28a1d3e4792f9cbbb9cbbff098"
HEAD = "0024_kb01_import_manifest_records"
PARENT = "0023_kb01_evidence_source_reference"


def test_manifest_single_head_and_frozen_0001_0023():
    scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert scripts.get_heads() == [HEAD]
    assert scripts.get_revision(HEAD).down_revision == PARENT
    protected = [
        p
        for p in (ROOT / "alembic/versions").glob("*.py")
        if p.name[:4].isdigit() and int(p.name[:4]) <= 23
    ]
    assert len(protected) == 23
    for path in protected:
        assert path.read_bytes() == subprocess.check_output(
            [
                "git",
                "show",
                PREVIOUS + ":" + str(path.relative_to(ROOT)),
            ],
            cwd=ROOT,
        )


def prior_rows(sf):
    with sf() as s:
        rows = {
            table: [
                dict(row._mapping)
                for row in s.execute(text("SELECT * FROM " + table + " ORDER BY 1"))
            ]
            for table in ("tenants", "metadata_definitions", "metadata_versions")
        }
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def test_manifest_fresh_exact0023_schema_preservation_safe_downgrade_and_new_format_refusal(
    tmp_path,
):
    previous = tmp_path / "exact0023"
    previous.mkdir()
    archive = tmp_path / "exact0023.tar"
    with archive.open("wb") as output:
        subprocess.run(["git", "archive", PREVIOUS], cwd=ROOT, stdout=output, check=True)
    with tarfile.open(archive) as source:
        source.extractall(previous, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["kb01_manifest_matrix_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=name).render_as_string(hide_password=False) for name in names]
    engine = None
    measured = {"head": HEAD, "parent": PARENT, "exact_previous_source": PREVIOUS}
    try:
        with admin.connect() as connection:
            for name in names:
                connection.execute(text('CREATE DATABASE "' + name + '"'))
        fresh = migrate(ROOT, urls[0], "upgrade", HEAD)
        assert fresh.returncode == 0, fresh.stderr
        old = migrate(previous, urls[1], "upgrade", PARENT)
        assert old.returncode == 0, old.stderr
        engine, sf = build_session_factory(urls[1])
        tenant = str(uuid4())
        definition, version = str(uuid4()), str(uuid4())
        with sf() as s, s.begin():
            s.add(b.TenantEntity(tenant_id=tenant, name="Synthetic migration preservation"))
            s.flush()
            s.add(
                m.MetadataDefinitionEntity(
                    definition_id=definition,
                    tenant_id=tenant,
                    kind="SCENARIO",
                    code="PRESERVED",
                    display_name="Preserved metadata",
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
                    payload_json={"exact_historical_pin": str(uuid4())},
                    created_by="original-author",
                )
            )
        digest = prior_rows(sf)
        up = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert up.returncode == 0, up.stderr
        assert prior_rows(sf) == digest
        assert catalog(urls[0]) == catalog(urls[1])
        measured.update(
            fresh=True,
            exact_previous_upgrade=True,
            schema_equivalence=True,
            prior_rows_unchanged=True,
        )
        down = migrate(ROOT, urls[1], "downgrade", PARENT)
        assert down.returncode == 0, down.stderr
        assert prior_rows(sf) == digest
        reup = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert reup.returncode == 0, reup.stderr
        assert prior_rows(sf) == digest
        measured.update(safe_empty_downgrade=True, safe_reupgrade=True)
        deletion_policy((sf, UUID(tenant), None, None))
        uploads = PostgresKnowledgeUploads(
            sf, RepositoryContext.user(UUID(tenant), "uploader", {"knowledge:upload:create"})
        )
        uploads.start(
            StartKnowledgeUpload(
                relative_path="catalogue.csv",
                declared_format="CSV",
                declared_bytes=15,
                content_sha256="a" * 64,
                idempotency_key=str(uuid4()),
            )
        )
        before_refusal = prior_rows(sf)
        refused = migrate(ROOT, urls[1], "downgrade", PARENT)
        assert (
            refused.returncode != 0
            and "KB01_MANIFEST_GOVERNANCE_DOWNGRADE_REFUSED" in refused.stderr
        )
        assert prior_rows(sf) == before_refusal
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM knowledge_upload_sessions WHERE declared_format='CSV'"
                    )
                )
                == 1
            )
        measured["catalogue_upload_downgrade_refused"] = True
        out = Path(os.environ.get("EVIDENCE_DIR", str(tmp_path)))
        out.mkdir(parents=True, exist_ok=True)
        (out / "kb01_manifest_migration_measured.json").write_text(
            json.dumps(measured, indent=2) + "\n"
        )
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as connection:
            for name in names:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname=:name AND pid<>pg_backend_pid()"
                    ),
                    {"name": name},
                )
                connection.execute(text('DROP DATABASE IF EXISTS "' + name + '"'))
        admin.dispose()
