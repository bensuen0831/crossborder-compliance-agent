"""Durable per-item retry preserves the one canonical run and exact uploaded original."""

from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import select
from test_kb01_batches_postgres import batches, create_documents, verified
from test_kb01_binary_ingestion_postgres import ingestion
from test_kb01_upload_postgres import env as env

from crossborder_compliance.application.knowledge_services import KnowledgeIngestionService
from crossborder_compliance.domain.knowledge_batches import (
    CreateKnowledgeImportBatch,
    RetryKnowledgeBatchItem,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_batch_ingestion_worker import (
    KnowledgeBatchIngestionWorker,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
    PostgresKnowledgeImportBatches,
)
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)

pytestmark = pytest.mark.runtime_smoke


def ready(env):
    f, _, service, _ = env
    mapper = batches(f)
    row = mapper.create(
        CreateKnowledgeImportBatch(
            upload_session_ids=(UUID(verified(env)),),
            idempotency_key=str(uuid4()),
        )
    )
    preview = mapper.detail(row["batch_id"])
    mapper.confirm_items(
        row["batch_id"], create_documents(f, preview["items"], preview["record_version"])
    )
    _, configured = ingestion(f, service.storage)
    ctx = RepositoryContext.user(
        UUID(f["tenant"]),
        "native-worker",
        {
            "knowledge:batch:work",
            "knowledge:document:ingest",
        },
    )
    worker = KnowledgeBatchIngestionWorker(
        PostgresKnowledgeImportBatches(f["sf"], ctx),
        KnowledgeIngestionService(
            PostgresKnowledgeRepository(f["sf"], ctx), binary_extractor=configured.binary_extractor
        ),
    )
    return f, mapper, row["batch_id"], worker


def test_retry_recovers_real_native_ingestion_without_new_run_or_original(env, monkeypatch):
    f, mapper, identity, worker = ready(env)
    extractor = worker.ingestion.binary_extractor
    original_extract = extractor.extract

    def unavailable(_):
        raise ClientError({"Error": {"Code": "ServiceUnavailable"}}, "GetObject")

    monkeypatch.setattr(extractor, "extract", unavailable)
    assert worker.run_once()
    failed = mapper.detail(identity)
    item = failed["items"][0]
    assert (
        failed["status"] == "PARTIAL_FAILURE" and item["error_code"] == "BINARY_SOURCE_UNAVAILABLE"
    )
    with f["sf"]() as session:
        rows = session.scalars(
            select(k.KnowledgeIngestionRunEntity).where(
                k.KnowledgeIngestionRunEntity.knowledge_version_id == item["knowledge_version_id"]
            )
        ).all()
        assert len(rows) == 1 and rows[0].status == "FAILED"
        original_run = rows[0].ingestion_run_id
    command = RetryKnowledgeBatchItem(
        expected_record_version=failed["record_version"],
        expected_item_record_version=item["record_version"],
        idempotency_key=str(uuid4()),
    )
    resumed = mapper.retry_item(identity, item["item_id"], command)
    assert mapper.retry_item(identity, item["item_id"], command) == resumed
    monkeypatch.setattr(extractor, "extract", original_extract)
    assert worker.run_once()
    assert mapper.detail(identity)["counts"] == {"COMPLETED": 1}
    assert worker.run_once() is False
    with f["sf"]() as session:
        rows = session.scalars(
            select(k.KnowledgeIngestionRunEntity).where(
                k.KnowledgeIngestionRunEntity.knowledge_version_id == item["knowledge_version_id"]
            )
        ).all()
        assert len(rows) == 1 and rows[0].ingestion_run_id == original_run
        assert rows[0].status == "COMPLETED"


