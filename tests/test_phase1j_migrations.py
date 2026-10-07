"""Independent fresh/exact Round2 dual path, catalog equivalence and transactional downgrade."""

import json
import os
import subprocess
import tarfile
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_phase1h_migrations import migrate, schema
from test_phase1j_contracts import risk_policy

from crossborder_compliance.application.metadata_services import MetadataLifecycleService
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import decision_models as j
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)

pytestmark = pytest.mark.runtime_smoke
BASE = "594be84cfc471af4c12f28600b22cffb66f830f7"
ROOT = Path(__file__).resolve().parents[1]


def catalog(url):
    result = schema(url)
    with create_engine(url).connect() as conn:
        result["functions"] = conn.execute(
            text(
                "SELECT proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='public' AND proname LIKE 'phase1%' ORDER BY proname"
            )
        ).all()
        result["index_definitions"] = conn.execute(
            text(
                "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname"
            )
        ).all()
    return result


def seed_scope(url):
    engine, sf = build_session_factory(url)
    tenant, project, version, snapshot, jurisdiction = [str(uuid4()) for _ in range(5)]
    with sf() as s, s.begin():
        s.add(b.TenantEntity(tenant_id=tenant, name="Migration acceptance"))
        s.flush()
        s.add(b.ProjectEntity(project_id=project, tenant_id=tenant, name="Decision migration"))
        s.flush()
        s.add(
            b.ProjectVersionEntity(
                project_version_id=version, project_id=project, tenant_id=tenant, version_no=1
            )
        )
        s.flush()
        s.add(
            b.AnalysisSnapshotEntity(
                analysis_snapshot_id=snapshot,
                tenant_id=tenant,
                project_version_id=version,
                snapshot_version="1.0",
                analysis_as_of_date=date(2026, 1, 1),
                provenance_json={},
            )
        )
        s.flush()
        s.add(
            b.JurisdictionEntity(
                jurisdiction_id=jurisdiction,
                tenant_id=tenant,
                code=jurisdiction,
                name="Canonical jurisdiction",
            )
        )
    return engine, sf, (tenant, project, version, snapshot, jurisdiction)


