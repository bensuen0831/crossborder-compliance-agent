"""Administrative channel composition over the existing canonical knowledge owner."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import case, delete, func, or_, select, text
from sqlalchemy.orm import aliased

from crossborder_compliance.application.knowledge_document_management import DOCUMENT_OPERATIONS
from crossborder_compliance.domain.knowledge_management import (
    KnowledgeDocumentMetadata,
    require_management_permission,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
    KnowledgeDocumentLabelEntity,
    KnowledgeManagementHoldEntity,
)
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    KnowledgeManagementConflict,
    PostgresKnowledgeTaxonomyRepository,
)


class PostgresKnowledgeDocumentManagement:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant_id = str(context.tenant_id)
        self.owner = PostgresKnowledgeRepository(sessions, context)
        self.management = PostgresKnowledgeTaxonomyRepository(sessions, context)

    def _labels(self, s, version):
        return [
            {
                "kind": row.kind,
                "definition_id": row.definition_id,
                "version_id": row.metadata_version_id,
            }
            for row in s.scalars(
                select(KnowledgeDocumentLabelEntity)
                .where(
                    KnowledgeDocumentLabelEntity.tenant_id == self.tenant_id,
                    KnowledgeDocumentLabelEntity.knowledge_version_id
                    == version.knowledge_version_id,
                )
                .order_by(
                    KnowledgeDocumentLabelEntity.kind, KnowledgeDocumentLabelEntity.definition_id
                )
            )
        ]

    def _version_view(self, s, doc, version):
        metadata = {
            **version.provenance_json.get("kb01_metadata", {"title": doc.display_name}),
            "labels": self._labels(s, version),
        }
        return {
            "knowledge_version_id": version.knowledge_version_id,
            "document_id": doc.document_id,
            "version": version.version,
            "record_version": version.record_version,
            "lifecycle": version.lifecycle,
            "language": version.language,
            "effective_from": version.effective_from.isoformat()
            if version.effective_from
            else None,
            "effective_to": version.effective_to.isoformat() if version.effective_to else None,
            "metadata": metadata,
            "content_hash": version.content_hash,
            "file_available": bool(version.original_artifact_ref),
        }

    def _view(self, s, doc):
        return {
            "document_id": doc.document_id,
            "source_id": doc.source_id,
            "display_name": doc.display_name,
            "record_version": doc.record_version,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        }

    def detail(self, identity):
        require_management_permission(self.context, "document:read")
        with self.sessions() as s:
            doc = self.owner.get(s, k.KnowledgeDocumentEntity, identity)
            versions = s.scalars(
                select(k.KnowledgeDocumentVersionEntity)
                .where(
                    k.KnowledgeDocumentVersionEntity.tenant_id == self.tenant_id,
                    k.KnowledgeDocumentVersionEntity.document_id == doc.document_id,
                )
                .order_by(k.KnowledgeDocumentVersionEntity.version.desc())
            ).all()
            return {
                **self._view(s, doc),
                "versions": [self._version_view(s, doc, v) for v in versions],
            }

    def list(
        self,
        *,
        query="",
        label_id=None,
        lifecycle=None,
        language=None,
        page=1,
        page_size=50,
        sort="updated_desc",
    ):
        require_management_permission(self.context, "document:read")
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("INVALID_PAGINATION")
        d, v, label = (
            k.KnowledgeDocumentEntity,
            k.KnowledgeDocumentVersionEntity,
            KnowledgeDocumentLabelEntity,
        )
        with self.sessions() as s:
            q = select(d).where(d.tenant_id == self.tenant_id)
            if query:
                q = q.where(d.display_name.ilike(f"%{query}%"))
            filters = [v.tenant_id == self.tenant_id, v.document_id == d.document_id]
            candidate = aliased(k.KnowledgeDocumentVersionEntity)
            selection = (
                select(candidate.knowledge_version_id)
                .where(
                    candidate.tenant_id == self.tenant_id,
                    candidate.document_id == d.document_id,
                    *([candidate.lifecycle == lifecycle] if lifecycle else []),
                )
                .order_by(
                    case((candidate.lifecycle == "ACTIVE", 0), else_=1), candidate.version.desc()
                )
                .limit(1)
                .correlate(d)
                .scalar_subquery()
            )
            filters.append(v.knowledge_version_id == selection)
            if lifecycle:
                filters.append(v.lifecycle == lifecycle)
            if language:
                filters.append(v.language == language)
            if label_id:
                filters.append(
                    select(label.label_id)
                    .where(
                        label.tenant_id == self.tenant_id,
                        label.knowledge_version_id == v.knowledge_version_id,
                        label.definition_id == str(label_id),
                    )
                    .exists()
                )
            if lifecycle or language or label_id:
                q = q.where(select(v.knowledge_version_id).where(*filters).exists())
            total = s.scalar(select(func.count()).select_from(q.subquery()))
            ordering = {
                "updated_desc": d.updated_at.desc(),
                "title_asc": d.display_name.asc(),
                "created_desc": d.created_at.desc(),
            }
            if sort not in ordering:
                raise ValueError("INVALID_DOCUMENT_SORT")
            rows = s.scalars(
                q.order_by(ordering[sort], d.document_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [self._view(s, row) for row in rows],
            }

    def _set_metadata(self, s, doc, version, metadata):
        value = KnowledgeDocumentMetadata.model_validate(metadata)
        pins = []
        for label in value.labels:
            definition = self.owner.get(s, m.MetadataDefinitionEntity, label.definition_id)
            pin = self.owner.get(s, m.MetadataVersionEntity, label.version_id)
            if (
                definition.kind != label.kind
                or pin.definition_id != definition.definition_id
                or definition.active_version_id != pin.version_id
                or pin.lifecycle_status != "ACTIVE"
                or not pin.payload_json.get("enabled", True)
            ):
                raise KnowledgeManagementConflict(
                    "DOCUMENT_CLASSIFICATION_NOT_ACTIVE_OR_MISMATCHED"
                )
            pins.append((label, pin))
        s.execute(
            delete(KnowledgeDocumentLabelEntity).where(
                KnowledgeDocumentLabelEntity.tenant_id == self.tenant_id,
                KnowledgeDocumentLabelEntity.knowledge_version_id == version.knowledge_version_id,
            )
        )
        for label, pin in pins:
            s.add(
                KnowledgeDocumentLabelEntity(
                    label_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    knowledge_version_id=version.knowledge_version_id,
                    definition_id=str(label.definition_id),
                    metadata_version_id=pin.version_id,
                    kind=label.kind,
                )
            )
        # These administrative fields are bounded metadata. Core identities
        # and exact classifications remain relational; legal scope still uses
        # the existing independently reviewed KnowledgeBinding authority.
        version.provenance_json = {
            **version.provenance_json,
            "kb01_metadata": value.model_dump(mode="json", exclude={"labels"}),
        }
        doc.display_name = value.title

    def _impact(self, s, doc):
        versions = s.scalars(
            select(k.KnowledgeDocumentVersionEntity).where(
                k.KnowledgeDocumentVersionEntity.tenant_id == self.tenant_id,
                k.KnowledgeDocumentVersionEntity.document_id == doc.document_id,
            )
        ).all()
        protected = any(
            v.lifecycle != "DRAFT" or v.review_task_id or v.approved_by for v in versions
        )
        refs = {}
        targets = {doc.document_id, *[v.knowledge_version_id for v in versions]}
        for table in b.Base.metadata.sorted_tables:
            # The document owns its unpublished versions and administrative
            # classifications. Every other FK reference protects physical deletion.
            if table.name in {
                "knowledge_documents",
                "knowledge_document_versions",
                "knowledge_document_labels",
            }:
                continue
            columns = [
                col
                for col in table.c
                if any(
                    fk.column.table.name in {"knowledge_documents", "knowledge_document_versions"}
                    and fk.column.name != "tenant_id"
                    for fk in col.foreign_keys
                )
            ]
            if not columns:
                continue
            predicates = [or_(*[col.in_(targets) for col in columns])]
            if "tenant_id" in table.c:
                predicates.append(table.c.tenant_id == self.tenant_id)
            count = s.scalar(select(func.count()).select_from(table).where(*predicates))
            if count:
                refs[table.name] = count
        pin_count = s.scalar(
            select(func.count())
            .select_from(m.AnalysisSnapshotRegistryPinEntity)
            .where(
                m.AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant_id,
                or_(
                    m.AnalysisSnapshotRegistryPinEntity.object_id.in_(targets),
                    m.AnalysisSnapshotRegistryPinEntity.version_id.in_(targets),
                ),
            )
        )
        if pin_count:
            refs["analysis_snapshot_registry_pins"] = pin_count
        return {
            "document_id": doc.document_id,
            "references": refs,
            "protected_version_history": protected,
            "eligible_draft": not refs and not protected,
        }

    def impact(self, identity):
        require_management_permission(self.context, "document:read")
        with self.sessions() as s:
            return self._impact(s, self.owner.get(s, k.KnowledgeDocumentEntity, identity))

    def mutate(self, operation, identity, request):
        require_management_permission(self.context, DOCUMENT_OPERATIONS[operation])
        action = "DOCUMENT_" + operation
        with self.sessions() as s, s.begin():
            # Same short metadata lock order used by both administration channels.
            s.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": f"kb01:taxonomy-mutations:{self.tenant_id}"},
            )
            idem, cached = self.management._key(
                s,
                action,
                request.idempotency_key,
                {
                    "identity": str(identity) if identity else None,
                    "request": request.model_dump(mode="json"),
                },
            )
            if cached is not None:
                return cached
            if operation == "CREATE":
                created = self.owner._create_document_in_session(
                    s, {"source_id": str(request.source_id), "display_name": request.metadata.title}
                )
                doc = self.owner.get(s, k.KnowledgeDocumentEntity, created["document_id"], True)
            elif operation in {"NEW_VERSION", "DELETE_DRAFT"}:
                doc = self.owner.get(s, k.KnowledgeDocumentEntity, identity, True)
                if doc.record_version != request.expected_record_version:
                    raise KnowledgeManagementConflict("KNOWLEDGE_DOCUMENT_VERSION_CONFLICT")
            else:
                initial = self.owner.get(s, k.KnowledgeDocumentVersionEntity, identity)
                doc = self.owner.get(s, k.KnowledgeDocumentEntity, initial.document_id, True)
                version = self.owner.version(s, identity)
                if version.record_version != request.expected_record_version:
                    raise KnowledgeManagementConflict("KNOWLEDGE_VERSION_CONFLICT")
            if operation in {"CREATE", "NEW_VERSION"}:
                payload = {
                    "collection_version_id": str(request.collection_version_id),
                    "language": request.language,
                    "effective_from": request.effective_from,
                    "effective_to": request.effective_to,
                    "provenance": {"kb01_actor": self.context.permission.actor_id},
                }
                made = self.owner._create_version_in_session(s, doc.document_id, payload)
                version = self.owner.get(
                    s, k.KnowledgeDocumentVersionEntity, made["knowledge_version_id"]
                )
                self._set_metadata(s, doc, version, request.metadata)
                doc.record_version += 1
                doc.updated_at = datetime.now(UTC)
                s.flush()
                result = self._version_view(s, doc, version)
            elif operation == "EDIT_DRAFT":
                if version.lifecycle != "DRAFT":
                    raise KnowledgeManagementConflict("KNOWLEDGE_VERSION_IMMUTABLE")
                self._set_metadata(s, doc, version, request.metadata)
                version.record_version += 1
                doc.record_version += 1
                s.flush()
                result = self._version_view(s, doc, version)
            elif operation == "DELETE_DRAFT":
                impact = self._impact(s, doc)
                policy = self.management._retention_policy(s)
                if (
                    not impact["eligible_draft"]
                    or not policy.draft_delete_allowed
                    or (datetime.now(UTC) - doc.created_at).total_seconds()
                    < policy.draft_retention_seconds
                ):
                    raise KnowledgeManagementConflict("KNOWLEDGE_DOCUMENT_DELETE_PROTECTED")
                version_ids = select(k.KnowledgeDocumentVersionEntity.knowledge_version_id).where(
                    k.KnowledgeDocumentVersionEntity.tenant_id == self.tenant_id,
                    k.KnowledgeDocumentVersionEntity.document_id == doc.document_id,
                )
                s.execute(
                    delete(KnowledgeDocumentLabelEntity).where(
                        KnowledgeDocumentLabelEntity.tenant_id == self.tenant_id,
                        KnowledgeDocumentLabelEntity.knowledge_version_id.in_(version_ids),
                    )
                )
                s.execute(
                    delete(k.KnowledgeDocumentVersionEntity).where(
                        k.KnowledgeDocumentVersionEntity.tenant_id == self.tenant_id,
                        k.KnowledgeDocumentVersionEntity.document_id == doc.document_id,
                    )
                )
                s.delete(doc)
                result = {"document_id": doc.document_id, "deleted": True, "impact": impact}
            else:
                if operation == "ARCHIVE" and s.scalar(
                    select(func.count())
                    .select_from(KnowledgeManagementHoldEntity)
                    .where(
                        KnowledgeManagementHoldEntity.tenant_id == self.tenant_id,
                        KnowledgeManagementHoldEntity.knowledge_document_id == doc.document_id,
                        KnowledgeManagementHoldEntity.released_at.is_(None),
                    )
                ):
                    raise KnowledgeManagementConflict("KNOWLEDGE_DOCUMENT_HAS_ACTIVE_HOLD")
                self.owner._governance_in_session(
                    s,
                    str(identity),
                    operation.lower().replace("_", "-"),
                    request.expected_record_version,
                )
                doc.record_version += 1
                result = self._version_view(s, doc, version)
            s.flush()
            resource = SimpleNamespace(kind="KNOWLEDGE_DOCUMENT", definition_id=doc.document_id)
            return self.management._audit(
                s, action, resource, getattr(request, "reason", "CREATE"), idem, result
            )
