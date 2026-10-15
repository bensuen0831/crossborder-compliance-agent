"""Real originals, S3, scanner and native process reach the existing Knowledge owner."""

import io
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from docx import Document
from sqlalchemy import select
from test_kb01_document_management_postgres import make
from test_kb01_upload_postgres import begin, transfer
from test_kb01_upload_postgres import env as env
from test_phase1f_postgres import binding

from crossborder_compliance.application.knowledge_services import KnowledgeIngestionService
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_binary_extraction import (
    NativeKnowledgeBinarySourceExtractor,
)
from crossborder_compliance.infrastructure.knowledge_native_parser import (
    IsolatedNativeKnowledgeParser,
)
from crossborder_compliance.infrastructure.knowledge_process_sandbox import KnowledgeProcessSandbox
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)

pytestmark = pytest.mark.runtime_smoke


def ingestion(f, storage):
    image = os.environ.get("KB01_TEST_NATIVE_IMAGE")
    root = os.environ.get("KB01_TEST_NATIVE_WORK_ROOT")
    assert image and root, "Actual offline native parser tooling is required"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    parser = IsolatedNativeKnowledgeParser(KnowledgeProcessSandbox(image, root))
    owner = PostgresKnowledgeRepository(
        f["sf"],
        RepositoryContext.user(
            UUID(f["tenant"]), "native-ingester", {"knowledge:admin", "knowledge:document:ingest"}
        ),
    )
    return owner, KnowledgeIngestionService(
        owner, binary_extractor=NativeKnowledgeBinarySourceExtractor(storage, parser, root)
    )


@pytest.mark.parametrize("format", ["TXT", "DOCX", "HTML", "XHTML", "DOC", "PDF"])
def test_original_binary_becomes_canonical_structure_citation_and_evidence(env, format):
    f, uploads, service, scanner = env
    text = "Article 1. SYNTHETIC_GOVERNED_TEST_DATA. 法規條文. المادة ١."
    if format in {"DOC", "PDF"}:
        import tempfile

        from kb01_native_fixtures import native_original

        root = Path(os.environ["KB01_TEST_NATIVE_WORK_ROOT"])
        root.mkdir(parents=True, exist_ok=True)
        if format == "PDF":
            text = "Article 1. SYNTHETIC_GOVERNED_TEST_DATA"
        with tempfile.TemporaryDirectory(dir=root) as folder:
            folder = Path(folder)
            folder.chmod(0o755)
            path = native_original(
                format,
                text,
                folder,
                KnowledgeProcessSandbox(os.environ["KB01_TEST_NATIVE_IMAGE"], root),
            )
            content = path.read_bytes()
    elif format == "DOCX":
        original = io.BytesIO()
        doc = Document()
        doc.add_paragraph(text)
        doc.save(original)
        content = original.getvalue()
    elif format in {"HTML", "XHTML"}:
        content = ("<html><body><p>" + text + "</p></body></html>").encode()
    else:
        content = text.encode()
    version = make(f)
    _, row = begin(
        service, content, relative_path="original." + format.lower(), declared_format=format
    )
    transfer(service, row, content)
    assert scanner.run_once()
    uploads.attach(
        row["upload_session_id"],
        version["knowledge_version_id"],
        version["record_version"],
        str(uuid4()),
    )
    owner, worker = ingestion(f, service.storage)
    before = owner.get_version(version["knowledge_version_id"])
    payload = {
        "binary_upload_session_id": row["upload_session_id"],
        "expected_record_version": before["record_version"],
        "idempotency_key": str(uuid4()),
        "bindings": [binding(f)],
    }
    run = worker.ingest(version["knowledge_version_id"], payload)
    assert worker.work(run["ingestion_run_id"])["status"] == "COMPLETED"
    assert worker.work(run["ingestion_run_id"])["status"] == "COMPLETED"
    after = owner.get_version(version["knowledge_version_id"])
    assert after["content_hash"] == before["content_hash"]
    assert after["original_artifact_ref"] == before["original_artifact_ref"]
    assert after["lifecycle"] == "INGESTED"
    with f["sf"]() as s:
        nodes = s.scalars(
            select(k.KnowledgeStructureNodeEntity).where(
                k.KnowledgeStructureNodeEntity.knowledge_version_id
                == version["knowledge_version_id"]
            )
        ).all()
        assert len(nodes) == 1 and text in nodes[0].original_text
        assert nodes[0].source_trace_json["content_hash"] == before["content_hash"]
        assert nodes[0].source_trace_json["upload_session_id"] == row["upload_session_id"]
        assert nodes[0].citation_id and nodes[0].regulatory_structure_node_id
        saved = s.get(k.KnowledgeIngestionRunEntity, run["ingestion_run_id"])
        assert saved.audit_json["native_parser"]["blocks"] == 1
        assert saved.input_json["binary_scope"]["policy_version_id"]
    checked = owner.governance(version["knowledge_version_id"], "validate", after["record_version"])
    assert checked["lifecycle"] == "VALIDATED"


