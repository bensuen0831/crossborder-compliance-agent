"""Real scanner/S3 catalogue originals and immutable PostgreSQL import proposals."""

import io
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_kb01_batches_postgres import batches, count_versions, verified
from test_kb01_upload_postgres import begin, transfer
from test_kb01_upload_postgres import env as env

from crossborder_compliance.domain.knowledge_batches import CreateKnowledgeImportBatch
from crossborder_compliance.domain.knowledge_manifest_governance import PrepareKnowledgeManifest
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.knowledge_manifest_imports import (
    PostgresKnowledgeManifestImports,
)
from crossborder_compliance.infrastructure.persistence.knowledge_manifest_models import (
    KnowledgeManifestRecordEntity as Record,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)

pytestmark = pytest.mark.runtime_smoke


def owner(env, *, grants=None, tenant=None):
    f, _, upload_service, _ = env
    return PostgresKnowledgeManifestImports(
        f["sf"],
        RepositoryContext.user(
            UUID(tenant or f["tenant"]),
            "manifest-mapper",
            {
                "knowledge:batch:manifest-import",
                "knowledge:batch:manifest-read",
                "knowledge:batch:manifest-export",
                "knowledge:batch:read",
                "knowledge:upload:read",
                "knowledge:taxonomy:read",
            }
            if grants is None
            else grants,
        ),
        storage=upload_service.storage,
        working_root=Path(os.environ["KB01_TEST_WORK_ROOT"]) / "manifests",
    )


def catalogue_bytes(kind, rows):
    if kind == "CSV":
        import csv

        output = io.StringIO()
        csv.writer(output).writerows(rows)
        return output.getvalue().encode()
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def prepare_input(env, rows, *, kind="CSV"):
    f, uploads, service, worker = env
    batch = batches(f).create(
        CreateKnowledgeImportBatch(
            upload_session_ids=(
                UUID(verified(env, "one/same.txt")),
                UUID(verified(env, "two/same.txt")),
            ),
            idempotency_key=str(uuid4()),
        )
    )
    data = catalogue_bytes(kind, rows)
    _, upload = begin(
        service, data, relative_path="optional-catalogue." + kind.lower(), declared_format=kind
    )
    transfer(service, upload, data)
    assert worker.run_once()
    assert uploads.detail(upload["upload_session_id"])["status"] == "VERIFIED"
    request = PrepareKnowledgeManifest(
        upload_session_id=upload["upload_session_id"],
        expected_record_version=batch["record_version"],
        columns={"title": "Title", "relative_path": "Path"},
        idempotency_key=str(uuid4()),
    )
    return batch, request


