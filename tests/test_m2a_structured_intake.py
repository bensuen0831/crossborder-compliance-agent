"""Structured and genuine document input converge on the canonical PG facts."""

# ruff: noqa: F401,F811 -- shared real PostgreSQL fixture graph
import io
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from test_m2a_intake import create, setup
from test_phase1e_postgres import CleanScan, MemoryStorage, Queue
from test_phase1i_postgres import config_service, publish_config
from test_phase1j_postgres import fixture, foundation_i, foundation_j

from crossborder_compliance.application.document_services import (
    DocumentIngestionService,
    DocumentParseService,
)
from crossborder_compliance.infrastructure.document_parsers import default_native_parsers
from crossborder_compliance.infrastructure.intake_composition import intake_service, project_context
from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import decision_models as j
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.context_repositories import (
    PostgresContextResolutionRepository,
)
from crossborder_compliance.infrastructure.persistence.document_repositories import (
    PostgresDocumentIntelligenceRepository,
)

pytestmark = pytest.mark.runtime_smoke


def binding(f, code="COUNT", field="data_volume", value_type="integer"):
    with f["sf"]() as s:
        definition = s.scalar(
            select(m.MetadataDefinitionEntity).where(
                m.MetadataDefinitionEntity.tenant_id == f["tenant"],
                m.MetadataDefinitionEntity.kind == "BUSINESS_FACT_TYPE",
                m.MetadataDefinitionEntity.code == code,
            )
        )
        ident = definition.definition_id if definition else None
    payload = {
        "effective_from": "2025-01-01",
        "structured_intake_binding": {"field_path": field, "value_type": value_type},
    }
    if ident:
        return publish_config(f, "BUSINESS_FACT_TYPE", payload, definition_id=ident)
    svc = config_service(f)
    draft = svc.create_draft(
        kind="BUSINESS_FACT_TYPE", code=code, display_name="Governed test fact", payload=payload
    )
    vid = UUID(draft["version_id"])
    review = svc.submit_review(vid, expected_record_version=draft["record_version"])
    approved = config_service(f, "independent-reviewer").approve(
        vid, expected_record_version=review["record_version"]
    )
    return svc.publish(vid, expected_record_version=approved["record_version"])


def confirm(c, record):
    response = c.post(
        f"/api/v1/projects/{record['project_id']}/intake/confirm",
        json={"expected_version": record["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def start(c, record):
    response = c.post(
        f"/api/v1/projects/{record['project_id']}/snapshots/{record['analysis_snapshot_id']}/workflow",
        json={},
    )
    assert response.status_code == 200, response.text
    return response.json()


def facts(f, project):
    with f["sf"]() as s:
        return s.scalars(
            select(e.BusinessFactEntity).where(
                e.BusinessFactEntity.tenant_id == f["tenant"],
                e.BusinessFactEntity.project_id == project,
            )
        ).all()


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_manual_only_exact_provenance_and_existing_formal_chain(foundation_j):
    f = foundation_j
    mapping = binding(f)
    _, c, ctx, values = setup(f)
    record = create(c, {**values, "data_volume": "3"}).json()
    confirmed = confirm(c, record)
    rows = facts(f, record["project_id"])
    assert len(rows) == 1
    fact = rows[0]
    assert fact.fact_type == "COUNT" and fact.normalized_value_json == 3
    assert fact.original_values_json == ["3"] and not fact.source_document_ids_json
    p = fact.structured_provenance_json[0]
    assert p["source_type"] == "USER_INPUT" and p["source_ref"] == record["project_version_id"]
    assert (
        p["source_version"] == "1"
        and p["source_locator"] == "data_volume"
        and p["actor_ref"] == "author"
    )
    with f["sf"]() as s:
        snapshot = s.get(b.AnalysisSnapshotEntity, confirmed["analysis_snapshot_id"])
        assert snapshot.project_version_id == record["project_version_id"]
        assert p["request_id"] == snapshot.analysis_snapshot_id
        assert datetime.fromisoformat(p["generated_at"]) == datetime.fromisoformat(
            snapshot.provenance_json["confirmed_at"]
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.DocumentEntity)
                .where(b.DocumentEntity.project_id == record["project_id"])
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.DocumentParseRunEntity)
                .join(b.DocumentVersionEntity)
                .join(
                    b.DocumentEntity,
                    b.DocumentEntity.document_id == b.DocumentVersionEntity.document_id,
                )
                .where(b.DocumentEntity.project_id == record["project_id"])
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.SourceTraceRefEntity)
                .join(b.DocumentVersionEntity)
                .join(
                    b.DocumentEntity,
                    b.DocumentEntity.document_id == b.DocumentVersionEntity.document_id,
                )
                .where(b.DocumentEntity.project_id == record["project_id"])
            )
            == 0
        )
        pin = s.scalar(
            select(m.AnalysisSnapshotRegistryPinEntity).where(
                m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id
                == snapshot.analysis_snapshot_id,
                m.AnalysisSnapshotRegistryPinEntity.pin_type == "STRUCTURED_INTAKE_FACT_BINDING",
            )
        )
        assert pin.object_id == mapping["definition_id"]
    view = start(c, confirmed)
    assert view["status"] == "COMPLETED", view
    assert view["result_refs"]["applicability"]
    assert start(c, confirmed) == view and confirm(c, record) == confirmed
    assert c.get(f"/api/v1/workflows/{view['workflow_run_id']}").json() == view
    assert [x.fact_id for x in facts(f, record["project_id"])] == [fact.fact_id]
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(j.MODELS["FINAL_PATH"])
                .where(
                    j.MODELS["FINAL_PATH"].analysis_snapshot_id == confirmed["analysis_snapshot_id"]
                )
            )
            == 1
        )


