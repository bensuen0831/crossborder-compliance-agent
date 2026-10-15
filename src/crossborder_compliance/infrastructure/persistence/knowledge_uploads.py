"""Tenant/CAS/idempotency owner for durable knowledge binary transport receipts."""

import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import func, select, text

from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
    PostgresKnowledgeTaxonomyRepository,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeBinaryAttachmentEntity as Attachment,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeUploadPartEntity as Part,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeUploadSessionEntity as Upload,
)


class PostgresKnowledgeUploads:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant = str(context.tenant_id)
        self.actor = context.permission.actor_id
        self.management = PostgresKnowledgeTaxonomyRepository(sessions, context)
        self.owner = PostgresKnowledgeRepository(sessions, context)

    def _get(self, s, identity, lock=False):
        q = select(Upload).where(
            Upload.tenant_id == self.tenant, Upload.upload_session_id == str(identity)
        )
        row = s.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise LookupError("upload not found")
        return row

    def _target(self, s, identity, expected):
        row = self.owner.get(s, k.KnowledgeDocumentVersionEntity, str(identity))
        self.owner.get(s, k.KnowledgeDocumentEntity, row.document_id, True)
        row = s.scalar(
            select(k.KnowledgeDocumentVersionEntity)
            .where(
                k.KnowledgeDocumentVersionEntity.tenant_id == self.tenant,
                k.KnowledgeDocumentVersionEntity.knowledge_version_id == str(identity),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row.record_version != expected:
            raise KnowledgeManagementConflict("KNOWLEDGE_VERSION_CONFLICT")
        if row.lifecycle != "DRAFT" or row.original_artifact_ref:
            raise KnowledgeManagementConflict("KNOWLEDGE_ORIGINAL_ALREADY_FROZEN")
        return row

    def _policy(self, s):
        roots = s.scalars(
            select(m.MetadataDefinitionEntity)
            .where(
                m.MetadataDefinitionEntity.tenant_id == self.tenant,
                m.MetadataDefinitionEntity.kind == "KNOWLEDGE_MANAGEMENT_POLICY",
                m.MetadataDefinitionEntity.status == "ACTIVE",
                m.MetadataDefinitionEntity.active_version_id.is_not(None),
            )
            .order_by(m.MetadataDefinitionEntity.definition_id)
            .with_for_update()
        ).all()
        policy = self.management._retention_policy(s)
        if len(roots) != 1:
            raise KnowledgeManagementConflict("KNOWLEDGE_MANAGEMENT_POLICY_AMBIGUOUS")
        version = s.scalar(
            select(m.MetadataVersionEntity)
            .where(
                m.MetadataVersionEntity.tenant_id == self.tenant,
                m.MetadataVersionEntity.version_id == roots[0].active_version_id,
            )
            .with_for_update()
        )
        return roots[0], version, policy

    def policy_view(self):
        require_management_permission(self.context, "upload:read")
        from crossborder_compliance.domain.knowledge_upload import ARCHIVE_FORMATS, DOCUMENT_FORMATS

        with self.sessions() as s, s.begin():
            root, version, policy = self._policy(s)
            return {
                "policy_definition_id": root.definition_id,
                "policy_version_id": version.version_id,
                "max_single_bytes": policy.max_single_bytes,
                "max_archive_bytes": policy.max_archive_bytes,
                "max_expanded_bytes": policy.max_expanded_bytes,
                "max_archive_entries": policy.max_archive_entries,
                "multipart_chunk_bytes": policy.multipart_chunk_bytes,
                "upload_expiry_seconds": policy.upload_expiry_seconds,
                "tenant_storage_quota_bytes": policy.tenant_storage_quota_bytes,
                "max_active_upload_sessions": policy.max_active_upload_sessions,
                "scan_required": policy.scan_required,
                "allowed_document_formats": sorted(DOCUMENT_FORMATS),
                "allowed_archive_formats": sorted(ARCHIVE_FORMATS),
            }

    @staticmethod
    def _view(row):
        return {
            "upload_session_id": row.upload_session_id,
            "knowledge_version_id": row.knowledge_version_id,
            "relative_path": row.relative_path,
            "declared_format": row.declared_format,
            "declared_bytes": row.declared_bytes,
            "content_sha256": row.content_sha256,
            "part_bytes": row.part_bytes,
            "part_count": math.ceil(row.declared_bytes / row.part_bytes),
            "status": row.status,
            "record_version": row.record_version,
            "expires_at": row.expires_at.isoformat(),
            "created_by": row.created_by,
            "attempts": row.attempts,
            "error_code": row.error_code,
            "scan": {
                key: value
                for key, value in row.scan_json.items()
                if key in {"byte_size", "content_sha256", "detected_format", "scanner"}
            },
        }

    def _audit(self, s, operation, row, idem, reason):
        return self.management._audit(
            s,
            operation,
            SimpleNamespace(kind="KNOWLEDGE_UPLOAD", definition_id=row.upload_session_id),
            reason,
            idem,
            self._view(row),
        )

    @staticmethod
    def _cas(row, expected):
        if row.record_version != expected:
            raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_VERSION_CONFLICT")

    @staticmethod
    def _writable(row):
        if row.status != "UPLOADING" or row.expires_at <= datetime.now(UTC):
            raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_NOT_WRITABLE")

    def start(self, request):
        require_management_permission(self.context, "upload:create")
        if request.knowledge_version_id:
            require_management_permission(self.context, "document:write")
        with self.sessions() as s, s.begin():
            idem, cached = self.management._key(
                s, "UPLOAD_CREATE", request.idempotency_key, request.model_dump(mode="json")
            )
            if cached is not None:
                return self._view(self._get(s, cached["upload_session_id"]))
            root, version, policy = self._policy(s)
            ceiling = (
                policy.max_archive_bytes
                if request.declared_format in {"RAR", "ZIP"}
                else policy.max_single_bytes
            )
            if request.declared_bytes > ceiling:
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_SIZE_LIMIT")
            if math.ceil(request.declared_bytes / policy.multipart_chunk_bytes) > 10000:
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_PART_COUNT_LIMIT")
            s.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "kb01:upload-quota:" + self.tenant},
            )
            reserved = s.scalar(
                select(func.coalesce(func.sum(Upload.declared_bytes), 0)).where(
                    Upload.tenant_id == self.tenant, Upload.status.not_in(("CANCELLED", "EXPIRED"))
                )
            )
            active = s.scalar(
                select(func.count())
                .select_from(Upload)
                .where(
                    Upload.tenant_id == self.tenant,
                    Upload.status.in_(
                        ("CREATING", "UPLOADING", "FINALIZING", "QUEUED_SCAN", "SCANNING")
                    ),
                )
            )
            if (
                reserved + request.declared_bytes > policy.tenant_storage_quota_bytes
                or active >= policy.max_active_upload_sessions
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_STORAGE_QUOTA_EXCEEDED")
            if request.knowledge_version_id:
                self._target(s, request.knowledge_version_id, request.expected_record_version)
            identity = str(uuid4())
            row = Upload(
                upload_session_id=identity,
                tenant_id=self.tenant,
                created_by=self.actor,
                knowledge_version_id=str(request.knowledge_version_id)
                if request.knowledge_version_id
                else None,
                expected_knowledge_record_version=request.expected_record_version,
                relative_path=request.relative_path,
                declared_format=request.declared_format,
                declared_bytes=request.declared_bytes,
                content_sha256=request.content_sha256,
                part_bytes=policy.multipart_chunk_bytes,
                policy_definition_id=root.definition_id,
                policy_version_id=version.version_id,
                policy_json=policy.model_dump(mode="json"),
                object_key=f"knowledge-upload/{self.tenant}/{identity}/original",
                expires_at=datetime.now(UTC) + timedelta(seconds=policy.upload_expiry_seconds),
                status="CREATING",
                scan_json={},
            )
            s.add(row)
            s.flush()
            return self._audit(s, "UPLOAD_CREATE", row, idem, "Local binary upload declared")

    def detail(self, identity):
        require_management_permission(self.context, "upload:read")
        with self.sessions() as s:
            row = self._get(s, identity)
            parts = s.scalars(
                select(Part)
                .where(
                    Part.tenant_id == self.tenant,
                    Part.upload_session_id == row.upload_session_id,
                )
                .order_by(Part.part_number)
            ).all()
            return {
                **self._view(row),
                "received_parts": [
                    {
                        "part_number": p.part_number,
                        "byte_size": p.byte_size,
                        "content_sha256": p.content_sha256,
                    }
                    for p in parts
                ],
                "received_bytes": sum(p.byte_size for p in parts),
            }

    def initialize_claim(self, identity):
        require_management_permission(self.context, "upload:create")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            if row.status != "CREATING":
                return None
            now = datetime.now(UTC)
            if row.lease_expires_at and row.lease_expires_at > now:
                return None
            row.lease_token = str(uuid4())
            row.lease_expires_at = now + timedelta(minutes=5)
            row.record_version += 1
            return {"object_key": row.object_key, "lease_token": row.lease_token}

    def initialized(self, identity, token, multipart_id):
        require_management_permission(self.context, "upload:create")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            if row.status != "CREATING" or row.lease_token != token:
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_LEASE_LOST")
            row.multipart_id = multipart_id
            row.status = "UPLOADING"
            row.lease_token = row.lease_expires_at = None
            row.record_version += 1
            return self._view(row)

    def transport(self, identity, operation="upload:write"):
        require_management_permission(self.context, operation)
        with self.sessions() as s:
            row = self._get(s, identity)
            return {
                **self._view(row),
                "object_key": row.object_key,
                "multipart_id": row.multipart_id,
                "object_version": row.object_version,
                "policy": row.policy_json,
            }

    def part_request(self, identity, request):
        require_management_permission(self.context, "upload:write")
        with self.sessions() as s:
            row = self._get(s, identity)
            self._writable(row)
            count = math.ceil(row.declared_bytes / row.part_bytes)
            if request.part_number > count:
                raise KnowledgeManagementConflict("INVALID_KNOWLEDGE_UPLOAD_PART")
            size = min(
                row.part_bytes, row.declared_bytes - (request.part_number - 1) * row.part_bytes
            )
            expiry = min(
                row.policy_json["signed_part_expiry_seconds"],
                int((row.expires_at - datetime.now(UTC)).total_seconds()),
            )
            return {
                "object_key": row.object_key,
                "multipart_id": row.multipart_id,
                "number": request.part_number,
                "size": size,
                "sha256": request.content_sha256,
                "expiry": expiry,
            }

    def acknowledge_part(self, identity, request, provider_part):
        require_management_permission(self.context, "upload:write")
        with self.sessions() as s, s.begin():
            idem, cached = self.management._key(
                s,
                "UPLOAD_PART_ACK",
                request.idempotency_key,
                {"upload_session_id": str(identity), "request": request.model_dump(mode="json")},
            )
            if cached is not None:
                return cached
            row = self._get(s, identity, True)
            self._cas(row, request.expected_record_version)
            self._writable(row)
            expected = min(
                row.part_bytes, row.declared_bytes - (request.part_number - 1) * row.part_bytes
            )
            if (
                expected <= 0
                or not provider_part
                or provider_part["number"] != request.part_number
                or provider_part["byte_size"] != expected
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_PART_NOT_PRESENT")
            old = s.get(Part, (self.tenant, row.upload_session_id, request.part_number))
            if old:
                if (
                    old.content_sha256 != request.content_sha256
                    or old.etag != provider_part["etag"]
                ):
                    raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_PART_RECEIPT_CONFLICT")
            else:
                s.add(
                    Part(
                        tenant_id=self.tenant,
                        upload_session_id=row.upload_session_id,
                        part_number=request.part_number,
                        byte_size=expected,
                        content_sha256=request.content_sha256,
                        etag=provider_part["etag"],
                        received_at=datetime.now(UTC),
                    )
                )
            row.record_version += 1
            return self._audit(s, "UPLOAD_PART_ACK", row, idem, "Provider part receipt recorded")

    def complete_intent(self, identity, request, provider_parts):
        require_management_permission(self.context, "upload:complete")
        with self.sessions() as s, s.begin():
            idem, cached = self.management._key(
                s,
                "UPLOAD_COMPLETE",
                request.idempotency_key,
                {"upload_session_id": str(identity), "request": request.model_dump(mode="json")},
            )
            row = self._get(s, identity, True)
            if cached is not None:
                return self._view(row)
            self._cas(row, request.expected_record_version)
            self._writable(row)
            receipts = s.scalars(
                select(Part)
                .where(
                    Part.tenant_id == self.tenant,
                    Part.upload_session_id == row.upload_session_id,
                )
                .order_by(Part.part_number)
            ).all()
            expected = [
                {"number": p.part_number, "byte_size": p.byte_size, "etag": p.etag}
                for p in receipts
            ]
            if (
                len(receipts) != math.ceil(row.declared_bytes / row.part_bytes)
                or [p.part_number for p in receipts] != list(range(1, len(receipts) + 1))
                or expected != sorted(provider_parts, key=lambda p: p["number"])
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_INCOMPLETE_OR_CHANGED")
            row.status = "FINALIZING"
            row.record_version += 1
            return self._audit(s, "UPLOAD_COMPLETE", row, idem, "Complete verified provider parts")

    def completed(self, identity, provider_head):
        require_management_permission(self.context, "upload:complete")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            if row.status != "FINALIZING":
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_COMPLETION_STATE_CHANGED")
            if provider_head["byte_size"] != row.declared_bytes:
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_SIZE_MISMATCH")
            row.object_version = provider_head["object_version"]
            row.status = "QUEUED_SCAN"
            row.record_version += 1
            return self._view(row)

    def completion_parts(self, identity):
        require_management_permission(self.context, "upload:complete")
        with self.sessions() as s:
            row = self._get(s, identity)
            if row.status != "FINALIZING":
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_COMPLETION_STATE_CHANGED")
            return [
                {"number": p.part_number, "byte_size": p.byte_size, "etag": p.etag}
                for p in s.scalars(
                    select(Part)
                    .where(
                        Part.tenant_id == self.tenant,
                        Part.upload_session_id == row.upload_session_id,
                    )
                    .order_by(Part.part_number)
                )
            ]

    def verification_parts(self, identity):
        require_management_permission(self.context, "upload:work")
        with self.sessions() as s:
            row = self._get(s, identity)
            return [
                {
                    "number": p.part_number,
                    "byte_size": p.byte_size,
                    "content_sha256": p.content_sha256,
                }
                for p in s.scalars(
                    select(Part)
                    .where(
                        Part.tenant_id == self.tenant,
                        Part.upload_session_id == row.upload_session_id,
                    )
                    .order_by(Part.part_number)
                )
            ]

    def cancel_intent(self, identity, request):
        require_management_permission(self.context, "upload:cancel")
        with self.sessions() as s, s.begin():
            idem, cached = self.management._key(
                s,
                "UPLOAD_CANCEL",
                request.idempotency_key,
                {"upload_session_id": str(identity), "request": request.model_dump(mode="json")},
            )
            row = self._get(s, identity, True)
            if cached is not None:
                return self._view(row)
            self._cas(row, request.expected_record_version)
            if row.status not in {
                "CREATING",
                "UPLOADING",
                "QUEUED_SCAN",
                "SCANNING",
                "FAILED",
            } or s.scalar(
                select(Attachment).where(
                    Attachment.tenant_id == self.tenant,
                    Attachment.upload_session_id == row.upload_session_id,
                )
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_CANCEL_NOT_ALLOWED")
            row.status = "CANCELLING"
            row.record_version += 1
            return self._audit(s, "UPLOAD_CANCEL", row, idem, "Cancel unconsumed binary transport")

    def cancelled(self, identity):
        require_management_permission(self.context, "upload:cancel")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            if row.status not in {"CANCELLING", "CANCELLED"}:
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_CANCEL_STATE_CHANGED")
            if row.status != "CANCELLED":
                row.status = "CANCELLED"
                row.record_version += 1
            return self._view(row)

    def retry_scan(self, identity, request):
        require_management_permission(self.context, "upload:retry")
        with self.sessions() as s, s.begin():
            idem, cached = self.management._key(
                s,
                "UPLOAD_RETRY",
                request.idempotency_key,
                {"upload_session_id": str(identity), "request": request.model_dump(mode="json")},
            )
            row = self._get(s, identity, True)
            if cached is not None:
                return self._view(row)
            self._cas(row, request.expected_record_version)
            if (
                row.status != "FAILED"
                or not row.object_version
                or row.attempts >= 3
                or row.error_code not in {"SCANNER_UNAVAILABLE", "SCANNER_TIMEOUT"}
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_RETRY_NOT_ALLOWED")
            row.status = "QUEUED_SCAN"
            row.error_code = None
            row.record_version += 1
            return self._audit(s, "UPLOAD_RETRY", row, idem, "Retry bounded scanner work")

    def scan_claim(self):
        require_management_permission(self.context, "upload:work")
        with self.sessions() as s, s.begin():
            now = datetime.now(UTC)
            exhausted = s.scalar(
                select(Upload)
                .where(
                    Upload.tenant_id == self.tenant,
                    Upload.status == "SCANNING",
                    Upload.lease_expires_at <= now,
                    Upload.attempts >= 3,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if exhausted is not None:
                token = exhausted.lease_token
                exhausted.status, exhausted.error_code = "FAILED", "SCANNER_TIMEOUT"
                exhausted.lease_token = exhausted.lease_expires_at = None
                exhausted.record_version += 1
                idem, cached = self.management._key(
                    s,
                    "UPLOAD_SCAN_RESULT",
                    "scan-expired:" + token,
                    {
                        "upload_session_id": exhausted.upload_session_id,
                        "error_code": "SCANNER_TIMEOUT",
                    },
                )
                if cached is None:
                    self._audit(
                        s, "UPLOAD_SCAN_RESULT", exhausted, idem, "Final scanner lease expired"
                    )
            row = s.scalar(
                select(Upload)
                .where(
                    Upload.tenant_id == self.tenant,
                    (Upload.status == "QUEUED_SCAN")
                    | ((Upload.status == "SCANNING") & (Upload.lease_expires_at < now)),
                    Upload.attempts < 3,
                )
                .order_by(Upload.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            row.status = "SCANNING"
            row.attempts += 1
            row.record_version += 1
            row.lease_token = str(uuid4())
            row.lease_expires_at = now + timedelta(
                seconds=row.policy_json["scanner_timeout_seconds"] + 300
            )
            return {
                **self._view(row),
                "object_key": row.object_key,
                "object_version": row.object_version,
                "lease_token": row.lease_token,
                "policy": row.policy_json,
            }

    def scan_result(self, identity, token, scan, error_code=None):
        require_management_permission(self.context, "upload:work")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            if row.status in {"CANCELLING", "CANCELLED"}:
                return self._view(row)
            if row.status != "SCANNING" or row.lease_token != token:
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_LEASE_LOST")
            if error_code not in {
                None,
                "MALWARE_DETECTED",
                "BINARY_VERIFICATION_FAILED",
                "SCANNER_UNAVAILABLE",
                "SCANNER_TIMEOUT",
                "UNSUPPORTED_BINARY_FORMAT",
                "SCANNER_LIMIT_EXCEEDED",
                "ENCRYPTED_BINARY_UNSUPPORTED",
            }:
                raise ValueError("INVALID_SCAN_ERROR_CODE")
            if error_code is None and (
                not row.object_version
                or scan.get("content_sha256") != row.content_sha256
                or scan.get("byte_size") != row.declared_bytes
                or scan.get("detected_format") != row.declared_format
                or scan.get("scanner", {}).get("clean") is not True
            ):
                raise ValueError("INVALID_VERIFIED_SCAN_RECEIPT")
            row.status = (
                "QUARANTINED"
                if error_code == "MALWARE_DETECTED"
                else "FAILED"
                if error_code
                else "VERIFIED"
            )
            row.error_code = error_code
            row.scan_json = scan
            row.record_version += 1
            row.lease_token = row.lease_expires_at = None
            idem, _ = self.management._key(
                s,
                "UPLOAD_SCAN_RESULT",
                "scan:" + token,
                {"upload_session_id": str(identity), "scan": scan, "error_code": error_code},
            )
            return self._audit(s, "UPLOAD_SCAN_RESULT", row, idem, "Isolated binary verification")

    def cleanup_claim(self):
        """Reserve cancellation/expiry cleanup without releasing quota before S3 cleanup."""
        require_management_permission(self.context, "upload:work")
        with self.sessions() as s, s.begin():
            now = datetime.now(UTC)
            row = s.scalar(
                select(Upload)
                .where(
                    Upload.tenant_id == self.tenant,
                    (
                        (Upload.status == "CANCELLING")
                        & ((Upload.lease_expires_at.is_(None)) | (Upload.lease_expires_at <= now))
                    )
                    | ((Upload.status.in_(("CREATING", "UPLOADING"))) & (Upload.expires_at <= now)),
                )
                .order_by(Upload.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            if row.status != "CANCELLING":
                row.error_code = "UPLOAD_EXPIRED"
            row.status, row.lease_token = "CANCELLING", str(uuid4())
            row.lease_expires_at = now + timedelta(minutes=5)
            row.record_version += 1
            return {
                "upload_session_id": row.upload_session_id,
                "object_key": row.object_key,
                "multipart_id": row.multipart_id,
                "object_version": row.object_version,
                "lease_token": row.lease_token,
            }

    def cleanup_finished(self, identity, token):
        require_management_permission(self.context, "upload:work")
        with self.sessions() as s, s.begin():
            row = self._get(s, identity, True)
            if row.status in {"CANCELLED", "EXPIRED"}:
                return self._view(row)
            if row.status != "CANCELLING" or row.lease_token != token:
                raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_LEASE_LOST")
            row.status = "EXPIRED" if row.error_code == "UPLOAD_EXPIRED" else "CANCELLED"
            row.lease_token = row.lease_expires_at = None
            row.record_version += 1
            idem, cached = self.management._key(
                s,
                "UPLOAD_CANCEL",
                "cleanup:" + token,
                {"upload_session_id": row.upload_session_id, "status": row.status},
            )
            return cached or self._audit(
                s, "UPLOAD_CANCEL", row, idem, "Owned provider cleanup completed"
            )

    def attach(self, identity, version_id, expected, key):
        require_management_permission(self.context, "upload:attach")
        require_management_permission(self.context, "document:write")
        with self.sessions() as s, s.begin():
            idem, cached = self.management._key(
                s,
                "UPLOAD_ATTACH",
                key,
                {
                    "upload_session_id": str(identity),
                    "knowledge_version_id": str(version_id),
                    "expected_record_version": expected,
                },
            )
            if cached is not None:
                return cached
            return self.attach_in_session(s, identity, version_id, expected, idem)

    def attach_in_session(self, s, identity, version_id, expected, idem):
        """Reuse exact attachment owner inside an atomic batch mapping transaction."""
        require_management_permission(self.context, "upload:attach")
        require_management_permission(self.context, "document:write")
        version = self._target(s, version_id, expected)
        row = self._get(s, identity, True)
        if row.status != "VERIFIED" or row.declared_format in {"RAR", "ZIP"}:
            raise KnowledgeManagementConflict("KNOWLEDGE_BINARY_NOT_ATTACHABLE")
        if row.knowledge_version_id and row.knowledge_version_id != str(version_id):
            raise KnowledgeManagementConflict("KNOWLEDGE_UPLOAD_TARGET_MISMATCH")
        if s.scalar(
            select(Attachment).where(
                Attachment.tenant_id == self.tenant,
                Attachment.upload_session_id == row.upload_session_id,
            )
        ):
            raise KnowledgeManagementConflict("KNOWLEDGE_BINARY_ALREADY_ATTACHED")
        s.add(
            Attachment(
                tenant_id=self.tenant,
                knowledge_version_id=str(version_id),
                upload_session_id=row.upload_session_id,
                attached_by=self.actor,
                attached_at=datetime.now(UTC),
            )
        )
        # This pointer remains the existing version's original-artifact authority.
        version.original_artifact_ref = "s3://" + row.scan_json["bucket"] + "/" + row.object_key
        version.content_hash = row.content_sha256
        version.provenance_json = {**version.provenance_json, "kb01_binary_transport": True}
        version.record_version += 1
        row.knowledge_version_id = str(version_id)
        row.record_version += 1
        return self._audit(s, "UPLOAD_ATTACH", row, idem, "Attach verified immutable original")