def test_native_ingestion_worker_needs_no_broad_admin_or_publication_authority(env):
    f, uploads, service, scanner = env
    content = b"Article 1. SYNTHETIC_GOVERNED_TEST_DATA restricted ingestion.\n"
    version = make(f)
    _, row = begin(service, content)
    transfer(service, row, content)
    assert scanner.run_once()
    uploads.attach(
        row["upload_session_id"],
        version["knowledge_version_id"],
        version["record_version"],
        str(uuid4()),
    )
    inspector, configured = ingestion(f, service.storage)
    current = inspector.get_version(version["knowledge_version_id"])
    inspector.create_binding(version["knowledge_version_id"], binding(f), current["record_version"])
    current = inspector.get_version(version["knowledge_version_id"])
    worker_owner = PostgresKnowledgeRepository(
        f["sf"],
        RepositoryContext.user(
            UUID(f["tenant"]), "restricted-native-worker", {"knowledge:document:ingest"}
        ),
    )
    worker = KnowledgeIngestionService(worker_owner, binary_extractor=configured.binary_extractor)
    run = worker.ingest(
        version["knowledge_version_id"],
        {
            "binary_upload_session_id": row["upload_session_id"],
            "expected_record_version": current["record_version"],
            "idempotency_key": str(uuid4()),
        },
    )
    assert worker.work(run["ingestion_run_id"])["status"] == "COMPLETED"
    assert worker_owner.get_run(run["ingestion_run_id"])["status"] == "COMPLETED"
    with pytest.raises(PermissionError):
        worker_owner.governance(version["knowledge_version_id"], "validate", 1)
    with pytest.raises(PermissionError):
        worker_owner.schedule_ingestion(
            version["knowledge_version_id"],
            {
                "nodes": [
                    {
                        "canonical_locator": "forged",
                        "original_text": "Not an authorized native source",
                    }
                ],
                "idempotency_key": str(uuid4()),
            },
        )


def test_durable_batch_ingestion_uses_single_canonical_run_and_keeps_original(env):
    from test_kb01_batches_postgres import batches, create_documents

    from crossborder_compliance.domain.knowledge_batches import CreateKnowledgeImportBatch
    from crossborder_compliance.infrastructure.knowledge_batch_ingestion_worker import (
        KnowledgeBatchIngestionWorker,
    )
    from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
        PostgresKnowledgeImportBatches,
    )

    f, uploads, service, scanner = env
    content = b"Article 1. SYNTHETIC_GOVERNED_TEST_DATA batch native extraction.\n"
    _, row = begin(service, content)
    transfer(service, row, content)
    assert scanner.run_once()
    mapper = batches(f)
    batch = mapper.create(
        CreateKnowledgeImportBatch(
            upload_session_ids=(UUID(row["upload_session_id"]),), idempotency_key=str(uuid4())
        )
    )
    preview = mapper.detail(batch["batch_id"])
    mapper.confirm_items(
        batch["batch_id"], create_documents(f, preview["items"], preview["record_version"])
    )
    owner, configured = ingestion(f, service.storage)
    version_id = mapper.detail(batch["batch_id"])["items"][0]["knowledge_version_id"]
    before = owner.get_version(version_id)
    owner.create_binding(version_id, binding(f), before["record_version"])
    context = RepositoryContext.user(
        UUID(f["tenant"]),
        "batch-native-worker",
        {"knowledge:batch:work", "knowledge:document:ingest"},
    )
    batch_worker = KnowledgeBatchIngestionWorker(
        PostgresKnowledgeImportBatches(f["sf"], context),
        KnowledgeIngestionService(
            PostgresKnowledgeRepository(f["sf"], context),
            binary_extractor=configured.binary_extractor,
        ),
    )
    assert batch_worker.run_once()
    assert batch_worker.run_once() is False
    complete = mapper.detail(batch["batch_id"])
    assert complete["status"] == "COMPLETED" and complete["counts"] == {"COMPLETED": 1}
    after = owner.get_version(version_id)
    assert after["lifecycle"] == "INGESTED" and after["content_hash"] == before["content_hash"]
    assert after["original_artifact_ref"] == before["original_artifact_ref"]
    with f["sf"]() as s:
        runs = s.scalars(
            select(k.KnowledgeIngestionRunEntity).where(
                k.KnowledgeIngestionRunEntity.knowledge_version_id == version_id
            )
        ).all()
        assert len(runs) == 1 and runs[0].status == "COMPLETED"


