"""Canonical PostgreSQL import mapping and real isolated archive/S3 work."""

import io
import os
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_kb01_upload_postgres import begin, transfer
from test_kb01_upload_postgres import env as env

from crossborder_compliance.domain.knowledge_batches import (
    ConfirmKnowledgeBatchItems,
    CreateKnowledgeImportBatch,
    KnowledgeBatchMapping,
)
from crossborder_compliance.domain.knowledge_management import (
    CreateManagedKnowledgeDocument,
    KnowledgeDocumentMetadata,
    KnowledgeManagementPermissionError,
)
from crossborder_compliance.domain.knowledge_upload import KnowledgeUploadMutation
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_archive_extractor import (
    IsolatedKnowledgeArchiveExtractor,
)
from crossborder_compliance.infrastructure.knowledge_import_worker import KnowledgeImportWorker
from crossborder_compliance.infrastructure.knowledge_process_sandbox import KnowledgeProcessSandbox
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
    PostgresKnowledgeImportBatches,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)

pytestmark = pytest.mark.runtime_smoke


def batches(f, actor="batch-mapper", grants=None):
    permissions = {
        "knowledge:batch:" + action
        for action in ["create", "read", "work", "confirm", "cancel", "retry"]
    } | {"knowledge:document:write", "knowledge:upload:attach"}
    return PostgresKnowledgeImportBatches(
        f["sf"],
        RepositoryContext.user(UUID(f["tenant"]), actor, permissions if grants is None else grants),
    )


def verified(env, name="法律/original.txt"):
    _, repo, service, worker = env
    data = b"Article 1. SYNTHETIC_GOVERNED_TEST_DATA for canonical import.\n"
    _, row = begin(service, data, relative_path=name)
    transfer(service, row, data)
    assert worker.run_once()
    assert repo.detail(row["upload_session_id"])["status"] == "VERIFIED"
    return row["upload_session_id"]


def create_documents(f, items, version, **changes):
    return ConfirmKnowledgeBatchItems(
        expected_record_version=version,
        idempotency_key=str(uuid4()),
        mappings=tuple(
            KnowledgeBatchMapping(
                item_id=UUID(item["item_id"]),
                document=CreateManagedKnowledgeDocument(
                    source_id=UUID(f["source"]),
                    collection_version_id=UUID(f["cv"]),
                    language="en",
                    metadata=KnowledgeDocumentMetadata(title=item["relative_path"]),
                    idempotency_key=str(uuid4()),
                ),
            )
            for item in items
        ),
        **changes,
    )


def count_versions(f):
    with f["sf"]() as s:
        return s.scalar(
            select(func.count())
            .select_from(k.KnowledgeDocumentVersionEntity)
            .where(k.KnowledgeDocumentVersionEntity.tenant_id == f["tenant"])
        )


def test_batch_uses_canonical_drafts_only_after_explicit_mapping(env):
    f, repo, _, _ = env
    owner = batches(f)
    identities = [verified(env), verified(env, "قانون/two.txt")]
    before = count_versions(f)
    command = CreateKnowledgeImportBatch(
        upload_session_ids=tuple(map(UUID, identities)), idempotency_key=str(uuid4())
    )
    batch = owner.create(command)
    assert owner.create(command)["batch_id"] == batch["batch_id"]
    preview = owner.detail(batch["batch_id"], page_size=1)
    assert preview["total"] == 2 and len(preview["items"]) == 1
    assert count_versions(f) == before
    items = owner.detail(batch["batch_id"])["items"]
    decision = create_documents(f, items, batch["record_version"])
    result = owner.confirm_items(batch["batch_id"], decision)
    assert owner.confirm_items(batch["batch_id"], decision) == result
    assert result["status"] == "CONFIRMED"
    assert count_versions(f) == before + 2
    for item in owner.detail(batch["batch_id"])["items"]:
        assert item["status"] == "READY"
        with f["sf"]() as s:
            version = s.get(k.KnowledgeDocumentVersionEntity, item["knowledge_version_id"])
            assert version.lifecycle == "DRAFT"
            assert version.provenance_json["created_by"] == "batch-mapper"
            assert (
                version.original_artifact_ref
                and version.content_hash == repo.detail(item["upload_session_id"])["content_sha256"]
            )
    with pytest.raises(KnowledgeManagementConflict, match="UPLOAD_ALREADY_ATTACHED"):
        owner.create(command.model_copy(update={"idempotency_key": str(uuid4())}))


