"""Real PostgreSQL exact0017/fresh identity migration, no result rewrites."""

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from test_phase1h_migrations import migrate
from test_phase1j_migrations import catalog, seed_scope

from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.classification import ClassificationResult
from crossborder_compliance.infrastructure.persistence import models as b

pytestmark = pytest.mark.runtime_smoke
ROOT = Path(__file__).resolve().parents[1]
BASE = "0f5a40c5ca3a8771624fb38e9380856d79e67342"
WIP = "b7b7602a58581b6316510e184300684cfa6d8036"
HEAD = "0018_phase1h_multijurisdiction_classification_identity"
OLD = "0017_m2e_external_agent_api"


def index(engine):
    with engine.connect() as c:
        return c.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname='uq_formal_classification_snapshot'"
            )
        )


def payload(row):
    value = dict(row)
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def test_fresh_exact0017_equivalence_preserving_rows_downgrade_and_refusal(tmp_path):
    source = tmp_path / "baseline"
    source.mkdir()
    archive = tmp_path / "baseline.tar"
    with archive.open("wb") as output:
        subprocess.run(
            ["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=output, check=True
        )
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    base = make_url(get_settings().database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["r11_migration_" + uuid4().hex for _ in range(2)]
    urls = [base.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = {"migration": HEAD, "parent": OLD}
    engine = None
    try:
        with admin.connect() as c:
            for n in names:
                c.execute(text('CREATE DATABASE "' + n + '"'))
        fresh = migrate(ROOT, urls[0], "upgrade", "head")
        assert fresh.returncode == 0, fresh.stderr
        old = migrate(source, urls[1], "upgrade", "head")
        assert old.returncode == 0, old.stderr
        with create_engine(urls[1]).connect() as c:
            assert (
                c.scalar(text("SELECT version_num FROM alembic_version"))
                == "0016_phase1kb_multi_provider_llm_governance"
            )
        exact = migrate(ROOT, urls[1], "upgrade", OLD)
        assert exact.returncode == 0, exact.stderr
        engine, sf, ids = seed_scope(urls[1])
        tenant, project, version, snapshot, jurisdiction = ids
        scheme, scheme_version, subject, category, evidence_id, hit = [
            str(uuid4()) for _ in range(6)
        ]
        first = ClassificationResult(
            tenant_id=tenant,
            project_id=project,
            data_item_id=subject,
            jurisdiction_id=jurisdiction,
            analysis_snapshot_id=snapshot,
            scheme_id=scheme,
            scheme_version_id=scheme_version,
            category_ids=[category],
            level_id=None,
            rule_hit_ids=[hit],
            evidence_ids=[evidence_id],
            source_fact_refs=[str(uuid4())],
            reason_codes=["COUNT_RULE"],
            confidence=1,
            review_required=False,
            status="CLASSIFIED",
            context_version=1,
        )
        with sf() as s, s.begin():
            s.add(
                b.ClassificationSchemeEntity(
                    scheme_id=scheme, tenant_id=tenant, code=scheme, name="Migration scheme"
                )
            )
            s.flush()
            s.add(
                b.ClassificationResultEntity(
                    classification_result_id=str(first.classification_result_id),
                    tenant_id=tenant,
                    project_id=project,
                    analysis_snapshot_id=snapshot,
                    subject_type="DATA_ITEM",
                    subject_id=subject,
                    scheme_id=scheme,
                    scheme_version_id=scheme_version,
                    jurisdiction_id=jurisdiction,
                    confidence=1,
                    formal_provenance_json=first.model_dump(mode="json"),
                )
            )

        def rows():
            with engine.connect() as c:
                return [
                    dict(r)
                    for r in c.execute(
                        text(
                            "SELECT * FROM classification_results ORDER BY classification_result_id"
                        )
                    ).mappings()
                ]

        before = rows()
        digest = payload(before[0])
        assert "jurisdiction_id" not in index(engine).split("USING btree")[1]
        up = migrate(ROOT, urls[1], "upgrade", "head")
        assert up.returncode == 0, up.stderr
        assert rows() == before and payload(rows()[0]) == digest
        assert ClassificationResult.model_validate(rows()[0]["formal_provenance_json"]) == first
        definition = index(engine)
        assert (
            "(tenant_id, project_id, analysis_snapshot_id, subject_id, "
            "jurisdiction_id, scheme_version_id)" in definition
        )
        assert "WHERE (formal_provenance_json IS NOT NULL)" in definition
        assert catalog(urls[0]) == catalog(urls[1])
        safe = migrate(ROOT, urls[1], "downgrade", OLD)
        assert safe.returncode == 0, safe.stderr
        assert rows() == before and "jurisdiction_id" not in index(engine).split("USING btree")[1]
        again = migrate(ROOT, urls[1], "upgrade", HEAD)
        assert again.returncode == 0, again.stderr
        assert rows() == before and catalog(urls[0]) == catalog(urls[1])
        destination = str(uuid4())
        with sf() as s, s.begin():
            s.add(
                b.JurisdictionEntity(
                    jurisdiction_id=destination,
                    tenant_id=tenant,
                    code=destination,
                    name="Destination",
                )
            )
            s.flush()
            second = dict(
                before[0], classification_result_id=str(uuid4()), jurisdiction_id=destination
            )
            second["formal_provenance_json"] = dict(
                first.model_dump(mode="json"),
                jurisdiction_id=destination,
                classification_result_id=second["classification_result_id"],
            )
            s.add(b.ClassificationResultEntity(**second))
        both = rows()
        assert len(both) == 2
        with pytest.raises(IntegrityError, match="uq_formal_classification_snapshot"):
            with sf() as s, s.begin():
                s.add(
                    b.ClassificationResultEntity(
                        **dict(before[0], classification_result_id=str(uuid4()))
                    )
                )
        schema_before = catalog(urls[1])
        refusal = migrate(ROOT, urls[1], "downgrade", OLD)
        assert (
            refusal.returncode != 0
            and "R1 classification identity downgrade refused" in refusal.stderr
        )
        assert rows() == both and catalog(urls[1]) == schema_before and index(engine) == definition
        with engine.connect() as c:
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        evidence.update(
            fresh=True,
            exact0016_to0017_to0018=True,
            exact0017_upgrade=True,
            schema_equivalence=True,
            legacy_row_and_digest_unchanged=True,
            safe_downgrade=True,
            reupgrade=True,
            two_jurisdictions_persist=True,
            same_jurisdiction_duplicate_rejected=True,
            unsafe_downgrade_transactionally_refused=True,
            predicate_unchanged=True,
        )
        output = Path(os.getenv("EVIDENCE_DIR", str(ROOT / "artifacts/m2e/r11")))
        output.mkdir(parents=True, exist_ok=True)
        (output / "migration_measured.json").write_text(json.dumps(evidence, indent=2) + "\n")
    finally:
        if engine:
            engine.dispose()
        with admin.connect() as c:
            for n in names:
                c.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": n},
                )
                c.execute(text('DROP DATABASE IF EXISTS "' + n + '"'))
        admin.dispose()


def test_frozen_migrations_and_wip0017_byte_identity():
    for path in (ROOT / "alembic/versions").glob("*.py"):
        if path.name[:4].isdigit() and int(path.name[:4]) <= 17:
            ref = WIP if path.name.startswith("0017") else BASE
            assert path.read_bytes() == subprocess.check_output(
                ["git", "show", ref + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            )