def test_batch_resume_after_completed_ingestion_does_not_reparse_or_duplicate(env, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from test_kb01_batches_postgres import batches, create_documents

    from crossborder_compliance.domain.knowledge_batches import CreateKnowledgeImportBatch
    from crossborder_compliance.infrastructure.knowledge_batch_ingestion_worker import (
        KnowledgeBatchIngestionWorker,
    )
    from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
        PostgresKnowledgeImportBatches,
    )
    from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
        KnowledgeBatchItemEntity,
    )

    f, _, service, scanner = env
    content = b"Article 1. Synthetic canonical ingestion restart.\n"
    _, row = begin(service, content)
    transfer(service, row, content)
    assert scanner.run_once()
    mapper = batches(f)
    batch = mapper.create(
        CreateKnowledgeImportBatch(
            upload_session_ids=(UUID(row["upload_session_id"]),), idempotency_key=str(uuid4())
        )
    )
    preview = mapper.detail(batch["batch_id"])
    mapper.confirm_items(
        batch["batch_id"], create_documents(f, preview["items"], preview["record_version"])
    )
    inspector, configured = ingestion(f, service.storage)
    item = mapper.detail(batch["batch_id"])["items"][0]
    context = RepositoryContext.user(
        UUID(f["tenant"]),
        "durable-native-worker",
        {"knowledge:batch:work", "knowledge:document:ingest"},
    )
    repository = PostgresKnowledgeImportBatches(f["sf"], context)
    worker = KnowledgeBatchIngestionWorker(
        repository,
        KnowledgeIngestionService(
            PostgresKnowledgeRepository(f["sf"], context),
            binary_extractor=configured.binary_extractor,
        ),
    )
    finish = repository.ingestion_finished

    def crash(*args):
        raise RuntimeError("Synthetic process loss after genuine canonical ingestion commit")

    monkeypatch.setattr(repository, "ingestion_finished", crash)
    with pytest.raises(RuntimeError, match="Synthetic process loss"):
        worker.run_once()
    saved = inspector.get_version(item["knowledge_version_id"])
    assert saved["lifecycle"] == "INGESTED"
    with f["sf"]() as s, s.begin():
        s.get(KnowledgeBatchItemEntity, item["item_id"]).lease_expires_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
    monkeypatch.setattr(repository, "ingestion_finished", finish)

    def no_hidden_reparse(*args):
        raise AssertionError("Completed canonical ingestion must not re-extract original")

    monkeypatch.setattr(configured.binary_extractor, "extract", no_hidden_reparse)
    assert worker.run_once()
    assert mapper.detail(batch["batch_id"])["status"] == "COMPLETED"
    assert inspector.get_version(item["knowledge_version_id"]) == saved
    with f["sf"]() as s:
        assert (
            len(
                s.scalars(
                    select(k.KnowledgeIngestionRunEntity).where(
                        k.KnowledgeIngestionRunEntity.knowledge_version_id
                        == item["knowledge_version_id"]
                    )
                ).all()
            )
            == 1
        )


