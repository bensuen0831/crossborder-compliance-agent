"""Real PostgreSQL + real S3 multipart + isolated ClamAV transport evidence."""

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from test_kb01_document_management_postgres import make
from test_kb01_taxonomy_postgres import deletion_policy
from test_phase1f_postgres import fixture as foundation

from crossborder_compliance.application.knowledge_uploads import KnowledgeUploadService
from crossborder_compliance.domain.knowledge_management import KnowledgeManagementPermissionError
from crossborder_compliance.domain.knowledge_upload import (
    KnowledgeUploadMutation,
    KnowledgeUploadPartReceipt,
    KnowledgeUploadPartRequest,
    StartKnowledgeUpload,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_binary_storage import S3KnowledgeBinaryStore
from crossborder_compliance.infrastructure.knowledge_process_sandbox import (
    ClamKnowledgeScanner,
    KnowledgeProcessSandbox,
)
from crossborder_compliance.infrastructure.knowledge_upload_worker import KnowledgeUploadWorker
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeBinaryAttachmentEntity,
    KnowledgeUploadSessionEntity,
)
from crossborder_compliance.infrastructure.persistence.knowledge_uploads import (
    PostgresKnowledgeUploads,
)

pytestmark = pytest.mark.runtime_smoke
GRANTS = {
    "knowledge:upload:" + action
    for action in ("create", "read", "write", "complete", "work", "attach", "cancel", "retry")
}
GRANTS.add("knowledge:document:write")


def test_final_scan_lease_expiry_is_audited_and_not_left_running(env):
    from datetime import UTC, datetime, timedelta

    f, repo, service, _ = env
    data = b"Article 1. Synthetic final lease loss.\n"
    _, row = begin(service, data)
    transfer(service, row, data)
    claim = repo.scan_claim()
    with f["sf"]() as s, s.begin():
        saved = s.get(KnowledgeUploadSessionEntity, row["upload_session_id"])
        saved.attempts = 3
        saved.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert repo.scan_claim() is None
    state = repo.detail(row["upload_session_id"])
    assert state["status"] == "FAILED" and state["error_code"] == "SCANNER_TIMEOUT"
    with pytest.raises(KnowledgeManagementConflict, match="LEASE_LOST"):
        repo.scan_result(row["upload_session_id"], claim["lease_token"], {}, "SCANNER_UNAVAILABLE")
    with pytest.raises(KnowledgeManagementConflict, match="RETRY_NOT_ALLOWED"):
        repo.retry_scan(
            row["upload_session_id"],
            KnowledgeUploadMutation(
                expected_record_version=state["record_version"], idempotency_key=str(uuid4())
            ),
        )


def test_durable_cleanup_finishes_cancel_after_lost_provider_response(env):
    _, repo, service, _ = env
    _, row = begin(service, b"Article 1. Synthetic cancellation crash.\n")
    transport = repo.transport(row["upload_session_id"])
    repo.cancel_intent(
        row["upload_session_id"],
        KnowledgeUploadMutation(
            expected_record_version=row["record_version"], idempotency_key=str(uuid4())
        ),
    )
    service.storage.abort(transport["object_key"], transport["multipart_id"])
    assert service.cleanup_once()
    assert repo.detail(row["upload_session_id"])["status"] == "CANCELLED"
    assert service.cleanup_once() is False