def test_foreign_item_rolls_back_all_canonical_mapping(env):
    f, _, _, _ = env
    owner = batches(f)
    batch = owner.create(
        CreateKnowledgeImportBatch(
            upload_session_ids=(UUID(verified(env)),), idempotency_key=str(uuid4())
        )
    )
    items = owner.detail(batch["batch_id"])["items"] + [
        {"item_id": str(uuid4()), "relative_path": "foreign.txt"}
    ]
    before = count_versions(f)
    with pytest.raises(KnowledgeManagementConflict, match="ITEM_NOT_CONFIRMABLE"):
        owner.confirm_items(batch["batch_id"], create_documents(f, items, batch["record_version"]))
    assert count_versions(f) == before
    assert owner.detail(batch["batch_id"])["counts"] == {"UNMAPPED": 1}


def test_batch_tenant_grants_cas_and_cancel_preserve_original(env):
    f, repo, _, _ = env
    owner = batches(f)
    upload = verified(env)
    batch = owner.create(
        CreateKnowledgeImportBatch(upload_session_ids=(UUID(upload),), idempotency_key=str(uuid4()))
    )
    with pytest.raises(KnowledgeManagementPermissionError):
        batches(f, grants=set()).detail(batch["batch_id"])
    other = PostgresKnowledgeImportBatches(
        f["sf"], RepositoryContext.user(uuid4(), "other", {"knowledge:batch:read"})
    )
    with pytest.raises(LookupError):
        other.detail(batch["batch_id"])
    with pytest.raises(KnowledgeManagementConflict, match="VERSION_CONFLICT"):
        owner.cancel(
            batch["batch_id"],
            KnowledgeUploadMutation(
                expected_record_version=batch["record_version"] + 1, idempotency_key=str(uuid4())
            ),
        )
    cancelled = owner.cancel(
        batch["batch_id"],
        KnowledgeUploadMutation(
            expected_record_version=batch["record_version"], idempotency_key=str(uuid4())
        ),
    )
    assert cancelled["status"] == "CANCELLED"
    assert repo.detail(upload)["status"] == "VERIFIED"
    with pytest.raises(KnowledgeManagementConflict, match="NOT_CONFIRMABLE"):
        owner.confirm_items(
            batch["batch_id"],
            create_documents(
                f, owner.detail(batch["batch_id"])["items"], cancelled["record_version"]
            ),
        )


@pytest.mark.parametrize("archive_type", ["ZIP", "RAR4", "RAR5"])
def test_durable_archive_worker_creates_verified_originals_not_legal_results(
    env, tmp_path, archive_type
):
    from kb01_archive_fixtures import write_rar4, write_rar5

    f, repo, uploads, scanner = env
    original = tmp_path / "original.txt"
    data = b"Article 1. Genuine synthetic archive import original.\n"
    original.write_bytes(data)
    source = tmp_path / ("source.zip" if archive_type == "ZIP" else "source.rar")
    if archive_type == "ZIP":
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("法律/original.txt", data)
    else:
        (write_rar4 if archive_type == "RAR4" else write_rar5)(source, [("original.txt", original)])
    _, row = begin(
        uploads,
        source.read_bytes(),
        relative_path=source.name,
        declared_format=source.suffix[1:].upper(),
    )
    transfer(uploads, row, source.read_bytes())
    assert scanner.run_once()
    owner = batches(f)
    batch = owner.create(
        CreateKnowledgeImportBatch(
            archive_upload_session_id=UUID(row["upload_session_id"]), idempotency_key=str(uuid4())
        )
    )
    before = count_versions(f)
    root = Path(os.environ["KB01_TEST_ARCHIVE_WORK_ROOT"])
    extractor = IsolatedKnowledgeArchiveExtractor(
        KnowledgeProcessSandbox(os.environ["KB01_TEST_ARCHIVE_IMAGE"], root)
    )
    worker = KnowledgeImportWorker(owner, uploads, uploads.storage, extractor, root)
    assert worker.run_once()
    preview = owner.detail(batch["batch_id"])
    assert preview["status"] == "PREVIEW" and preview["total"] == 1
    assert preview["items"][0]["mapping_available"] is False
    assert preview["items"][0]["transport_pending"] is True
    assert preview["items"][0]["upload_status"] == "QUEUED_SCAN"
    assert count_versions(f) == before
    command = create_documents(f, preview["items"], preview["record_version"])
    with pytest.raises(KnowledgeManagementConflict, match="UPLOAD_NOT_VERIFIED"):
        owner.confirm_items(batch["batch_id"], command)
    assert scanner.run_once()
    child = repo.detail(preview["items"][0]["upload_session_id"])
    assert child["status"] == "VERIFIED"
    ready = owner.detail(batch["batch_id"])["items"][0]
    assert ready["mapping_available"] is True and ready["transport_pending"] is False
    assert ready["upload_status"] == "VERIFIED"
    owner.confirm_items(batch["batch_id"], command)
    assert count_versions(f) == before + 1
    assert worker.run_once() is False