def test_batch_cancel_after_mapping_preserves_canonical_draft_without_new_work(env):
    from test_kb01_batches_postgres import batches, create_documents

    from crossborder_compliance.domain.knowledge_batches import CreateKnowledgeImportBatch
    from crossborder_compliance.domain.knowledge_upload import KnowledgeUploadMutation

    f, _, service, scanner = env
    data = b"Article 1. Explicit cancellation retains authorized original.\n"
    _, row = begin(service, data)
    transfer(service, row, data)
    assert scanner.run_once()
    mapper = batches(f)
    batch = mapper.create(
        CreateKnowledgeImportBatch(
            upload_session_ids=(UUID(row["upload_session_id"]),), idempotency_key=str(uuid4())
        )
    )
    preview = mapper.detail(batch["batch_id"])
    confirmed = mapper.confirm_items(
        batch["batch_id"], create_documents(f, preview["items"], preview["record_version"])
    )
    inspector, _ = ingestion(f, service.storage)
    item = mapper.detail(batch["batch_id"])["items"][0]
    before = inspector.get_version(item["knowledge_version_id"])
    cancelled = mapper.cancel(
        batch["batch_id"],
        KnowledgeUploadMutation(
            expected_record_version=confirmed["record_version"], idempotency_key=str(uuid4())
        ),
    )
    assert cancelled["status"] == "CANCELLED"
    assert mapper.detail(batch["batch_id"])["counts"] == {"CANCELLED": 1}
    assert inspector.get_version(item["knowledge_version_id"]) == before


def test_standalone_native_request_has_durable_canonical_work_identity(env):
    from crossborder_compliance.infrastructure.knowledge_batch_ingestion_worker import (
        KnowledgeBatchIngestionWorker,
    )
    from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
        PostgresKnowledgeImportBatches,
    )

    f, uploads, service, scanner = env
    data = b"Article 1. Standalone canonical source and durable work.\n"
    version = make(f)
    _, row = begin(service, data)
    transfer(service, row, data)
    assert scanner.run_once()
    uploads.attach(
        row["upload_session_id"],
        version["knowledge_version_id"],
        version["record_version"],
        str(uuid4()),
    )
    inspector, configured = ingestion(f, service.storage)
    current = inspector.get_version(version["knowledge_version_id"])
    context = RepositoryContext.user(
        UUID(f["tenant"]),
        "standalone-worker",
        {"knowledge:document:ingest", "knowledge:batch:work"},
    )
    owner = PostgresKnowledgeRepository(f["sf"], context)
    ingestion_service = KnowledgeIngestionService(
        owner, binary_extractor=configured.binary_extractor
    )
    run = ingestion_service.ingest(
        version["knowledge_version_id"],
        {
            "binary_upload_session_id": row["upload_session_id"],
            "expected_record_version": current["record_version"],
            "idempotency_key": str(uuid4()),
        },
    )
    batches = PostgresKnowledgeImportBatches(f["sf"], context)
    first = batches.queue_existing_ingestion(run["ingestion_run_id"])
    assert (
        batches.queue_existing_ingestion(run["ingestion_run_id"])["batch_id"] == first["batch_id"]
    )
    assert KnowledgeBatchIngestionWorker(batches, ingestion_service).run_once()
    assert owner.get_run(run["ingestion_run_id"])["status"] == "COMPLETED"


def test_runtime_worker_rejects_system_identity_instead_of_bypassing_current_roles(env):
    from crossborder_compliance.infrastructure.knowledge_management_worker import (
        KnowledgeManagementWorker,
    )

    f, _, service, scanner = env
    _, configured = ingestion(f, service.storage)
    runtime = KnowledgeManagementWorker(
        f["sf"],
        service.storage,
        scanner.scanner,
        scanner.sandbox,
        None,
        configured.binary_extractor.parser,
        lambda: [RepositoryContext.system(UUID(f["tenant"]))],
        Path(os.environ["KB01_TEST_NATIVE_WORK_ROOT"]),
    )
    with pytest.raises(PermissionError, match="SCOPED_IDENTITY"):
        runtime.run_once()