@pytest.fixture
def env(request):
    f = foundation.__wrapped__()
    deletion_policy(
        (f["sf"], UUID(f["tenant"]), None, None),
        **getattr(request, "param", {}),
    )
    cfg_path = os.environ.get("KB01_TEST_S3_CONFIG")
    image = os.environ.get("KB01_TEST_TOOL_IMAGE")
    work = os.environ.get("KB01_TEST_WORK_ROOT")
    database = os.environ.get("KB01_TEST_SCAN_DATABASE")
    assert all((cfg_path, image, work, database)), (
        "Real KB01 transport acceptance services are required"
    )
    store = S3KnowledgeBinaryStore(**json.loads(Path(cfg_path).read_text()))
    context = RepositoryContext.user(UUID(f["tenant"]), "upload-user", GRANTS)
    repo = PostgresKnowledgeUploads(f["sf"], context)
    sandbox = KnowledgeProcessSandbox(image, Path(work))
    scanner = ClamKnowledgeScanner(
        sandbox, Path(database), "SYNTHETIC_SECURITY_SIGNATURES:EICAR_ONLY"
    )
    worker = KnowledgeUploadWorker(repo, store, scanner, sandbox, Path(work))
    return f, repo, KnowledgeUploadService(repo, store), worker


def begin(service, data, **changes):
    request = StartKnowledgeUpload(
        **{
            "relative_path": "legal-input.txt",
            "declared_format": "TXT",
            "declared_bytes": len(data),
            "content_sha256": hashlib.sha256(data).hexdigest(),
            "idempotency_key": str(uuid4()),
            **changes,
        }
    )
    return request, service.start(request)


def transfer(service, row, data):
    for number, start in enumerate(range(0, len(data), row["part_bytes"]), 1):
        part = data[start : start + row["part_bytes"]]
        digest = hashlib.sha256(part).hexdigest()
        signed = service.part_url(
            row["upload_session_id"],
            KnowledgeUploadPartRequest(
                part_number=number,
                content_sha256=digest,
            ),
        )
        with httpx.Client(trust_env=False) as client:
            response = client.put(signed["url"], content=part, headers=signed["headers"])
        assert response.status_code == 200
        result = service.acknowledge(
            row["upload_session_id"],
            KnowledgeUploadPartReceipt(
                part_number=number,
                content_sha256=digest,
                expected_record_version=row["record_version"],
                idempotency_key=str(uuid4()),
            ),
        )
        row = service.repository.detail(result["upload_session_id"])
    request = KnowledgeUploadMutation(
        expected_record_version=row["record_version"], idempotency_key=str(uuid4())
    )
    return request, service.complete(row["upload_session_id"], request)


def test_real_multipart_receipts_and_scan_are_not_knowledge_publication(env):
    f, repo, service, worker = env
    version = make(f)
    data = b"Article 1. This is a synthetic governed transport record.\n" * 700000
    _, row = begin(
        service,
        data,
        knowledge_version_id=version["knowledge_version_id"],
        expected_record_version=version["record_version"],
    )
    assert row["status"] == "UPLOADING" and row["created_by"] == "upload-user"
    _, completed = transfer(service, row, data)
    assert completed["status"] == "QUEUED_SCAN"
    with f["sf"]() as s:
        canonical = s.get(k.KnowledgeDocumentVersionEntity, version["knowledge_version_id"])
        assert canonical.lifecycle == "DRAFT" and canonical.original_artifact_ref is None
    assert worker.run_once()
    ready = repo.detail(row["upload_session_id"])
    assert ready["status"] == "VERIFIED" and len(ready["received_parts"]) == 2
    repo.attach(
        row["upload_session_id"],
        version["knowledge_version_id"],
        version["record_version"],
        str(uuid4()),
    )
    with f["sf"]() as s:
        canonical = s.get(k.KnowledgeDocumentVersionEntity, version["knowledge_version_id"])
        assert (
            canonical.lifecycle == "DRAFT"
            and canonical.content_hash == hashlib.sha256(data).hexdigest()
        )
        assert (
            s.scalar(
                select(KnowledgeBinaryAttachmentEntity).where(
                    KnowledgeBinaryAttachmentEntity.knowledge_version_id
                    == canonical.knowledge_version_id,
                )
            ).attached_by
            == "upload-user"
        )