def test_unmapped_missing_facts_warns_without_formal_decisions(foundation_j):
    f = foundation_j
    _, c, _, values = setup(f)
    record = confirm(c, create(c, {**values, "data_volume": "3"}).json())
    view = start(c, record)
    assert view["status"] == "WARNING" and view["reason_codes"] == ["FORMAL_BUSINESS_FACT_REQUIRED"]
    assert not facts(f, record["project_id"]) and not view["result_refs"].get("applicability")
    with f["sf"]() as s:
        for model in j.MODELS.values():
            assert (
                s.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.analysis_snapshot_id == record["analysis_snapshot_id"])
                )
                == 0
            )


def test_missing_required_type_warns_even_when_other_fact_exists(foundation_j):
    f = foundation_j
    # Govern a different declared input; it cannot satisfy the configured COUNT.
    publish_config(
        f,
        "BUSINESS_FACT_TYPE",
        {"structured_intake_binding": {"field_path": "business_purpose", "value_type": "string"}},
    )
    _, c, _, values = setup(f)
    record = confirm(c, create(c, values).json())
    view = start(c, record)
    assert len(facts(f, record["project_id"])) == 1
    assert view["status"] == "WARNING" and view["reason_codes"] == ["FORMAL_BUSINESS_FACT_REQUIRED"]


def real_document(f, context, project, value):
    from docx import Document

    doc = Document()
    doc.add_paragraph("Purpose: " + value)
    buffer = io.BytesIO()
    doc.save(buffer)
    repo = PostgresDocumentIntelligenceRepository(f["sf"], context)
    storage = MemoryStorage()
    queue = Queue()
    result = DocumentIngestionService(repo, storage, CleanScan()).ingest(
        tenant_id=UUID(f["tenant"]),
        project_id=UUID(project),
        filename="actual-purpose.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=buffer.getvalue(),
    )
    parser = DocumentParseService(repo, storage, default_native_parsers(), queue)
    task = parser.request_parse(
        document_version_id=UUID(result["document_version_id"]), idempotency_key=str(uuid4())
    )
    assert parser.process_task(UUID(task["task_id"]))["status"] == "COMPLETED"


@pytest.mark.parametrize(
    "document_value,conflict", [("Manual purpose", False), ("Other purpose", True)]
)
def test_real_document_and_manual_merge_or_existing_durable_conflict(
    foundation_j, document_value, conflict
):
    f = foundation_j
    # The existing native extractor emits governed GENERIC_FIELD candidates.
    binding(f, code="GENERIC_FIELD", field="business_purpose", value_type="string")
    _, c, ctx, values = setup(f)
    values = {**values, "business_purpose": "Manual purpose"}
    record = create(c, values).json()
    real_document(f, ctx, record["project_id"], document_value)
    confirmed = confirm(c, record)
    rows = facts(f, record["project_id"])
    assert len(rows) == (2 if conflict else 1)
    assert sum(bool(x.structured_provenance_json) for x in rows) == 1
    assert any(x.source_document_ids_json for x in rows)
    if conflict:
        assert all(x.review_required and x.validation_status == "REVIEW_REQUIRED" for x in rows)
        view = start(c, confirmed)
        assert view["status"] == "REVIEW_REQUIRED" and view["review_id"]
        with f["sf"]() as s:
            assert s.scalar(
                select(e.ContextConflictEntity).where(
                    e.ContextConflictEntity.project_id == record["project_id"],
                    e.ContextConflictEntity.conflict_type == "BUSINESS_FACT_CONFLICT",
                )
            )
            assert s.get(b.ReviewTaskEntity, view["review_id"]).status == "PENDING"
        assert start(c, confirmed) == view
    else:
        assert rows[0].validation_status == "VALIDATED"


@pytest.mark.parametrize("corruption", ["actor", "version", "tenant", "value"])
def test_provenance_scope_or_history_tamper_rejected(foundation_j, corruption):
    f = foundation_j
    binding(f)
    _, c, _, values = setup(f)
    record = confirm(c, create(c, {**values, "data_volume": "3"}).json())
    row = facts(f, record["project_id"])[0]
    with pytest.raises(DBAPIError):
        with f["sf"]() as s, s.begin():
            target = s.get(e.BusinessFactEntity, row.fact_id)
            if corruption == "value":
                target.normalized_value_json = 99
            elif corruption == "tenant":
                target.tenant_id = str(uuid4())
            else:
                p = {
                    **target.structured_provenance_json[0],
                    ("actor_ref" if corruption == "actor" else "source_version"): "wrong",
                }
                target.structured_provenance_json = [p]
            s.flush()