def test_archive_batch_unsupported_member_fails_without_fabricated_draft(env):
    f, _, uploads, scanner = env
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("unsupported.exe", b"Not a governed knowledge document")
    data = content.getvalue()
    _, row = begin(uploads, data, relative_path="unsupported.zip", declared_format="ZIP")
    transfer(uploads, row, data)
    assert scanner.run_once()
    owner = batches(f)
    batch = owner.create(
        CreateKnowledgeImportBatch(
            archive_upload_session_id=UUID(row["upload_session_id"]), idempotency_key=str(uuid4())
        )
    )
    root = Path(os.environ["KB01_TEST_ARCHIVE_WORK_ROOT"])
    extractor = IsolatedKnowledgeArchiveExtractor(
        KnowledgeProcessSandbox(os.environ["KB01_TEST_ARCHIVE_IMAGE"], root)
    )
    before = count_versions(f)
    assert KnowledgeImportWorker(owner, uploads, uploads.storage, extractor, root).run_once()
    result = owner.detail(batch["batch_id"])
    assert (
        result["status"] == "FAILED" and result["error_code"] == "UNSUPPORTED_ARCHIVE_MEMBER_FORMAT"
    )
    assert count_versions(f) == before


def test_import_transport_recovery_reuses_completed_child_after_lost_receipt(env, monkeypatch):
    import httpx

    from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
        KnowledgeUploadSessionEntity,
    )

    f, _, uploads, scanner = env
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("legal/original.txt", "Article 1. Genuine resumable synthetic input.")
    data = content.getvalue()
    _, row = begin(uploads, data, relative_path="resume.zip", declared_format="ZIP")
    transfer(uploads, row, data)
    assert scanner.run_once()
    owner = batches(f)
    batch = owner.create(
        CreateKnowledgeImportBatch(
            archive_upload_session_id=UUID(row["upload_session_id"]), idempotency_key=str(uuid4())
        )
    )
    root = Path(os.environ["KB01_TEST_ARCHIVE_WORK_ROOT"])
    extractor = IsolatedKnowledgeArchiveExtractor(
        KnowledgeProcessSandbox(os.environ["KB01_TEST_ARCHIVE_IMAGE"], root)
    )
    worker = KnowledgeImportWorker(owner, uploads, uploads.storage, extractor, root)
    persist = owner.extracted_item

    def lost_receipt(*args):
        raise httpx.ConnectError("Synthetic crash after genuine multipart completion")

    monkeypatch.setattr(owner, "extracted_item", lost_receipt)
    assert worker.run_once()
    failed = owner.detail(batch["batch_id"])
    assert failed["status"] == "FAILED" and failed["error_code"] == "IMPORT_TRANSPORT_UNAVAILABLE"
    with f["sf"]() as s:
        original_uploads = set(
            s.scalars(
                select(KnowledgeUploadSessionEntity.upload_session_id).where(
                    KnowledgeUploadSessionEntity.tenant_id == f["tenant"]
                )
            )
        )
    assert len(original_uploads) == 2
    monkeypatch.setattr(owner, "extracted_item", persist)
    owner.retry(
        batch["batch_id"],
        KnowledgeUploadMutation(
            expected_record_version=failed["record_version"], idempotency_key=str(uuid4())
        ),
    )
    assert worker.run_once()
    recovered = owner.detail(batch["batch_id"])
    assert recovered["status"] == "PREVIEW" and recovered["total"] == 1
    with f["sf"]() as s:
        assert (
            set(
                s.scalars(
                    select(KnowledgeUploadSessionEntity.upload_session_id).where(
                        KnowledgeUploadSessionEntity.tenant_id == f["tenant"]
                    )
                )
            )
            == original_uploads
        )
    assert scanner.run_once()
    owner.confirm_items(
        batch["batch_id"], create_documents(f, recovered["items"], recovered["record_version"])
    )