def test_repeated_start_and_completion_reuse_exact_provider_upload(env):
    _, repo, service, worker = env
    data = b"Article 1. Deterministic transport replay."
    request, row = begin(service, data)
    with repo.sessions() as s:
        upload_id = s.get(KnowledgeUploadSessionEntity, row["upload_session_id"]).multipart_id
    replay = service.start(request)
    assert replay["upload_session_id"] == row["upload_session_id"]
    with repo.sessions() as s:
        assert (
            s.get(KnowledgeUploadSessionEntity, row["upload_session_id"]).multipart_id == upload_id
        )
    completion, _ = transfer(service, row, data)
    assert service.complete(row["upload_session_id"], completion)["status"] == "QUEUED_SCAN"
    assert worker.run_once()
    assert service.complete(row["upload_session_id"], completion)["status"] == "VERIFIED"


def test_idempotency_cannot_change_declared_binary(env):
    _, _, service, _ = env
    request, _ = begin(service, b"Article 1.")
    with pytest.raises(KnowledgeManagementConflict, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        service.start(request.model_copy(update={"content_sha256": "a" * 64}))


def test_cross_tenant_and_revoked_current_grant_fail_closed(env):
    f, _, service, _ = env
    _, row = begin(service, b"Article 1.")
    other = PostgresKnowledgeUploads(f["sf"], RepositoryContext.user(uuid4(), "other", GRANTS))
    with pytest.raises(LookupError):
        other.detail(row["upload_session_id"])
    revoked = PostgresKnowledgeUploads(
        f["sf"], RepositoryContext.user(UUID(f["tenant"]), "upload-user", set())
    )
    with pytest.raises(KnowledgeManagementPermissionError):
        revoked.detail(row["upload_session_id"])


def test_stale_part_cas_and_incomplete_completion_are_rejected(env):
    _, _, service, _ = env
    data = b"Article 1."
    _, row = begin(service, data)
    with pytest.raises(KnowledgeManagementConflict, match="INCOMPLETE_OR_CHANGED"):
        service.complete(
            row["upload_session_id"],
            KnowledgeUploadMutation(
                expected_record_version=row["record_version"],
                idempotency_key=str(uuid4()),
            ),
        )
    digest = hashlib.sha256(data).hexdigest()
    signed = service.part_url(
        row["upload_session_id"], KnowledgeUploadPartRequest(part_number=1, content_sha256=digest)
    )
    with httpx.Client(trust_env=False) as client:
        assert client.put(signed["url"], content=data, headers=signed["headers"]).status_code == 200
    with pytest.raises(KnowledgeManagementConflict, match="VERSION_CONFLICT"):
        service.acknowledge(
            row["upload_session_id"],
            KnowledgeUploadPartReceipt(
                expected_record_version=row["record_version"] + 1,
                idempotency_key=str(uuid4()),
                part_number=1,
                content_sha256=digest,
            ),
        )


def test_malware_is_quarantined_and_cannot_be_attached(env):
    f, repo, service, worker = env
    data = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    _, row = begin(service, data)
    transfer(service, row, data)
    assert worker.run_once()
    assert repo.detail(row["upload_session_id"])["status"] == "QUARANTINED"
    version = make(f)
    with pytest.raises(KnowledgeManagementConflict, match="NOT_ATTACHABLE"):
        repo.attach(row["upload_session_id"], version["knowledge_version_id"], 1, str(uuid4()))


def test_declared_complete_hash_is_independently_verified(env):
    _, repo, service, worker = env
    data = b"Article 1. Actual content."
    _, row = begin(service, data, content_sha256="a" * 64)
    transfer(service, row, data)
    assert worker.run_once()
    result = repo.detail(row["upload_session_id"])
    assert result["status"] == "FAILED" and result["error_code"] == "BINARY_VERIFICATION_FAILED"


def test_scan_lease_is_single_winner_and_recovers_after_expiry(env):
    _, repo, service, _ = env
    _, row = begin(service, b"Article 1.")
    transfer(service, row, b"Article 1.")
    claim = repo.scan_claim()
    assert claim and repo.scan_claim() is None
    from datetime import UTC, datetime, timedelta

    with repo.sessions() as s, s.begin():
        upload = s.get(KnowledgeUploadSessionEntity, row["upload_session_id"])
        upload.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    successor = repo.scan_claim()
    assert successor["lease_token"] != claim["lease_token"]
    with pytest.raises(KnowledgeManagementConflict, match="LEASE_LOST"):
        repo.scan_result(row["upload_session_id"], claim["lease_token"], {}, "SCANNER_UNAVAILABLE")


def test_cancel_aborts_provider_and_releases_only_unconsumed_transport(env):
    _, repo, service, _ = env
    _, row = begin(service, b"Article 1. Cancel before completion.")
    request = KnowledgeUploadMutation(
        expected_record_version=row["record_version"], idempotency_key=str(uuid4())
    )
    result = service.cancel(row["upload_session_id"], request)
    assert result["status"] == "CANCELLED"
    assert service.cancel(row["upload_session_id"], request)["status"] == "CANCELLED"
    with pytest.raises(KnowledgeManagementConflict, match="NOT_WRITABLE"):
        service.part_url(
            row["upload_session_id"],
            KnowledgeUploadPartRequest(
                part_number=1,
                content_sha256=row["content_sha256"],
            ),
        )


def test_scanner_failure_retry_keeps_the_exact_binary_and_is_bounded(env):
    _, repo, service, worker = env
    _, row = begin(service, b"Article 1. Retry offline scan.")
    transfer(service, row, b"Article 1. Retry offline scan.")
    claim = repo.scan_claim()
    repo.scan_result(row["upload_session_id"], claim["lease_token"], {}, "SCANNER_UNAVAILABLE")
    failed = repo.detail(row["upload_session_id"])
    repo.retry_scan(
        row["upload_session_id"],
        KnowledgeUploadMutation(
            expected_record_version=failed["record_version"],
            idempotency_key=str(uuid4()),
        ),
    )
    assert worker.run_once()
    final = repo.detail(row["upload_session_id"])
    assert final["status"] == "VERIFIED" and final["attempts"] == 2
    assert final["content_sha256"] == row["content_sha256"]


def test_upload_http_authentication_and_safe_projection(env):
    f, repo, service, _ = env
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from crossborder_compliance.interfaces.api.routes.knowledge_uploads import router

    app = FastAPI()
    app.include_router(router)
    app.state.knowledge_session_factory = f["sf"]
    app.state.knowledge_binary_store = service.storage
    payload = StartKnowledgeUpload(
        relative_path="source.txt",
        declared_format="TXT",
        declared_bytes=10,
        content_sha256="a" * 64,
        idempotency_key=str(uuid4()),
    ).model_dump(mode="json")
    unauthenticated = FastAPI()
    unauthenticated.include_router(router)
    with TestClient(unauthenticated) as client:
        assert (
            client.post(
                "/api/v1/admin/knowledge-management/upload-sessions", json=payload
            ).status_code
            == 401
        )

    @app.middleware("http")
    async def trusted_host(request: Request, call_next):
        # Host assertion belongs to this engineering harness, not a production auth claim.
        request.state.repository_context = repo.context
        return await call_next(request)

    with TestClient(app) as client:
        result = client.post("/api/v1/admin/knowledge-management/upload-sessions", json=payload)
        assert result.status_code == 201, result.text
        content = result.json()
        assert content["created_by"] == "upload-user"
        assert not {"object_key", "multipart_id", "object_version", "secret_key"} & content.keys()
        identity = content["upload_session_id"]
        # SQL progress is readable even when the storage adapter is unconfigured.
        app.state.knowledge_binary_store = None
        assert (
            client.get("/api/v1/admin/knowledge-management/upload-sessions/" + identity).status_code
            == 200
        )


def test_upload_manifest_and_completed_part_receipts_are_database_immutable(env):
    _, repo, service, _ = env
    from sqlalchemy.exc import DBAPIError

    from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
        KnowledgeUploadPartEntity,
    )

    data = b"Article 1. Immutable transport manifest."
    _, row = begin(service, data)
    with pytest.raises(DBAPIError, match="KB01_UPLOAD_MANIFEST_IMMUTABLE"):
        with repo.sessions() as s, s.begin():
            s.get(KnowledgeUploadSessionEntity, row["upload_session_id"]).declared_bytes += 1
    transfer(service, row, data)
    with pytest.raises(DBAPIError, match="KB01_COMPLETED_UPLOAD_PART_IMMUTABLE"):
        with repo.sessions() as s, s.begin():
            part = s.get(KnowledgeUploadPartEntity, (repo.tenant, row["upload_session_id"], 1))
            part.content_sha256 = "f" * 64