def test_phase1j_fresh_exact_0009_schema_equivalence_and_downgrade(tmp_path):
    source = tmp_path / "round2"
    source.mkdir()
    archive = tmp_path / "round2.tar"
    with archive.open("wb") as out:
        subprocess.run(["git", "archive", "--format=tar", BASE], cwd=ROOT, stdout=out, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter="data")
    baseurl = make_url(get_settings().database_url)
    admin = create_engine(baseurl.set(database="postgres"), isolation_level="AUTOCOMMIT")
    names = ["phase1j_migration_" + uuid4().hex for _ in range(3)]
    urls = [baseurl.set(database=n).render_as_string(hide_password=False) for n in names]
    evidence = {"verified_base": BASE, "baseline_revision": "0009_phase1i", "head": "0010_phase1j"}
    try:
        with admin.connect() as conn:
            for n in names:
                conn.execute(text('CREATE DATABASE "' + n + '"'))
        fresh = migrate(ROOT, urls[0], "upgrade", "head")
        assert fresh.returncode == 0, fresh.stderr
        frozen = migrate(source, urls[1], "upgrade", "head")
        assert frozen.returncode == 0, frozen.stderr
        with create_engine(urls[1]).connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0009_phase1i"
            assert conn.scalar(text("SELECT to_regclass('compliance_obligation_results')")) is None
        upgraded = migrate(ROOT, urls[1], "upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence.update(fresh_upgrade=True, exact_0009_upgrade=True, full_catalog_equivalence=True)
        for url in urls[:2]:
            down = migrate(ROOT, url, "downgrade", "0009_phase1i")
            assert down.returncode == 0, down.stderr
            up = migrate(ROOT, url, "upgrade", "head")
            assert up.returncode == 0, up.stderr
        assert catalog(urls[0]) == catalog(urls[1])
        evidence["empty_roundtrip"] = True
        third = migrate(ROOT, urls[2], "upgrade", "head")
        assert third.returncode == 0, third.stderr
        for state, url in zip(("POLICY", "PIN", "RESULT"), urls):
            engine, sf, ids = seed_scope(url)
            tenant, project, version, snapshot, jurisdiction = ids
            if state == "POLICY":

                def svc(actor):
                    ctx = RepositoryContext.user(
                        UUID(tenant),
                        actor,
                        {"metadata:admin", "metadata:review", "metadata:publish"},
                    )
                    return MetadataLifecycleService(PostgresAdminMetadataRepository(sf, ctx), ctx)

                from uuid import UUID

                draft = svc("author").create_draft(
                    kind="RISK_POLICY",
                    code="MIGRATION_RISK",
                    display_name="Governed risk",
                    payload=risk_policy(jurisdiction_ids=[jurisdiction]).model_dump(mode="json"),
                )
                ident = UUID(draft["version_id"])
                submitted = svc("author").submit_review(
                    ident, expected_record_version=draft["record_version"]
                )
                approved = svc("reviewer").approve(
                    ident, expected_record_version=submitted["record_version"]
                )
                svc("author").publish(ident, expected_record_version=approved["record_version"])
            elif state == "PIN":
                with sf() as s, s.begin():
                    s.add(
                        m.AnalysisSnapshotRegistryPinEntity(
                            pin_id=str(uuid4()),
                            tenant_id=tenant,
                            analysis_snapshot_id=snapshot,
                            pin_type="PHASE1J_INITIALIZATION",
                            logical_key="acceptance",
                            object_id=snapshot,
                            version_id=snapshot,
                            version_no=1,
                        )
                    )
            else:
                result_id = str(uuid4())
                fingerprint = "a" * 64
                pins_digest = "b" * 64
                payload = {
                    "tenant_id": tenant,
                    "project_id": project,
                    "analysis_snapshot_id": snapshot,
                    "result_id": result_id,
                    "input_digest": fingerprint,
                    "pins_digest": pins_digest,
                }
                with sf() as s, s.begin():
                    s.add(
                        j.MODELS["OBLIGATION"](
                            result_id=result_id,
                            tenant_id=tenant,
                            project_id=project,
                            analysis_snapshot_id=snapshot,
                            project_version_id=version,
                            context_version=1,
                            subject_type="SCENARIO",
                            subject_id=str(uuid4()),
                            analysis_as_of_date=date(2026, 1, 1),
                            jurisdiction_ids=[jurisdiction],
                            policy_version_id=None,
                            upstream_refs=[],
                            pins_json=[],
                            provenance_json={},
                            input_fingerprint=fingerprint,
                            pins_digest=pins_digest,
                            contract_version="2.0",
                            engine_version="FORMAL_DECISION_V2",
                            owner_actor_id="acceptance",
                            summary_status="INSUFFICIENT_EVIDENCE",
                            request_json={},
                            result_json=payload,
                        )
                    )
            before = catalog(url)
            with engine.connect() as conn:
                head_before_refusal = conn.scalar(text("SELECT version_num FROM alembic_version"))
            down = migrate(ROOT, url, "downgrade", "0009_phase1i")
            assert down.returncode != 0 and "archive/export" in down.stderr
            with engine.connect() as conn:
                assert (
                    conn.scalar(text("SELECT version_num FROM alembic_version")) == head_before_refusal
                )
            assert catalog(url) == before
            evidence[state.lower() + "_transactional_refusal"] = True
            engine.dispose()
        output = Path(os.getenv("EVIDENCE_DIR", str(ROOT / "artifacts/phase1j-migrations")))
        output.mkdir(parents=True, exist_ok=True)
        (output / "phase1j_migration_dual_path.json").write_text(json.dumps(evidence, indent=2))
    finally:
        with admin.connect() as conn:
            for n in names:
                conn.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": n},
                )
                conn.execute(text('DROP DATABASE IF EXISTS "' + n + '"'))
        admin.dispose()