def test_import_cancellation_rejects_late_worker_and_preserves_history(env):
    f, _, uploads, scanner = env
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("one.txt", "Article 1. Cancellation input.")
    data = content.getvalue()
    _, row = begin(uploads, data, relative_path="cancel.zip", declared_format="ZIP")
    transfer(uploads, row, data)
    assert scanner.run_once()
    owner = batches(f)
    batch = owner.create(
        CreateKnowledgeImportBatch(
            archive_upload_session_id=UUID(row["upload_session_id"]), idempotency_key=str(uuid4())
        )
    )
    claim = owner.extraction_claim()
    assert claim["batch_id"] == batch["batch_id"]
    assert owner.extraction_claim() is None
    current = owner.detail(batch["batch_id"])
    cancelled = owner.cancel(
        batch["batch_id"],
        KnowledgeUploadMutation(
            expected_record_version=current["record_version"], idempotency_key=str(uuid4())
        ),
    )
    with pytest.raises(KnowledgeManagementConflict, match="LEASE_LOST"):
        owner.extraction_finished(batch["batch_id"], claim["lease_token"], "a" * 64, 0)
    assert owner.detail(batch["batch_id"])["status"] == cancelled["status"] == "CANCELLED"


def test_batch_manifest_and_member_identity_are_database_immutable(env):
    from sqlalchemy.exc import DBAPIError

    from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
        KnowledgeBatchItemEntity,
        KnowledgeImportBatchEntity,
    )

    f, _, _, _ = env
    owner = batches(f)
    batch = owner.create(
        CreateKnowledgeImportBatch(
            upload_session_ids=(UUID(verified(env)),), idempotency_key=str(uuid4())
        )
    )
    item = owner.detail(batch["batch_id"])["items"][0]
    for entity, identity, field, value in [
        (KnowledgeImportBatchEntity, batch["batch_id"], "manifest_digest", "f" * 64),
        (KnowledgeImportBatchEntity, batch["batch_id"], "created_by", "spoofed"),
        (KnowledgeBatchItemEntity, item["item_id"], "relative_path", "replaced.txt"),
    ]:
        with pytest.raises(DBAPIError, match="IMMUTABLE"):
            with f["sf"]() as s, s.begin():
                setattr(s.get(entity, identity), field, value)


def test_one_batch_preserves_distinct_governed_countries_per_file_without_manifest(env):
    from test_kb01_document_management_postgres import published_label
    from test_kb01_statistics_postgres import statistics

    from crossborder_compliance.domain.knowledge_management import TaxonomyPayload
    from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
        KnowledgeDocumentLabelEntity,
    )

    f, _, _, _ = env
    countries = tuple(
        published_label(f, "JURISDICTION_CONFIG", TaxonomyPayload(jurisdiction_type="COUNTRY"))
        for _ in range(2)
    )
    owner = batches(f)
    batch = owner.create(
        CreateKnowledgeImportBatch(
            upload_session_ids=tuple(
                UUID(verified(env, path)) for path in ("country-a/same.txt", "country-b/same.txt")
            ),
            idempotency_key=str(uuid4()),
        )
    )
    items = owner.detail(batch["batch_id"])["items"]
    command = create_documents(f, items, batch["record_version"])
    command = command.model_copy(
        update={
            "mappings": tuple(
                mapping.model_copy(
                    update={
                        "document": mapping.document.model_copy(
                            update={
                                "metadata": mapping.document.metadata.model_copy(
                                    update={"labels": (country,)}
                                )
                            }
                        )
                    }
                )
                for mapping, country in zip(command.mappings, countries, strict=True)
            )
        }
    )
    owner.confirm_items(batch["batch_id"], command)
    saved = {item["item_id"]: item for item in owner.detail(batch["batch_id"])["items"]}
    for mapping, country in zip(command.mappings, countries, strict=True):
        item = saved[str(mapping.item_id)]
        assert item["manifest_record_id"] is None and item["status"] == "READY"
        with f["sf"]() as session:
            labels = session.scalars(
                select(KnowledgeDocumentLabelEntity).where(
                    KnowledgeDocumentLabelEntity.tenant_id == f["tenant"],
                    KnowledgeDocumentLabelEntity.knowledge_version_id
                    == item["knowledge_version_id"],
                )
            ).all()
            assert {(row.definition_id, row.metadata_version_id) for row in labels} == {
                (str(country.definition_id), str(country.version_id))
            }
        assert statistics(f).summary(label_id=country.definition_id)["documents"] == 1
    assert {item["relative_path"] for item in saved.values()} == {
        "country-a/same.txt",
        "country-b/same.txt",
    }