def test_attached_original_cannot_be_replaced_even_while_version_is_draft(env):
    f, repo, service, worker = env
    from sqlalchemy.exc import DBAPIError

    version = make(f)
    data = b"Article 1. Immutable original reference."
    _, row = begin(service, data)
    transfer(service, row, data)
    assert worker.run_once()
    repo.attach(row["upload_session_id"], version["knowledge_version_id"], 1, str(uuid4()))
    with pytest.raises(DBAPIError, match="KB01_ORIGINAL_BINARY_IDENTITY_IMMUTABLE"):
        with repo.sessions() as s, s.begin():
            canonical = s.get(k.KnowledgeDocumentVersionEntity, version["knowledge_version_id"])
            canonical.content_hash = "0" * 64


def test_upload_policy_view_comes_from_the_governed_tenant_version(env):
    f, repo, _, _ = env
    policy = repo.policy_view()
    assert policy["max_single_bytes"] >= 500_000_000
    assert policy["max_archive_bytes"] > 1_000_000_000
    assert set(policy["allowed_document_formats"]) == {"DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML"}
    assert set(policy["allowed_archive_formats"]) == {"RAR", "ZIP"}
    with f["sf"]() as session:
        from crossborder_compliance.infrastructure.persistence import metadata_models as m

        stored = session.get(m.MetadataVersionEntity, policy["policy_version_id"])
        assert stored.tenant_id == f["tenant"] and stored.lifecycle_status == "ACTIVE"
        assert stored.payload_json["max_single_bytes"] == policy["max_single_bytes"]
    restricted = PostgresKnowledgeUploads(
        f["sf"], RepositoryContext.user(UUID(f["tenant"]), "coarse-only", {"knowledge:admin"})
    )
    with pytest.raises(PermissionError):
        restricted.policy_view()


