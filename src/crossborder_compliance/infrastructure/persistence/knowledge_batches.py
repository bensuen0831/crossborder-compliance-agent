"""Durable import coordination over canonical uploads and knowledge versions."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import func, select, text

from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.domain.knowledge_paths import safe_relative_path
from crossborder_compliance.infrastructure.persistence.knowledge_document_management import (
    PostgresKnowledgeDocumentManagement,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeBatchItemEntity as Item,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeBinaryAttachmentEntity as Attachment,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeImportBatchEntity as Batch,
)
from crossborder_compliance.infrastructure.persistence.knowledge_uploads import (
    PostgresKnowledgeUploads,
)


def batch_manifest_digest(records):
    digest = hashlib.sha256()
    for row in sorted(records, key=lambda item: item["relative_path"]):
        digest.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


class PostgresKnowledgeImportBatches:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant, self.actor = str(context.tenant_id), context.permission.actor_id
        self.uploads = PostgresKnowledgeUploads(sessions, context)
        self.management = self.uploads.management
        self.documents = PostgresKnowledgeDocumentManagement(sessions, context)

    def _get(self, s, identity, lock=False):
        query = select(Batch).where(Batch.tenant_id == self.tenant, Batch.batch_id == str(identity))
        row = s.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise LookupError("batch not found")
        return row

    def _items(self, identity):
        return select(Item).where(Item.tenant_id == self.tenant, Item.batch_id == str(identity))

    @staticmethod
    def _view(row):
        return {
            "batch_id": row.batch_id,
            "archive_upload_session_id": row.archive_upload_session_id,
            "created_by": row.created_by,
            "status": row.status,
            "record_version": row.record_version,
            "manifest_digest": row.manifest_digest,
            "attempts": row.attempts,
            "error_code": row.error_code,
        }

    def _audit(self, s, action, row, idem, reason):
        return self.management._audit(
            s,
            action,
            SimpleNamespace(kind="KNOWLEDGE_IMPORT_BATCH", definition_id=row.batch_id),
            reason,
            idem,
            self._view(row),
        )

    @staticmethod
    def _cas(row, expected):
        if row.record_version != expected:
            raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_VERSION_CONFLICT")

    def _new_item(self, s, batch, upload, path):
        path = safe_relative_path(path)
        if (
            s.scalar(
                select(Attachment).where(
                    Attachment.tenant_id == self.tenant,
                    Attachment.upload_session_id == upload.upload_session_id,
                )
            )
            or upload.knowledge_version_id
        ):
            raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_UPLOAD_ALREADY_ATTACHED")
        other = s.scalar(
            select(Item)
            .join(Batch, (Batch.batch_id == Item.batch_id) & (Batch.tenant_id == Item.tenant_id))
            .where(
                Item.tenant_id == self.tenant,
                Item.upload_session_id == upload.upload_session_id,
                Batch.status != "CANCELLED",
            )
        )
        if other:
            if other.batch_id == batch.batch_id and other.relative_path == path:
                return other
            raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_ALREADY_IN_BATCH")
        item = Item(
            item_id=str(uuid4()),
            tenant_id=self.tenant,
            batch_id=batch.batch_id,
            upload_session_id=upload.upload_session_id,
            relative_path=path,
            status="UNMAPPED",
            proposed_metadata_json={},
        )
        s.add(item)
        return item

    def create(self, request):
        require_management_permission(self.context, "batch:create")
        with self.sessions() as s, s.begin():
            idem, cached = self.management._key(
                s, "BATCH_CREATE", request.idempotency_key, request.model_dump(mode="json")
            )
            if cached is not None:
                return self._view(self._get(s, cached["batch_id"]))
            row = Batch(
                batch_id=str(uuid4()),
                tenant_id=self.tenant,
                created_by=self.actor,
                archive_upload_session_id=str(request.archive_upload_session_id)
                if request.archive_upload_session_id
                else None,
                status="PENDING" if request.archive_upload_session_id else "PREVIEW",
            )
            s.add(row)
            s.flush()
            if request.archive_upload_session_id:
                archive = self.uploads._get(s, request.archive_upload_session_id, True)
                if archive.status != "VERIFIED" or archive.declared_format not in {"RAR", "ZIP"}:
                    raise KnowledgeManagementConflict("KNOWLEDGE_ARCHIVE_NOT_VERIFIED")
                duplicate = s.scalar(
                    select(Batch).where(
                        Batch.tenant_id == self.tenant,
                        Batch.archive_upload_session_id == archive.upload_session_id,
                        Batch.batch_id != row.batch_id,
                        Batch.status != "CANCELLED",
                    )
                )
                if duplicate:
                    raise KnowledgeManagementConflict("KNOWLEDGE_ARCHIVE_ALREADY_IN_BATCH")
            else:
                records = []
                paths = set()
                for identity in sorted(request.upload_session_ids, key=str):
                    upload = self.uploads._get(s, identity, True)
                    if upload.status != "VERIFIED" or upload.declared_format in {"RAR", "ZIP"}:
                        raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_UPLOAD_NOT_VERIFIED")
                    if upload.relative_path.casefold() in paths:
                        raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_PATH_COLLISION")
                    paths.add(upload.relative_path.casefold())
                    self._new_item(s, row, upload, upload.relative_path)
                    records.append(
                        {
                            "relative_path": upload.relative_path,
                            "byte_size": upload.declared_bytes,
                            "content_sha256": upload.content_sha256,
                        }
                    )
                row.manifest_digest = batch_manifest_digest(records)
            s.flush()
            return self._audit(s, "BATCH_CREATE", row, idem, "Create technical import work")

    def detail(self, identity, *, page=1, page_size=50):
        require_management_permission(self.context, "batch:read")
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("INVALID_PAGINATION")
        with self.sessions() as s:
            batch = self._get(s, identity)
            counts = s.execute(
                select(Item.status, func.count())
                .where(Item.tenant_id == self.tenant, Item.batch_id == batch.batch_id)
                .group_by(Item.status)
            ).all()
            rows = s.scalars(
                self._items(identity)
                .order_by(Item.relative_path)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                **self._view(batch),
                "counts": dict(counts),
                "total": sum(v for _, v in counts),
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        "item_id": item.item_id,
                        "upload_session_id": item.upload_session_id,
                        "relative_path": item.relative_path,
                        "knowledge_version_id": item.knowledge_version_id,
                        "status": item.status,
                        "record_version": item.record_version,
                        "error_code": item.error_code,
                    }
                    for item in rows
                ],
            }

    def extraction_claim(self):
        require_management_permission(self.context, "batch:work")
        with self.sessions() as s, s.begin():
            now = datetime.now(UTC)
            row = s.scalar(
                select(Batch)
                .where(
                    Batch.tenant_id == self.tenant,
                    Batch.attempts < 3,
                    (Batch.status == "PENDING")
                    | ((Batch.status == "EXTRACTING") & (Batch.lease_expires_at <= now)),
                )
                .order_by(Batch.created_at, Batch.batch_id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            archive = self.uploads._get(s, row.archive_upload_session_id)
            if archive.status != "VERIFIED":
                raise KnowledgeManagementConflict("KNOWLEDGE_ARCHIVE_NOT_VERIFIED")
            row.status, row.lease_token = "EXTRACTING", str(uuid4())
            row.lease_expires_at = now + timedelta(
                seconds=archive.policy_json["extraction_timeout_seconds"] + 300
            )
            row.attempts += 1
            row.record_version += 1
            return {
                **self._view(row),
                "lease_token": row.lease_token,
                "archive": {
                    "object_key": archive.object_key,
                    "object_version": archive.object_version,
                    "declared_bytes": archive.declared_bytes,
                    "content_sha256": archive.content_sha256,
                    "policy": archive.policy_json,
                },
            }

    @staticmethod
    def _lease(row, token):
        if (
            row.status != "EXTRACTING"
            or row.lease_token != token
            or row.lease_expires_at <= datetime.now(UTC)
        ):
            raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_LEASE_LOST")

    def heartbeat(self, identity, token):
        require_management_permission(self.context, "batch:work")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            self._lease(row, token)
            row.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

    def extracted_item(self, identity, token, upload_id, record):
        require_management_permission(self.context, "batch:work")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            self._lease(row, token)
            upload = self.uploads._get(s, upload_id, True)
            if (
                upload.declared_bytes != record["byte_size"]
                or upload.content_sha256 != record["content_sha256"]
                or upload.relative_path != record["relative_path"]
                or upload.status not in {"QUEUED_SCAN", "SCANNING", "VERIFIED"}
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_MEMBER_INTEGRITY_FAILED")
            self._new_item(s, row, upload, record["relative_path"])

    def extraction_finished(self, identity, token, digest, count, error=None):
        require_management_permission(self.context, "batch:work")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            self._lease(row, token)
            if error:
                if error not in {
                    "ARCHIVE_EXTRACTION_REFUSED",
                    "UNSUPPORTED_ARCHIVE_MEMBER_FORMAT",
                    "KNOWLEDGE_PROCESS_DISK_BUDGET_EXHAUSTED",
                    "BINARY_VERIFICATION_FAILED",
                    "IMPORT_TRANSPORT_UNAVAILABLE",
                }:
                    raise ValueError("INVALID_BATCH_FAILURE_CODE")
                row.status, row.error_code = "FAILED", error
            else:
                if (
                    s.scalar(select(func.count()).select_from(self._items(identity).subquery()))
                    != count
                ):
                    raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_MEMBER_COUNT_MISMATCH")
                row.status, row.manifest_digest, row.error_code = "PREVIEW", digest, None
            row.lease_expires_at = None
            row.record_version += 1
            idem, cached = self.management._key(
                s,
                "BATCH_EXTRACT",
                token,
                {"batch_id": row.batch_id, "manifest_digest": digest, "error": error},
            )
            return cached or self._audit(
                s, "BATCH_EXTRACT", row, idem, "Isolated archive extraction finished"
            )

    def confirm_items(self, identity, request):
        require_management_permission(self.context, "batch:confirm")
        require_management_permission(self.context, "document:write")
        require_management_permission(self.context, "upload:attach")
        with self.sessions() as s, s.begin():
            # Canonical document owner uses the same lock order for taxonomy references.
            s.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "kb01:taxonomy-mutations:" + self.tenant},
            )
            row = self._get(s, identity, True)
            idem, cached = self.management._key(
                s,
                "BATCH_CONFIRM",
                request.idempotency_key,
                {"batch_id": row.batch_id, "request": request.model_dump(mode="json")},
            )
            if cached is not None:
                return cached
            self._cas(row, request.expected_record_version)
            if row.status != "PREVIEW":
                raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_NOT_CONFIRMABLE")
            for mapping in sorted(request.mappings, key=lambda value: str(value.item_id)):
                item = s.scalar(
                    self._items(identity)
                    .where(Item.item_id == str(mapping.item_id))
                    .with_for_update()
                )
                if item is None or item.status != "UNMAPPED":
                    raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_ITEM_NOT_CONFIRMABLE")
                upload = self.uploads._get(s, item.upload_session_id, True)
                if upload.status != "VERIFIED":
                    raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_UPLOAD_NOT_VERIFIED")
                document = mapping.document.model_copy(
                    update={"idempotency_key": "batch:" + row.batch_id + ":" + item.item_id}
                )
                created = self.documents.create_in_session(s, document)
                attach_idem, attached = self.management._key(
                    s,
                    "UPLOAD_ATTACH",
                    "batch:" + row.batch_id + ":" + item.item_id,
                    {
                        "upload_session_id": upload.upload_session_id,
                        "knowledge_version_id": created["knowledge_version_id"],
                        "expected_record_version": created["record_version"],
                    },
                )
                if attached is None:
                    self.uploads.attach_in_session(
                        s,
                        upload.upload_session_id,
                        created["knowledge_version_id"],
                        created["record_version"],
                        attach_idem,
                    )
                item.knowledge_version_id = created["knowledge_version_id"]
                item.proposed_metadata_json = {}  # Canonical version owns the confirmed metadata.
                item.status = "READY"
                item.record_version += 1
            s.flush()
            remaining = s.scalar(
                select(func.count()).select_from(
                    self._items(identity).where(Item.status == "UNMAPPED").subquery()
                )
            )
            if not remaining:
                row.status = "CONFIRMED"
            row.record_version += 1
            return self._audit(
                s, "BATCH_CONFIRM", row, idem, "User confirmed canonical draft mapping"
            )

    def cancel(self, identity, request):
        require_management_permission(self.context, "batch:cancel")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            idem, cached = self.management._key(
                s,
                "BATCH_CANCEL",
                request.idempotency_key,
                {"batch_id": row.batch_id, "request": request.model_dump(mode="json")},
            )
            if cached is not None:
                return cached
            self._cas(row, request.expected_record_version)
            if row.status not in {"PENDING", "EXTRACTING", "PREVIEW", "FAILED"}:
                raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_NOT_CANCELLABLE")
            if s.scalar(
                select(func.count()).select_from(
                    self._items(identity).where(Item.knowledge_version_id.is_not(None)).subquery()
                )
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_HAS_CANONICAL_DRAFTS")
            row.status, row.lease_token, row.lease_expires_at = "CANCELLED", None, None
            row.record_version += 1
            for item in s.scalars(self._items(identity).with_for_update()):
                item.status = "CANCELLED"
                item.record_version += 1
            return self._audit(
                s,
                "BATCH_CANCEL",
                row,
                idem,
                "Cancel import work; immutable uploaded originals remain separately managed",
            )

    def retry(self, identity, request):
        require_management_permission(self.context, "batch:retry")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            idem, cached = self.management._key(
                s,
                "BATCH_RETRY",
                request.idempotency_key,
                {"batch_id": row.batch_id, "request": request.model_dump(mode="json")},
            )
            if cached is not None:
                return cached
            self._cas(row, request.expected_record_version)
            if (
                row.status != "FAILED"
                or row.error_code != "IMPORT_TRANSPORT_UNAVAILABLE"
                or row.attempts >= 3
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_NOT_RETRYABLE")
            row.status, row.error_code = "PENDING", None
            row.record_version += 1
            return self._audit(
                s, "BATCH_RETRY", row, idem, "Retry bounded technical transport failure"
            )
