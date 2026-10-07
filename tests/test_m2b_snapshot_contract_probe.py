"""Real binary/PG proof that the former frozen temporal blocker is corrected."""
# ruff: noqa: F401,F811 -- shared real PostgreSQL fixture graph
import io
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_m2b_document_inputs import host, upload
from test_phase1j_postgres import fixture, foundation_i, foundation_j

from crossborder_compliance.infrastructure.intake_composition import project_context
from crossborder_compliance.infrastructure.persistence import context_models as e
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.classification_repository import (
    PostgresFormalClassificationRepository,
)

pytestmark = pytest.mark.runtime_smoke


def document_bytes(value, header="Field"):
    from docx import Document

    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = header
    table.cell(0, 1).text = "Type"
    table.cell(1, 0).text = value
    table.cell(1, 1).text = "number"
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def test_stable_item_has_exact_immutable_snapshot_state_and_provenance(foundation_j, tmp_path):
    from test_m2a_intake import create

    f = foundation_j
    _, client, context, values = host(f, tmp_path)
    initial = create(client, values).json()
    project_id = initial["project_id"]
    base_url = f"/api/v1/projects/{project_id}/intake"
    media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    first_bytes = document_bytes("first-value")
    first_upload = upload(client, initial, first_bytes, name="fields.docx", media=media)
    assert first_upload.status_code == 201, first_upload.text
    first_view = first_upload.json()
    first_document = first_view["items"][0]
    parsed = client.post(
        base_url + f"/documents/{first_document['document_version_id']}/parse",
        json={"expected_version": 2, "idempotency_key": str(uuid4())},
    )
    assert parsed.status_code == 200 and parsed.json()["items"][0]["parse_status"] == "COMPLETED", parsed.text
    first_confirm = client.post(base_url + "/confirm", json={"expected_version": 2})
    assert first_confirm.status_code == 200, first_confirm.text
    first_snapshot = first_confirm.json()["analysis_snapshot_id"]

    scoped_context = project_context(f["sf"], context, UUID(project_id))
    classifier = PostgresFormalClassificationRepository(f["sf"], scoped_context)
    with f["sf"]() as session:
        item = session.scalar(select(b.DataItemEntity).where(
            b.DataItemEntity.tenant_id == f["tenant"],
            b.DataItemEntity.project_id == project_id,
            b.DataItemEntity.name == "field",
        ))
        assert item is not None
        item_id = item.data_item_id
        original_traces = set(session.scalars(select(e.DataItemSourceTraceLinkEntity.source_trace_ref_id).where(
            e.DataItemSourceTraceLinkEntity.data_item_id == item_id,
        )))
    # H accepts the original snapshot; this is not a missing permission/config.
    classifier.prepare(UUID(project_id), UUID(first_snapshot), UUID(item_id), UUID(f["scheme_version"]))
    from crossborder_compliance.application.context_services import DataItemNormalizationService
    from crossborder_compliance.infrastructure.persistence.context_repositories import PostgresContextResolutionRepository
    from crossborder_compliance.infrastructure.persistence import document_models as d
    repeated = PostgresContextResolutionRepository(f["sf"], scoped_context,
        parse_run_ids=(UUID(parsed.json()["items"][0]["parse_run_id"]),))
    assert item_id in {str(value) for value in DataItemNormalizationService(repeated).normalize(UUID(project_id), version=1).values()}

    superseded = client.post(base_url + "/supersede", json={"expected_version": 2, "idempotency_key": str(uuid4())})
    assert superseded.status_code == 200, superseded.text
    replaced = client.post(base_url + "/documents", data={
        "expected_version": 3,
        "idempotency_key": str(uuid4()),
        "replace_document_id": first_document["document_id"],
    }, files={"file": ("fields.docx", document_bytes("later-value", header="FIELD"), media)})
    assert replaced.status_code == 201, replaced.text
    second_document = replaced.json()["items"][0]
    assert second_document["document_id"] == first_document["document_id"]
    assert second_document["document_version_id"] != first_document["document_version_id"]
    second_parse = client.post(base_url + f"/documents/{second_document['document_version_id']}/parse", json={
        "expected_version": 4, "idempotency_key": str(uuid4()),
    })
    assert second_parse.status_code == 200 and second_parse.json()["items"][0]["parse_status"] == "COMPLETED", second_parse.text
    second_confirm = client.post(base_url + "/confirm", json={"expected_version": 4})
    assert second_confirm.status_code == 200, second_confirm.text
    second_snapshot = second_confirm.json()["analysis_snapshot_id"]
    assert second_snapshot != first_snapshot

    with f["sf"]() as session:
        pins = session.scalars(select(e.AnalysisSnapshotContextPinEntity).where(
            e.AnalysisSnapshotContextPinEntity.analysis_snapshot_id.in_([first_snapshot, second_snapshot]),
        )).all()
        inventory = {pin.analysis_snapshot_id: pin.data_inventory_version for pin in pins}
        from crossborder_compliance.infrastructure.persistence.context_temporal import exact_item_detail
        detail = exact_item_detail(session, f["tenant"], item_id, 1)
        second_detail = exact_item_detail(session, f["tenant"], item_id, 2)
        all_items = session.scalars(select(b.DataItemEntity).where(b.DataItemEntity.project_id == project_id)).all()
        current_traces = set(session.scalars(select(e.DataItemSourceTraceLinkEntity.source_trace_ref_id).where(
            e.DataItemSourceTraceLinkEntity.data_item_id == item_id,
        )))
        assert inventory[first_snapshot] == detail.version == 1
        assert inventory[second_snapshot] == 2
        assert len(all_items) == 2  # Field + Type headers, no duplicated authoritative item.
        assert original_traces < current_traces

    assert detail.display_name == "Field" and second_detail.display_name == "FIELD"
    with pytest.raises(ValueError, match="IMMUTABLE_INVENTORY"):
        DataItemNormalizationService(PostgresContextResolutionRepository(f["sf"], scoped_context,
            parse_run_ids=(UUID(second_parse.json()["items"][0]["parse_run_id"]),))).normalize(UUID(project_id), version=1)
    classifier.prepare(UUID(project_id), UUID(second_snapshot), UUID(item_id), UUID(f["scheme_version"]))
    from crossborder_compliance.infrastructure.persistence.context_temporal import item_trace_ids
    with f["sf"]() as session:
        v1_traces = set(item_trace_ids(session, f["tenant"], item_id, 1, first_snapshot))
        v2_traces = set(item_trace_ids(session, f["tenant"], item_id, 2, second_snapshot))
        assert v1_traces == original_traces
        assert v2_traces and v1_traces.isdisjoint(v2_traces)
    # Old snapshot validation and provenance remain unchanged.
    classifier.prepare(UUID(project_id), UUID(first_snapshot), UUID(item_id), UUID(f["scheme_version"]))
    from crossborder_compliance.infrastructure.persistence.knowledge_repositories import PostgresKnowledgeRepository
    knowledge = PostgresKnowledgeRepository(f["sf"], scoped_context)
    assert knowledge.formal_context(project_id, "DATA_ITEM", item_id, first_snapshot)["context_version"] == 1
    assert knowledge.formal_context(project_id, "DATA_ITEM", item_id, second_snapshot)["context_version"] == 2
    assert client.post(base_url + "/supersede", json={"expected_version": 4, "idempotency_key": str(uuid4())}).status_code == 200
    removed = client.post(base_url + f"/documents/{second_document['document_version_id']}/unlink", json={"expected_version": 5, "idempotency_key": str(uuid4())})
    assert removed.status_code == 200 and not removed.json()["items"]
    absent = client.post(base_url + "/confirm", json={"expected_version": 6})
    assert absent.status_code == 200, absent.text
    absent_snapshot = absent.json()["analysis_snapshot_id"]
    with f["sf"]() as session:
        with pytest.raises(LookupError): exact_item_detail(session, f["tenant"], item_id, 3)
        with pytest.raises(LookupError): exact_item_detail(session, f["tenant"], item_id, 999)
        assert set(item_trace_ids(session, f["tenant"], item_id, 1, first_snapshot)) == original_traces
    with pytest.raises(LookupError): classifier.prepare(UUID(project_id), UUID(absent_snapshot), UUID(item_id), UUID(f["scheme_version"]))
    with pytest.raises(LookupError): knowledge.formal_context(project_id, "DATA_ITEM", item_id, absent_snapshot)
    assert client.post(base_url + "/supersede", json={"expected_version": 6, "idempotency_key": str(uuid4())}).status_code == 200
    returning_record = client.get(base_url).json()
    returning = upload(client, returning_record, first_bytes, name="fields.docx", media=media)
    assert returning.status_code == 201, returning.text
    resumed_doc = returning.json()["items"][0]
    parsed = client.post(base_url + f"/documents/{resumed_doc['document_version_id']}/parse", json={"expected_version": 8, "idempotency_key": str(uuid4())})
    assert parsed.status_code == 200, parsed.text
    restored = client.post(base_url + "/confirm", json={"expected_version": 8})
    assert restored.status_code == 200, restored.text
    restored_snapshot = restored.json()["analysis_snapshot_id"]
    with f["sf"]() as session:
        restored_detail = exact_item_detail(session, f["tenant"], item_id, 4)
        assert restored_detail.data_item_id == item_id
        assert restored_detail.display_name == detail.display_name
        assert set(item_trace_ids(session, f["tenant"], item_id, 1, first_snapshot)) == original_traces
    classifier.prepare(UUID(project_id), UUID(restored_snapshot), UUID(item_id), UUID(f["scheme_version"]))
    assert knowledge.formal_context(project_id, "DATA_ITEM", item_id, restored_snapshot)["context_version"] == 4
    evidence = {
        "status": "TEMPORAL_COUNTEREXAMPLE_CORRECTED_NOT_FULL_CLOSURE",
        "database": "real PostgreSQL",
        "project_id": project_id,
        "data_item_id": item_id,
        "first_snapshot_id": first_snapshot,
        "second_snapshot_id": second_snapshot,
        "first_document_version_id": first_document["document_version_id"],
        "second_document_version_id": second_document["document_version_id"],
        "first_inventory_version": inventory[first_snapshot],
        "second_inventory_version": inventory[second_snapshot],
        "retained_detail_version": detail.version,
        "first_snapshot_prepare": "ACCEPTED",
        "second_snapshot_prepare": "ACCEPTED",
        "original_trace_ids": sorted(original_traces),
        "current_trace_ids": sorted(current_traces),
        "provenance_links_versioned": True,
        "formal_data_items_duplicated": False,
    }
    target = Path("artifacts/m2b/temporal_contract_result.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2) + "\n")