@pytest.mark.parametrize("env", [{}, {"scanner_memory_bytes": 4 * 1024**3}], indirect=True)
def test_worker_scans_with_frozen_upload_memory_budget(env, monkeypatch):
    # Exercise real S3 bytes and real ClamAV, including pre-field persisted policy.
    f, repo, service, worker = env
    data = b"Article 1. Synthetic frozen scanner budget.\n"
    _, row = begin(service, data)
    frozen_budget = repo.transport(row["upload_session_id"])["policy"]["scanner_memory_bytes"]
    # Replay the pre-field representation without changing the persisted policy.
    if frozen_budget == 2 * 1024**3:
        actual_claim = repo.scan_claim

        def claim():
            result = actual_claim()
            if result:
                result["policy"] = dict(result["policy"])
                result["policy"].pop("scanner_memory_bytes", None)
            return result

        monkeypatch.setattr(repo, "scan_claim", claim)
    transfer(service, row, data)
    actual_scan = worker.scanner.scan
    observed = []

    def scan(*args, **kwargs):
        observed.append(kwargs["memory_bytes"])
        return actual_scan(*args, **kwargs)

    monkeypatch.setattr(worker.scanner, "scan", scan)
    assert worker.run_once()
    assert repo.detail(row["upload_session_id"])["status"] == "VERIFIED"
    assert observed == [frozen_budget]