def test_failed_export_is_scoped_and_permanent_refusal_cannot_retry(env):
    f, mapper, identity, worker = ready(env)
    claim = worker.batches.ingestion_claim()
    worker.batches.ingestion_finished(claim, "NATIVE_EXTRACTION_REFUSED")
    failed = mapper.detail(identity)
    item = failed["items"][0]
    with pytest.raises(PermissionError):
        mapper.failures(identity)
    exporter = batches(f, grants={"knowledge:batch:read", "knowledge:batch:export"})
    page = exporter.failures(identity, page_size=1)
    assert page["total"] == 1 and page["items"][0]["technical_retry_available"] is False
    assert set(page["items"][0]) == {
        "item_id",
        "relative_path",
        "status",
        "error_code",
        "record_version",
        "attempts",
        "technical_retry_available",
    }
    foreign = PostgresKnowledgeImportBatches(
        f["sf"],
        RepositoryContext.user(
            uuid4(), "foreign", {"knowledge:batch:read", "knowledge:batch:export"}
        ),
    )
    with pytest.raises(LookupError):
        foreign.failures(identity)
    with pytest.raises(KnowledgeManagementConflict, match="NOT_RETRYABLE"):
        mapper.retry_item(
            identity,
            item["item_id"],
            RetryKnowledgeBatchItem(
                expected_record_version=failed["record_version"],
                expected_item_record_version=item["record_version"],
                idempotency_key=str(uuid4()),
            ),
        )


def test_retry_rejects_stale_item_revision_and_unknown_membership(env):
    _, mapper, identity, worker = ready(env)
    claim = worker.batches.ingestion_claim()
    worker.batches.ingestion_finished(claim, "BINARY_SOURCE_UNAVAILABLE")
    failed = mapper.detail(identity)
    item = failed["items"][0]
    command = RetryKnowledgeBatchItem(
        expected_record_version=failed["record_version"],
        expected_item_record_version=item["record_version"] - 1,
        idempotency_key=str(uuid4()),
    )
    with pytest.raises(KnowledgeManagementConflict, match="ITEM_VERSION_CONFLICT"):
        mapper.retry_item(identity, item["item_id"], command)
    with pytest.raises(LookupError):
        mapper.retry_item(
            identity,
            str(uuid4()),
            command.model_copy(
                update={
                    "idempotency_key": str(uuid4()),
                    "expected_item_record_version": item["record_version"],
                }
            ),
        )
    assert mapper.detail(identity)["counts"] == {"FAILED": 1}


def test_original_download_streams_exact_verified_version_as_safe_attachment(env):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from test_kb01_document_management_postgres import make
    from test_kb01_upload_postgres import begin, transfer

    from crossborder_compliance.interfaces.api.routes.knowledge_document_management import router

    f, uploads, upload_service, scanner = env
    original = b"Article 1. SYNTHETIC_GOVERNED_TEST_DATA.\n" * 40000
    # A real HTML original, not an HTML extension over plain text.
    original = b"<!doctype html><html><body><p>" + original + b"</p></body></html>"
    _, uploaded = begin(
        upload_service, original, relative_path="originals/條款.html", declared_format="HTML"
    )
    transfer(upload_service, uploaded, original)
    assert scanner.run_once()
    version = make(f)
    uploads.attach(
        UUID(uploaded["upload_session_id"]),
        UUID(version["knowledge_version_id"]),
        version["record_version"],
        str(uuid4()),
    )
    app = FastAPI()
    app.state.knowledge_session_factory = f["sf"]
    app.state.knowledge_binary_store = upload_service.storage
    app.include_router(router)
    active = {
        "context": RepositoryContext.user(
            UUID(f["tenant"]),
            "download-user",
            {
                "knowledge:document:read",
                "knowledge:document:download",
            },
        )
    }

    @app.middleware("http")
    async def trusted_host(request, call_next):
        request.state.repository_context = active["context"]
        return await call_next(request)

    url = (
        "/api/v1/admin/knowledge-management/documents/versions/"
        + version["knowledge_version_id"]
        + "/original"
    )
    with TestClient(app) as client:
        response = client.get(url)
        assert response.status_code == 200, response.text[:300]
        assert response.content == original
        assert response.headers["Content-Type"] == "application/octet-stream"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Content-Disposition"].startswith("attachment; filename*=UTF-8''")
        assert response.headers["Cache-Control"] == "no-store"
        active["context"] = RepositoryContext.user(
            UUID(f["tenant"]), "read-only", {"knowledge:document:read"}
        )
        assert client.get(url).status_code == 403
        active["context"] = RepositoryContext.user(
            uuid4(), "foreign", {"knowledge:document:read", "knowledge:document:download"}
        )
        assert client.get(url).status_code == 404