@pytest.mark.parametrize("foundation_i", [{"no_data": True}], indirect=True)
def test_restart_reconstructs_exact_host_and_revalidates_current_tenant(foundation_j, tmp_path):
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    from crossborder_compliance.domain.security import RepositoryContext
    from crossborder_compliance.interfaces.api.dependencies import get_repository_context

    f = foundation_j
    binding(f)
    app, c, ctx, values = setup(f)
    record = confirm(c, create(c, {**values, "data_volume": "3"}).json())
    root = Path(__file__).resolve().parents[1]
    manifest = tmp_path / "restart.json"
    manifest.write_text(
        json.dumps(
            dict(
                tenant=f["tenant"],
                scopes=sorted(ctx.permission.scopes),
                project=record["project_id"],
                snapshot=record["analysis_snapshot_id"],
            )
        )
    )
    expected_ids = [x.fact_id for x in facts(f, record["project_id"])]

    def run():
        proc = subprocess.run(
            [sys.executable, str(root / "tests/m2a_worker.py"), str(manifest)],
            cwd=root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    first = run()
    assert first["status"] == "COMPLETED"
    assert run() == first and first["workflow_run_id"] == record["workflow_run_id"]
    assert [x.fact_id for x in facts(f, record["project_id"])] == expected_ids
    for unauthorized in (
        RepositoryContext.user(uuid4(), "author", set(ctx.permission.scopes)),
        RepositoryContext.user(ctx.tenant_id, "other", set(ctx.permission.scopes)),
        RepositoryContext.user(ctx.tenant_id, "author", set()),
    ):
        app.dependency_overrides[get_repository_context] = lambda unauthorized=unauthorized: (
            unauthorized
        )
        assert c.get(f"/api/v1/workflows/{first['workflow_run_id']}").status_code == 404
        assert (
            c.post(
                f"/api/v1/projects/{record['project_id']}/snapshots/{record['analysis_snapshot_id']}/workflow",
                json={},
            ).status_code
            == 404
        )


@pytest.mark.parametrize(
    "field,value_type",
    [("unknown_field", "string"), ("project_id", "string"), ("business_purpose", "unknown_type")],
)
def test_ungoverned_binding_rejected_atomically(foundation_j, field, value_type):
    f = foundation_j
    binding(f, field=field, value_type=value_type)
    _, c, _, values = setup(f)
    record = create(c, values).json()
    response = c.post(
        f"/api/v1/projects/{record['project_id']}/intake/confirm", json={"expected_version": 1}
    )
    assert response.status_code == 422, response.text
    assert c.get(f"/api/v1/projects/{record['project_id']}/intake").json()["status"] == "DRAFT"
    assert not facts(f, record["project_id"])
    with f["sf"]() as s:
        assert not s.scalar(
            select(b.AnalysisSnapshotEntity).where(
                b.AnalysisSnapshotEntity.project_version_id == record["project_version_id"]
            )
        )


def test_concurrent_confirmation_same_snapshot_or_explicit_retry(foundation_j):
    from concurrent.futures import ThreadPoolExecutor

    f = foundation_j
    binding(f)
    _, c, _, values = setup(f)
    record = create(c, {**values, "data_volume": "3"}).json()
    path = f"/api/v1/projects/{record['project_id']}/intake/confirm"
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: c.post(path, json={"expected_version": 1}), range(2)))
    assert all(x.status_code in {200, 409} for x in responses), [x.text for x in responses]
    assert any(x.status_code == 200 for x in responses)
    confirmed = c.post(path, json={"expected_version": 1}).json()
    assert all(x.json() == confirmed for x in responses if x.status_code == 200)
    assert len(facts(f, record["project_id"])) == 1
    with f["sf"]() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(b.AnalysisSnapshotEntity)
                .where(b.AnalysisSnapshotEntity.project_version_id == record["project_version_id"])
            )
            == 1
        )


@pytest.mark.parametrize(
    "field",
    [
        "selected_products",
        "data_categories",
        "uploaded_documents",
        "organizations",
        "third_parties",
    ],
)
def test_unknown_or_other_project_refs_cannot_confirm(foundation_j, field):
    f = foundation_j
    binding(f)
    _, c, _, values = setup(f)
    record = create(c, {**values, field: [str(uuid4())]}).json()
    response = c.post(
        f"/api/v1/projects/{record['project_id']}/intake/confirm", json={"expected_version": 1}
    )
    assert response.status_code == 404, response.text
    assert not facts(f, record["project_id"])
    assert c.get(f"/api/v1/projects/{record['project_id']}/intake").json()["status"] == "DRAFT"
