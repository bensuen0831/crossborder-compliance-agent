"""Durable immutable catalogue proposals; existing batch/document owners retain authority."""

import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import func, select

from crossborder_compliance.application.knowledge_manifest import (
    ManifestError,
    ManifestPolicy,
    preview_manifest,
)
from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.domain.knowledge_upload import MANIFEST_FORMATS
from crossborder_compliance.infrastructure.knowledge_manifest_parser import NativeManifestParser
from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
    PostgresKnowledgeImportBatches,
)
from crossborder_compliance.infrastructure.persistence.knowledge_manifest_models import (
    KnowledgeImportManifestEntity as Manifest,
)
from crossborder_compliance.infrastructure.persistence.knowledge_manifest_models import (
    KnowledgeManifestRecordEntity as Record,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementCapabilityError,
    KnowledgeManagementConflict,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeBatchItemEntity as Item,
)

DIMENSION_KIND = {
    "language": "LANGUAGE",
    "category": "REGULATION_CATEGORY",
    "jurisdiction": "JURISDICTION_CONFIG",
    "topic": "RESEARCH_TOPIC",
    "issuer": "ISSUING_AUTHORITY",
}


class PostgresKnowledgeManifestImports:
    def __init__(self, sessions, context, *, storage=None, working_root=None, parser=None):
        self.sessions, self.context = sessions, context
        self.tenant = str(context.tenant_id)
        self.batches = PostgresKnowledgeImportBatches(sessions, context)
        self.storage, self.working_root = storage, Path(working_root) if working_root else None
        self.parser = parser or NativeManifestParser()

    @staticmethod
    def _view(row):
        return {
            "manifest_id": row.manifest_id,
            "batch_id": row.batch_id,
            "upload_session_id": row.upload_session_id,
            "inventory_digest": row.inventory_digest,
            "content_sha256": row.content_sha256,
            "status": row.status,
            "error_code": row.error_code,
            "record_count": row.record_count,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat(),
        }

    @staticmethod
    def _record_view(row):
        return {
            "manifest_record_id": row.manifest_record_id,
            "row_number": row.row_number,
            "canonical_path": row.canonical_path,
            "matched_item_id": row.matched_item_id,
            "status": row.status,
            "proposed_values": row.proposed_values_json,
            "metadata_refs": row.metadata_refs_json,
            "issues": row.issues_json,
        }

    def _get(self, s, batch_id, identity):
        self.batches._get(s, batch_id)
        row = s.scalar(
            select(Manifest).where(
                Manifest.tenant_id == self.tenant,
                Manifest.batch_id == str(batch_id),
                Manifest.manifest_id == str(identity),
            )
        )
        if row is None:
            raise LookupError("manifest not found")
        return row

    def _records(self, identity):
        return select(Record).where(
            Record.tenant_id == self.tenant, Record.manifest_id == str(identity)
        )

    def _input(self, upload, limits):
        if self.storage is None or self.working_root is None:
            raise KnowledgeManagementCapabilityError("KNOWLEDGE_MANIFEST_STORAGE_NOT_CONFIGURED")
        self.working_root.mkdir(parents=True, exist_ok=True)
        if upload.declared_bytes > limits.max_bytes:
            raise ManifestError("MANIFEST_SIZE_EXCEEDED")
        if shutil.disk_usage(self.working_root).free < upload.declared_bytes + 64 * 1024**2:
            raise ManifestError("MANIFEST_DISK_BUDGET_EXHAUSTED")
        with tempfile.TemporaryDirectory(prefix="manifest-", dir=self.working_root) as directory:
            path = Path(directory) / "original"
            measured = self.storage.download(
                upload.object_key, upload.object_version, path, upload.declared_bytes
            )
            if (
                measured["content_sha256"] != upload.content_sha256
                or measured["byte_size"] != upload.declared_bytes
            ):
                raise ManifestError("MANIFEST_ORIGINAL_DIGEST_MISMATCH")
            with path.open("rb") as stream:
                content = stream.read(limits.max_bytes + 1)
            if (
                len(content) != upload.declared_bytes
                or hashlib.sha256(content).hexdigest() != upload.content_sha256
            ):
                raise ManifestError("MANIFEST_ORIGINAL_DIGEST_MISMATCH")
            return content

    def prepare(self, batch_id, request):
        for grant in ("batch:manifest-import", "batch:read", "upload:read"):
            require_management_permission(self.context, grant)
        if request.metadata_mappings:
            require_management_permission(self.context, "taxonomy:read")
        with self.sessions() as s, s.begin():
            batch = self.batches._get(s, batch_id, True)
            idem, cached = self.batches.management._key(
                s,
                "MANIFEST_IMPORT",
                request.idempotency_key,
                {"batch_id": str(batch_id), "request": request.model_dump(mode="json")},
            )
            if cached is not None:
                return cached
            self.batches._cas(batch, request.expected_record_version)
            if batch.status != "PREVIEW" or not batch.manifest_digest:
                raise KnowledgeManagementConflict("KNOWLEDGE_BATCH_NOT_CONFIRMABLE")
            upload = self.batches.uploads._get(s, request.upload_session_id, True)
            if (
                upload.status != "VERIFIED"
                or upload.declared_format not in MANIFEST_FORMATS
                or upload.knowledge_version_id
            ):
                raise KnowledgeManagementConflict("KNOWLEDGE_MANIFEST_VERIFIED_ORIGINAL_REQUIRED")
            root, version, policy = self.batches.uploads._policy(s)
            inventory = s.scalars(self.batches._items(batch_id).order_by(Item.relative_path)).all()
            if len(inventory) > policy.max_archive_entries:
                raise ManifestError("MANIFEST_INVENTORY_LIMIT")
            labels, pinned = {}, {}
            for mapping in request.metadata_mappings:
                if any(label.kind != DIMENSION_KIND[mapping.dimension] for label in mapping.labels):
                    raise ValueError("MANIFEST_METADATA_DIMENSION_MISMATCH")
                self.batches.documents.validated_label_pins(s, mapping.labels)
                labels.setdefault(mapping.dimension, {})[mapping.source_value] = tuple(
                    str(label.definition_id) for label in mapping.labels
                )
                pinned[(mapping.dimension, mapping.source_value)] = [
                    label.model_dump(mode="json") for label in mapping.labels
                ]
            limits = policy.manifest
            parsing_policy = ManifestPolicy(
                columns=request.columns,
                metadata=labels,
                required_fields=request.required_fields,
                sheet_name=request.sheet_name,
                csv_encoding=request.csv_encoding,
                **limits.model_dump(),
            )
            manifest = Manifest(
                manifest_id=str(uuid4()),
                tenant_id=self.tenant,
                batch_id=batch.batch_id,
                upload_session_id=upload.upload_session_id,
                idempotency_key=request.idempotency_key,
                request_digest=hashlib.sha256(
                    json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
                ).hexdigest(),
                inventory_digest=batch.manifest_digest,
                content_sha256=upload.content_sha256,
                status="COMPLETED",
                record_count=0,
                created_by=self.context.permission.actor_id,
                created_at=datetime.now(UTC),
                mapping_json={
                    "columns": request.columns,
                    "required_fields": list(request.required_fields),
                    "metadata_mappings": [
                        v.model_dump(mode="json") for v in request.metadata_mappings
                    ],
                    "sheet_name": request.sheet_name,
                    "csv_encoding": request.csv_encoding,
                    "policy_definition_id": root.definition_id,
                    "policy_version_id": version.version_id,
                    "limits": limits.model_dump(),
                    "original_object_version": upload.object_version,
                },
            )
            try:
                content = self._input(upload, limits)
                preview = preview_manifest(
                    content,
                    kind=upload.declared_format,
                    policy=parsing_policy,
                    parser=self.parser,
                    source_paths=tuple(item.relative_path for item in inventory),
                )
                if preview.content_sha256 != upload.content_sha256:
                    raise ManifestError("MANIFEST_ORIGINAL_DIGEST_MISMATCH")
                if any(
                    any(len(value) > 4096 for _, value in row.values) for row in preview.records
                ):
                    raise ManifestError("MANIFEST_FIELD_VALUE_LIMIT")
                if any(
                    row.canonical_path and len(row.canonical_path) > 1024 for row in preview.records
                ):
                    raise ManifestError("MANIFEST_PATH_LENGTH_LIMIT")
            except ManifestError as exc:
                manifest.status, manifest.error_code = "FAILED", str(exc)
                preview = None
            manifest.record_count = len(preview.records) if preview is not None else 0
            s.add(manifest)
            s.flush()
            if preview is not None:
                from crossborder_compliance.application.knowledge_manifest import (
                    normalize_relative_path,
                )

                by_path = {
                    normalize_relative_path(
                        item.relative_path, case_sensitive=limits.case_sensitive_paths
                    ): item
                    for item in inventory
                }
                for record in preview.records:
                    values = dict(record.values)
                    item = by_path.get(record.canonical_path)
                    s.add(
                        Record(
                            manifest_record_id=str(uuid4()),
                            tenant_id=self.tenant,
                            batch_id=batch.batch_id,
                            manifest_id=manifest.manifest_id,
                            row_number=record.row,
                            canonical_path=record.canonical_path,
                            matched_item_id=item.item_id if item is not None else None,
                            status=record.status,
                            proposed_values_json=values,
                            metadata_refs_json={
                                dimension: pinned[(dimension, values[dimension])]
                                for dimension, _ in record.metadata_refs
                            },
                            issues_json=[asdict(issue) for issue in record.issues],
                        )
                    )
            result = self._view(manifest)
            return self.batches.management._audit(
                s,
                "MANIFEST_IMPORT",
                SimpleNamespace(
                    kind="KNOWLEDGE_IMPORT_MANIFEST", definition_id=manifest.manifest_id
                ),
                "User requested immutable catalogue proposal preview",
                idem,
                result,
            )

    @staticmethod
    def _pagination(page, page_size):
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("INVALID_PAGINATION")

    def list(self, batch_id, *, page=1, page_size=25):
        for grant in ("batch:read", "batch:manifest-read"):
            require_management_permission(self.context, grant)
        self._pagination(page, page_size)
        with self.sessions() as s:
            self.batches._get(s, batch_id)
            query = select(Manifest).where(
                Manifest.tenant_id == self.tenant, Manifest.batch_id == str(batch_id)
            )
            total = s.scalar(select(func.count()).select_from(query.subquery()))
            rows = s.scalars(
                query.order_by(Manifest.created_at, Manifest.manifest_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [self._view(row) for row in rows],
            }

    def detail(self, batch_id, manifest_id, *, page=1, page_size=25):
        for grant in ("batch:read", "batch:manifest-read"):
            require_management_permission(self.context, grant)
        self._pagination(page, page_size)
        with self.sessions() as s:
            manifest = self._get(s, batch_id, manifest_id)
            rows = s.scalars(
                self._records(manifest_id)
                .order_by(Record.row_number)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                **self._view(manifest),
                "total": manifest.record_count,
                "page": page,
                "page_size": page_size,
                "items": [self._record_view(row) for row in rows],
            }

    def missing_files(self, batch_id, manifest_id, *, page=1, page_size=100):
        for grant in ("batch:read", "batch:manifest-read", "batch:manifest-export"):
            require_management_permission(self.context, grant)
        self._pagination(page, page_size)
        with self.sessions() as s:
            self._get(s, batch_id, manifest_id)
            query = self._records(manifest_id).where(Record.status != "FILE_MATCHED")
            total = s.scalar(select(func.count()).select_from(query.subquery()))
            rows = s.scalars(
                query.order_by(Record.row_number).offset((page - 1) * page_size).limit(page_size)
            ).all()
            unlisted = self.batches._items(batch_id).where(
                ~select(Record.manifest_record_id)
                .where(
                    Record.tenant_id == self.tenant,
                    Record.manifest_id == str(manifest_id),
                    Record.matched_item_id == Item.item_id,
                )
                .exists()
            )
            missing_count = s.scalar(select(func.count()).select_from(unlisted.subquery()))
            files = s.scalars(
                unlisted.order_by(Item.relative_path)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "manifest_id": str(manifest_id),
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [self._record_view(row) for row in rows],
                "unlisted_total": missing_count,
                "unlisted_files": [
                    {"item_id": row.item_id, "relative_path": row.relative_path} for row in files
                ],
            }