@pytest.mark.parametrize("kind", ["CSV", "XLSX"])
def test_real_catalogue_preview_matches_full_path_and_survives_new_owner_without_publishing(
    env, kind
):
    f, _, _, _ = env
    batch, request = prepare_input(
        env, [["Title", "Path"], ["Synthetic original", "two/same.txt"]], kind=kind
    )
    before = count_versions(f)
    created = owner(env).prepare(batch["batch_id"], request)
    assert created["record_count"] == 1 and created["status"] == "COMPLETED"
    assert created["created_by"] == "manifest-mapper"
    assert owner(env).prepare(batch["batch_id"], request) == created
    loaded = owner(env).detail(batch["batch_id"], created["manifest_id"])
    assert loaded["total"] == 1 and loaded["items"][0]["status"] == "FILE_MATCHED"
    item = next(
        i
        for i in batches(f).detail(batch["batch_id"])["items"]
        if i["relative_path"] == "two/same.txt"
    )
    assert loaded["items"][0]["matched_item_id"] == item["item_id"]
    assert count_versions(f) == before
    from test_kb01_statistics_postgres import statistics

    inventory = statistics(f, set(owner(env).context.permission.scopes) | {"knowledge:statistics:read", "knowledge:document:read"}).summary(query="No matching document")["import_inventory"]
    assert inventory["scope"] == "TENANT_OPERATIONAL_UNFILTERED"
    assert inventory["manifest_records"] == 1 and inventory["missing_manifest_files"] == 0
    assert inventory["verified_uploads"] == 3 and inventory["verified_upload_bytes"] > 0
    assert statistics(f).summary()["import_inventory"] is None
    assert owner(env).list(batch["batch_id"])["total"] == 1
    report = owner(env).missing_files(batch["batch_id"], created["manifest_id"])
    assert report["total"] == 0 and report["unlisted_total"] == 1
    assert report["unlisted_files"][0]["relative_path"] == "one/same.txt"
    with pytest.raises(KnowledgeManagementConflict, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        owner(env).prepare(
            batch["batch_id"],
            request.model_copy(update={"columns": {"title": "Other", "relative_path": "Path"}}),
        )
    with pytest.raises(KnowledgeManagementConflict, match="BATCH_VERSION_CONFLICT"):
        owner(env).prepare(
            batch["batch_id"],
            request.model_copy(
                update={"idempotency_key": str(uuid4()), "expected_record_version": 999}
            ),
        )


def test_catalogue_duplicate_missing_and_unlisted_records_are_not_fabricated_files(env):
    batch, request = prepare_input(
        env,
        [
            ["Title", "Path"],
            ["Duplicate A", "one/same.txt"],
            ["Duplicate B", "one/same.txt"],
            ["Missing", "not-uploaded.txt"],
        ],
    )
    created = owner(env).prepare(batch["batch_id"], request)
    report = owner(env).missing_files(batch["batch_id"], created["manifest_id"], page_size=2)
    assert report["total"] == 3 and len(report["items"]) == 2
    assert all(row["status"] == "MAPPING_REQUIRED" for row in report["items"])
    assert all(
        any(issue["code"] == "DUPLICATE_CANDIDATE" for issue in row["issues"])
        for row in report["items"]
    )
    remaining = owner(env).missing_files(
        batch["batch_id"], created["manifest_id"], page=2, page_size=2
    )
    assert remaining["items"][0]["status"] == "FILE_MISSING"
    assert remaining["items"][0]["matched_item_id"] is None
    assert report["unlisted_total"] == 1


def test_formula_is_a_review_issue_and_never_evaluated(env):
    batch, request = prepare_input(env, [["Title", "Path"], ["=1+1", "one/same.txt"]], kind="XLSX")
    created = owner(env).prepare(batch["batch_id"], request)
    record = owner(env).detail(batch["batch_id"], created["manifest_id"])["items"][0]
    assert record["proposed_values"]["title"] == "=1+1"
    assert record["status"] == "MAPPING_REQUIRED"
    assert any(issue["code"] == "FORMULA_NOT_ALLOWED" for issue in record["issues"])


def test_bad_columns_persist_failed_preview_without_partial_proposals(env):
    batch, request = prepare_input(env, [["Title", "Path"], ["Synthetic", "one/same.txt"]])
    request = request.model_copy(
        update={"columns": {"title": "Unknown header", "relative_path": "Path"}}
    )
    created = owner(env).prepare(batch["batch_id"], request)
    assert created["status"] == "FAILED" and created["error_code"] == "MISSING_OR_AMBIGUOUS_COLUMNS"
    assert created["record_count"] == 0
    assert owner(env).detail(batch["batch_id"], created["manifest_id"])["items"] == []


def test_catalogue_receipts_are_immutable_and_not_attachable_as_legal_documents(env):
    f, _, service, _ = env
    batch, request = prepare_input(env, [["Title", "Path"], ["Synthetic", "one/same.txt"]])
    created = owner(env).prepare(batch["batch_id"], request)
    with f["sf"]() as s:
        row = s.scalar(select(Record).where(Record.manifest_id == created["manifest_id"]))
        identity = row.manifest_record_id
    for table, key, value in [
        ("knowledge_import_manifests", "manifest_id", created["manifest_id"]),
        ("knowledge_manifest_records", "manifest_record_id", identity),
    ]:
        with f["sf"]() as s, pytest.raises(DBAPIError, match="KB01_MANIFEST_RECEIPT_IMMUTABLE"):
            s.execute(text(f"DELETE FROM {table} WHERE {key}=:id"), {"id": value})
            s.commit()
    with pytest.raises(KnowledgeManagementConflict, match="BATCH_UPLOAD_NOT_VERIFIED"):
        batches(f).create(
            CreateKnowledgeImportBatch(
                upload_session_ids=(request.upload_session_id,), idempotency_key=str(uuid4())
            )
        )
    from test_kb01_document_management_postgres import make

    version = make(f)
    with pytest.raises(KnowledgeManagementConflict, match="NOT_ATTACHABLE"):
        service.repository.attach(
            request.upload_session_id,
            version["knowledge_version_id"],
            version["record_version"],
            str(uuid4()),
        )


def test_catalogue_scope_revocation_and_cross_tenant_are_fail_closed(env):
    batch, request = prepare_input(env, [["Title", "Path"], ["Synthetic", "one/same.txt"]])
    created = owner(env).prepare(batch["batch_id"], request)
    with pytest.raises(PermissionError):
        owner(env, grants={"knowledge:admin"}).prepare(batch["batch_id"], request)
    with pytest.raises(PermissionError):
        owner(env, grants={"knowledge:batch:read", "knowledge:batch:manifest-read"}).missing_files(
            batch["batch_id"], created["manifest_id"]
        )
    with pytest.raises(LookupError):
        owner(env, tenant=str(uuid4())).detail(batch["batch_id"], created["manifest_id"])


def test_explicit_batch_confirmation_retains_exact_catalogue_provenance(env):
    from test_kb01_batches_postgres import create_documents

    from crossborder_compliance.infrastructure.persistence import knowledge_models as k

    f, _, _, _ = env
    batch, request = prepare_input(
        env, [["Title", "Path"], ["Human reviewed title", "one/same.txt"]]
    )
    manifest = owner(env).prepare(batch["batch_id"], request)
    record = owner(env).detail(batch["batch_id"], manifest["manifest_id"])["items"][0]
    batch_owner = batches(f)
    batch_owner = batches(
        f, grants=set(batch_owner.context.permission.scopes) | {"knowledge:batch:manifest-read"}
    )
    item = next(
        i
        for i in batch_owner.detail(batch["batch_id"])["items"]
        if i["item_id"] == record["matched_item_id"]
    )
    command = create_documents(f, [item], batch["record_version"])
    command = command.model_copy(
        update={
            "mappings": (
                command.mappings[0].model_copy(
                    update={"manifest_record_id": UUID(record["manifest_record_id"])}
                ),
            )
        }
    )
    batch_owner.confirm_items(batch["batch_id"], command)
    actual = next(
        i for i in batch_owner.detail(batch["batch_id"])["items"] if i["item_id"] == item["item_id"]
    )
    assert actual["manifest_record_id"] == record["manifest_record_id"]
    with f["sf"]() as s:
        version = s.get(k.KnowledgeDocumentVersionEntity, actual["knowledge_version_id"])
        assert version.provenance_json["kb01_manifest_record_id"] == record["manifest_record_id"]
        assert version.lifecycle == "DRAFT"
    assert owner(env).detail(batch["batch_id"], manifest["manifest_id"])["items"][0] == record
    with (
        f["sf"]() as s,
        pytest.raises(DBAPIError, match="KB01_CONFIRMED_MANIFEST_BINDING_IMMUTABLE"),
    ):
        s.execute(
            text("UPDATE knowledge_batch_items SET manifest_record_id=NULL WHERE item_id=:id"),
            {"id": item["item_id"]},
        )
        s.commit()


def test_existing_genuine_catalogue_evidence_causes_atomic_downgrade_refusal(env):
    from test_phase1h_migrations import migrate

    from crossborder_compliance.config import get_settings

    batch, request = prepare_input(env, [["Title", "Path"], ["Synthetic", "one/same.txt"]])
    manifest = owner(env).prepare(batch["batch_id"], request)
    before = owner(env).detail(batch["batch_id"], manifest["manifest_id"])
    result = migrate(
        Path(__file__).resolve().parents[1],
        get_settings().database_url,
        "downgrade",
        "0023_kb01_evidence_source_reference",
    )
    assert result.returncode != 0 and "KB01_MANIFEST_GOVERNANCE_DOWNGRADE_REFUSED" in result.stderr
    assert owner(env).detail(batch["batch_id"], manifest["manifest_id"]) == before
