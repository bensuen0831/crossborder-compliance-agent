import hashlib
import json
import math
from datetime import date
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID, uuid4

from sqlalchemy import func, select, text

from crossborder_compliance.domain.knowledge import (
    DIMENSIONS,
    PRODUCT_DIMENSIONS,
    KnowledgeBinding,
    KnowledgeSource,
    KnowledgeTranslation,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import context_models as c
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)


def hash_value(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def result(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def effective(row, when):
    return (row.effective_from is None or row.effective_from <= when) and (
        row.effective_to is None or row.effective_to >= when
    )


def date_value(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


class PostgresKnowledgeRepository:
    def __init__(self, sessions, context: RepositoryContext):
        self.sessions, self.context, self.tenant_id = sessions, context, str(context.tenant_id)

    def admin(self):
        if (
            not self.context.permission.system
            and "knowledge:admin" not in self.context.permission.scopes
        ):
            raise PermissionError("knowledge administration permission required")

    def rows(self, s, model, *conditions):
        return s.scalars(select(model).where(model.tenant_id == self.tenant_id, *conditions)).all()

    def get(self, s, model, ident, lock=False):
        query = select(model).where(
            list(model.__table__.primary_key)[0] == str(ident), model.tenant_id == self.tenant_id
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = s.scalar(query)
        if row is None:
            raise LookupError("object not found")
        return row

    def version(self, s, ident, expected=None):
        row = self.get(s, k.KnowledgeDocumentVersionEntity, ident, True)
        if expected is not None and row.record_version != expected:
            raise OptimisticConcurrencyError("stale knowledge version")
        return row

    def metadata(self, s, ident, kind=None, when=None):
        row = self.get(s, m.MetadataDefinitionEntity, ident)
        if kind and row.kind != kind:
            raise ValueError("metadata dimension mismatch")
        if not row.active_version_id or row.status != "ACTIVE":
            raise ValueError("inactive metadata")
        version = self.get(s, m.MetadataVersionEntity, row.active_version_id)
        if version.lifecycle_status != "ACTIVE" or not effective(version, when or date.today()):
            raise ValueError("metadata not effective")
        return row

    def product_lineage(self, s, ident, when):
        """Registry ancestry only; never expand a domain into all registered products."""
        refs = set()
        current = self.metadata(s, ident, when=when)
        while current:
            if current.definition_id in refs:
                raise ValueError("cyclic product registry")
            if current.kind.lower() not in PRODUCT_DIMENSIONS:
                raise ValueError("non-product context reference")
            refs.add(current.definition_id)
            current = (
                self.metadata(s, current.parent_definition_id, when=when)
                if current.parent_definition_id
                else None
            )
        for link in self.rows(
            s, m.MetadataBindingEntity, m.MetadataBindingEntity.source_definition_id == ident
        ):
            if effective(link, when):
                target = self.metadata(s, link.target_definition_id, when=when)
                if target.kind == "PRODUCT_TAG":
                    refs.add(target.definition_id)
        return refs

    def create_source(self, payload):
        self.admin()
        source = KnowledgeSource.model_validate(
            dict(
                payload,
                source_id=str(uuid4()),
                tenant_id=self.tenant_id,
                source_hash=hash_value(payload),
            )
        )
        if source.canonical_url:
            url = urlsplit(source.canonical_url)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.fragment
                or any(
                    key.lower() in {"token", "api_key", "password", "secret"}
                    for key, value in parse_qsl(url.query)
                )
            ):
                raise ValueError("source must use credential-free HTTPS")
        with self.sessions() as s, s.begin():
            self.get(s, m.KnowledgeCollectionEntity, source.collection_id)
            if source.authority_ref:
                self.metadata(s, source.authority_ref)
            for ref in source.jurisdiction_refs:
                self.get(s, b.JurisdictionEntity, ref)
            s.add(
                m.KnowledgeSourceDefinitionEntity(
                    knowledge_source_definition_id=source.source_id,
                    knowledge_collection_id=source.collection_id,
                    tenant_id=self.tenant_id,
                    code=source.code,
                    source_type=source.source_type,
                    config_json=source.model_dump(mode="json"),
                )
            )
        return source.model_dump(mode="json")

    def get_source(self, source_id):
        self.admin()
        with self.sessions() as s:
            return dict(self.get(s, m.KnowledgeSourceDefinitionEntity, source_id).config_json)

    def update_source(self, source_id, payload, expected):
        self.admin()
        with self.sessions() as s, s.begin():
            row = self.get(s, m.KnowledgeSourceDefinitionEntity, source_id, True)
            if row.record_version != expected:
                raise OptimisticConcurrencyError("stale source version")
            if set(payload) - {"enabled", "refresh_policy", "validation_status"}:
                raise ValueError("source identity is immutable")
            row.config_json = KnowledgeSource.model_validate(
                dict(row.config_json, **payload, record_version=expected + 1)
            ).model_dump(mode="json")
            row.record_version += 1
            return row.config_json

    def create_document(self, payload):
        self.admin()
        with self.sessions() as s, s.begin():
            self.get(s, m.KnowledgeSourceDefinitionEntity, payload["source_id"])
            row = k.KnowledgeDocumentEntity(
                document_id=str(uuid4()),
                tenant_id=self.tenant_id,
                source_id=payload["source_id"],
                display_name=payload["display_name"],
            )
            s.add(row)
            s.flush()
            return result(row)

    def create_version(self, document_id, payload):
        self.admin()
        with self.sessions() as s, s.begin():
            doc = self.get(s, k.KnowledgeDocumentEntity, document_id, True)
            source = self.get(s, m.KnowledgeSourceDefinitionEntity, doc.source_id)
            collection = self.get(
                s, m.KnowledgeCollectionVersionEntity, payload["collection_version_id"]
            )
            if collection.knowledge_collection_id != source.knowledge_collection_id:
                raise ValueError("source collection mismatch")
            number = (
                int(
                    s.scalar(
                        select(
                            func.coalesce(func.max(k.KnowledgeDocumentVersionEntity.version), 0)
                        ).where(
                            k.KnowledgeDocumentVersionEntity.tenant_id == self.tenant_id,
                            k.KnowledgeDocumentVersionEntity.document_id == document_id,
                        )
                    )
                    or 0
                )
                + 1
            )
            start, end = (
                date_value(payload.get("effective_from")),
                date_value(payload.get("effective_to")),
            )
            if start and end and end < start:
                raise ValueError("invalid effective dates")
            row = k.KnowledgeDocumentVersionEntity(
                knowledge_version_id=str(uuid4()),
                tenant_id=self.tenant_id,
                document_id=document_id,
                collection_version_id=collection.knowledge_collection_version_id,
                version=number,
                language=payload["language"],
                effective_from=start,
                effective_to=end,
                provenance_json=dict(
                    payload["provenance"],
                    created_by=self.context.user_context.user_id,
                    source_id=source.knowledge_source_definition_id,
                    source_hash=source.config_json["source_hash"],
                ),
            )
            s.add(row)
            s.flush()
            return result(row)

    def binding(self, row):
        return dict(
            binding_id=row.knowledge_binding_id,
            tenant_id=row.tenant_id,
            knowledge_version_id=row.knowledge_version_id,
            scope_type=row.scope_type,
            dimensions=row.dimensions_json,
            permission_scopes=row.permission_scopes_json,
            provenance=row.provenance_json,
            review_status=row.review_status,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            version=row.binding_version,
        )

    def add_binding(self, s, version, payload):
        binding = KnowledgeBinding.model_validate(
            dict(
                payload,
                binding_id=str(uuid4()),
                tenant_id=self.tenant_id,
                knowledge_version_id=version.knowledge_version_id,
            )
        )
        for dimension, refs in binding.dimensions.items():
            for ref in refs:
                if dimension == "jurisdiction":
                    self.get(s, b.JurisdictionEntity, ref)
                else:
                    self.metadata(s, ref, dimension.upper())
        row = m.KnowledgeBindingEntity(
            knowledge_binding_id=binding.binding_id,
            tenant_id=self.tenant_id,
            knowledge_collection_version_id=version.collection_version_id,
            knowledge_version_id=version.knowledge_version_id,
            scope_type=binding.scope_type,
            scope_ref=binding.binding_id,
            binding_version=binding.version,
            dimensions_json={key: list(values) for key, values in binding.dimensions.items()},
            permission_scopes_json=list(binding.permission_scopes),
            provenance_json=binding.provenance,
            review_status="PENDING",
            effective_from=binding.effective_from,
            effective_to=binding.effective_to,
        )
        s.add(row)
        return row

    def create_binding(self, version_id, payload, expected):
        self.admin()
        with self.sessions() as s, s.begin():
            version = self.version(s, version_id, expected)
            if version.lifecycle not in {"DRAFT", "INGESTED"}:
                raise ValueError("reviewed binding is immutable")
            row = self.add_binding(s, version, payload)
            version.record_version += 1
            s.flush()
            return self.binding(row)

    def schedule_ingestion(self, version_id, payload):
        self.admin()
        if bool(payload.get("nodes")) == bool(payload.get("url")):
            raise ValueError("canonical upload or approved URL required")
        with self.sessions() as s, s.begin():
            version = self.version(s, version_id)
            previous = self.rows(
                s,
                k.KnowledgeIngestionRunEntity,
                k.KnowledgeIngestionRunEntity.knowledge_version_id == version_id,
            )
            for run in previous:
                if run.idempotency_key == payload["idempotency_key"]:
                    if run.request_hash != hash_value(payload):
                        raise ValueError("idempotency payload mismatch")
                    return result(run)
            if version.lifecycle != "DRAFT" or previous:
                raise ValueError("version already ingested or scheduled")
            doc = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
            source = self.get(s, m.KnowledgeSourceDefinitionEntity, doc.source_id)
            if payload.get("url") and payload["url"] != source.config_json.get("canonical_url"):
                raise ValueError("URL must match source definition")
            for binding in payload.get("bindings", []):
                self.add_binding(s, version, binding)
            run_id, event_id = str(uuid4()), str(uuid4())
            s.add(
                m.RegistrySyncEventEntity(
                    registry_sync_event_id=event_id,
                    tenant_id=self.tenant_id,
                    object_kind="KNOWLEDGE_INGESTION",
                    object_id=run_id,
                    version_id=version_id,
                    event_version=1,
                    status="PENDING",
                    attempts=0,
                )
            )
            s.flush()
            row = k.KnowledgeIngestionRunEntity(
                ingestion_run_id=run_id,
                tenant_id=self.tenant_id,
                knowledge_version_id=version_id,
                idempotency_key=payload["idempotency_key"],
                request_hash=hash_value(payload),
                input_json=payload,
                audit_json={},
                status="PENDING",
                outbox_event_id=event_id,
            )
            s.add(row)
            s.flush()
            return result(row)

    def ingestion_input(self, run_id):
        self.admin()
        with self.sessions() as s:
            run = self.get(s, k.KnowledgeIngestionRunEntity, run_id)
            version = self.get(s, k.KnowledgeDocumentVersionEntity, run.knowledge_version_id)
            doc = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
            source = self.get(s, m.KnowledgeSourceDefinitionEntity, doc.source_id)
            return dict(
                status=run.status,
                run=result(run),
                input=run.input_json,
                tenant_id=self.tenant_id,
                version_id=version.knowledge_version_id,
                language=version.language,
                effective_from=version.effective_from,
                source_id=doc.source_id,
                document_id=doc.document_id,
                official_source=source.config_json.get("canonical_url") or source.code,
            )

    def fail_ingestion(self, run_id):
        self.admin()
        with self.sessions() as s, s.begin():
            row = self.get(s, k.KnowledgeIngestionRunEntity, run_id, True)
            if row.status != "COMPLETED":
                row.status = "FAILED"
                row.error_code = "INGESTION_FAILED"
                row.record_version += 1

    def complete_ingestion(self, run_id, nodes, chunks, audit):
        self.admin()
        with self.sessions() as s, s.begin():
            run = self.get(s, k.KnowledgeIngestionRunEntity, run_id, True)
            if run.status == "COMPLETED":
                return result(run)
            version = self.version(s, run.knowledge_version_id)
            if version.lifecycle != "DRAFT":
                raise ValueError("canonical version is immutable")
            doc = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
            source = self.get(s, m.KnowledgeSourceDefinitionEntity, doc.source_id)
            jurisdictions = source.config_json.get("jurisdiction_refs", [])
            legal = source.source_type in {"OFFICIAL_REGULATOR", "OFFICIAL_LEGISLATION"}
            if legal and len(jurisdictions) != 1:
                raise ValueError("legal structure requires canonical source jurisdiction")
            pending = list(nodes)
            inserted = set()
            while pending:
                ready = [n for n in pending if not n.parent_node_id or n.parent_node_id in inserted]
                if not ready:
                    raise ValueError("invalid hierarchy")
                for node in ready:
                    if node.knowledge_version_id != version.knowledge_version_id:
                        raise ValueError("cross-version structure")
                    eid = str(uuid4())
                    evidence = dict(
                        node.provenance,
                        knowledge_version_id=version.knowledge_version_id,
                        structure_node_id=node.structure_node_id,
                        original_language=node.language,
                        effective_date=str(node.effective_date),
                        canonical_locator=node.canonical_locator,
                    )
                    s.add(
                        b.EvidenceReferenceEntity(
                            evidence_id=eid,
                            tenant_id=self.tenant_id,
                            evidence_type="KNOWLEDGE_ORIGINAL",
                            source_ref=json.dumps(evidence, sort_keys=True),
                            excerpt_hash=hash_value(node.original_text),
                            validation_status="VALIDATED",
                        )
                    )
                    s.flush()
                    s.add(
                        b.CitationEntity(
                            citation_id=node.citation_id,
                            tenant_id=self.tenant_id,
                            evidence_id=eid,
                            locator=node.canonical_locator,
                            quote_hash=hash_value(node.original_text),
                        )
                    )
                    if legal:
                        s.add(
                            b.RegulatoryStructureNodeEntity(
                                regulatory_structure_node_id=node.structure_node_id,
                                tenant_id=self.tenant_id,
                                jurisdiction_id=jurisdictions[0],
                                regulation_version_ref=version.knowledge_version_id,
                                node_type=node.node_type,
                                node_path=node.canonical_locator,
                                official_source=evidence["official_source"],
                                effective_from=version.effective_from,
                                effective_to=version.effective_to,
                            )
                        )
                    s.flush()
                    values = node.model_dump(exclude={"source_trace", "provenance"})
                    s.add(
                        k.KnowledgeStructureNodeEntity(
                            **values,
                            tenant_id=self.tenant_id,
                            regulatory_structure_node_id=node.structure_node_id if legal else None,
                            source_trace_json=node.source_trace,
                            provenance_json=node.provenance,
                        )
                    )
                    s.flush()
                    pending.remove(node)
                    inserted.add(node.structure_node_id)
            for chunk in chunks:
                if (
                    chunk.knowledge_version_id != version.knowledge_version_id
                    or not set(chunk.structure_node_ids) <= inserted
                ):
                    raise ValueError("chunk provenance outside canonical version")
                s.add(
                    k.KnowledgeChunkEntity(
                        **chunk.model_dump(exclude={"structure_node_ids", "citation_refs"}),
                        tenant_id=self.tenant_id,
                    )
                )
                s.flush()
                for node_id in chunk.structure_node_ids:
                    s.add(
                        k.KnowledgeChunkNodeEntity(
                            chunk_id=chunk.chunk_id,
                            structure_node_id=node_id,
                            tenant_id=self.tenant_id,
                        )
                    )
            version.lifecycle = "INGESTED"
            version.record_version += 1
            version.content_hash = audit["content_hash"]
            version.original_artifact_ref = audit["artifact_ref"]
            run.status = "COMPLETED"
            run.error_code = None
            run.audit_json = audit
            run.record_version += 1
            self.change(s, version.knowledge_version_id, "INGESTED", audit)
            s.flush()
            return result(run)

    def dispatch_outbox(self, queue):
        self.admin()
        delivered = 0
        with self.sessions() as s, s.begin():
            events = s.scalars(
                select(m.RegistrySyncEventEntity)
                .where(
                    m.RegistrySyncEventEntity.tenant_id == self.tenant_id,
                    m.RegistrySyncEventEntity.object_kind == "KNOWLEDGE_INGESTION",
                    m.RegistrySyncEventEntity.status == "PENDING",
                )
                .with_for_update(skip_locked=True)
            ).all()
            for event in events:
                event.attempts += 1
                try:
                    queue.enqueue(task_id=UUID(event.object_id), task_type="KNOWLEDGE_INGESTION")
                except Exception:
                    event.last_error = "QUEUE_DELIVERY_FAILED"
                    continue
                event.status = "APPLIED"
                event.applied_at = b.utcnow()
                delivered += 1
        return delivered

    def change(self, s, version_id, event_type, provenance):
        s.add(
            k.KnowledgeChangeEventEntity(
                event_id=str(uuid4()),
                tenant_id=self.tenant_id,
                knowledge_version_id=version_id,
                event_type=event_type,
                provenance_json=provenance,
            )
        )

    def quality(self, s, version):
        doc = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
        source = self.get(s, m.KnowledgeSourceDefinitionEntity, doc.source_id)
        nodes = self.rows(
            s,
            k.KnowledgeStructureNodeEntity,
            k.KnowledgeStructureNodeEntity.knowledge_version_id == version.knowledge_version_id,
        )
        chunks = self.rows(
            s,
            k.KnowledgeChunkEntity,
            k.KnowledgeChunkEntity.knowledge_version_id == version.knowledge_version_id,
        )
        bindings = self.rows(
            s,
            m.KnowledgeBindingEntity,
            m.KnowledgeBindingEntity.knowledge_version_id == version.knowledge_version_id,
        )
        collection = self.get(s, m.KnowledgeCollectionVersionEntity, version.collection_version_id)
        checks = dict(
            source_quality=source.config_json.get("validation_status") == "VALIDATED"
            and source.config_json.get("enabled", False),
            structure_quality=bool(nodes and chunks),
            citation_quality=bool(nodes) and all(n.citation_id for n in nodes),
            version_quality=bool(version.content_hash) and collection.lifecycle_status == "ACTIVE",
            language_quality=bool(version.language)
            and all(n.language == version.language for n in nodes),
            binding_completeness=bool(bindings) and all(row.provenance_json for row in bindings),
            provenance_completeness=bool(version.provenance_json and version.original_artifact_ref)
            and all(n.source_trace_json and n.provenance_json for n in nodes),
        )
        existing = self.rows(
            s,
            k.KnowledgeQualityResultEntity,
            k.KnowledgeQualityResultEntity.knowledge_version_id == version.knowledge_version_id,
        )
        row = (
            existing[0]
            if existing
            else k.KnowledgeQualityResultEntity(
                quality_id=str(uuid4()),
                tenant_id=self.tenant_id,
                knowledge_version_id=version.knowledge_version_id,
            )
        )
        if not existing:
            s.add(row)
        row.checks_json = checks
        row.reason_codes_json = [name.upper() for name, passed in checks.items() if not passed]
        row.status = "PASS" if all(checks.values()) else "FAILED"
        return row

    def governance(self, version_id, action, expected):
        self.admin()
        actor = self.context.user_context.user_id
        with self.sessions() as s, s.begin():
            initial = self.get(s, k.KnowledgeDocumentVersionEntity, version_id)
            self.get(s, k.KnowledgeDocumentEntity, initial.document_id, True)
            version = self.version(s, version_id)
            if action == "publish" and version.lifecycle == "ACTIVE":
                return result(version)
            if version.record_version != expected:
                raise OptimisticConcurrencyError("stale knowledge version")
            transitions = {
                "validate": ("INGESTED", "VALIDATED"),
                "submit-review": ("VALIDATED", "PENDING_REVIEW"),
                "approve": ("PENDING_REVIEW", "APPROVED"),
                "publish": ("APPROVED", "ACTIVE"),
                "supersede": ("ACTIVE", "SUPERSEDED"),
                "expire": ("ACTIVE", "EXPIRED"),
                "archive": ("EXPIRED", "ARCHIVED"),
            }
            before, after = transitions[action]
            if version.lifecycle != before:
                raise ValueError("invalid lifecycle transition")
            if action in {"validate", "approve", "publish"}:
                quality = self.quality(s, version)
                if quality.status != "PASS":
                    if action == "validate":
                        s.flush()
                        return dict(result(version), quality_status="FAILED")
                    raise ValueError("quality gate failed")
            if action == "submit-review":
                change, task = str(uuid4()), str(uuid4())
                s.add(
                    m.AdminChangeSetEntity(
                        change_set_id=change,
                        tenant_id=self.tenant_id,
                        actor_id=actor,
                        lifecycle_status="PENDING_REVIEW",
                        summary=f"Knowledge version {version_id}",
                    )
                )
                s.flush()
                s.add(
                    m.AdminReviewTaskEntity(
                        review_task_id=task,
                        tenant_id=self.tenant_id,
                        change_set_id=change,
                        review_status="PENDING",
                    )
                )
                s.flush()
                version.review_task_id = task
            if action == "approve":
                task = self.get(s, m.AdminReviewTaskEntity, version.review_task_id, True)
                change = self.get(s, m.AdminChangeSetEntity, task.change_set_id)
                if self.context.permission.system or change.actor_id == actor:
                    raise ValueError("independent human reviewer required")
                task.review_status = "APPROVED"
                task.reviewer_id = actor
                task.decision_comment = "Knowledge and binding review approved"
                change.lifecycle_status = "APPROVED"
                version.approved_by = actor
                for binding in self.rows(
                    s,
                    m.KnowledgeBindingEntity,
                    m.KnowledgeBindingEntity.knowledge_version_id == version_id,
                ):
                    binding.review_status = "APPROVED"
            if action == "publish":
                task = self.get(s, m.AdminReviewTaskEntity, version.review_task_id)
                if task.review_status != "APPROVED" or not version.approved_by:
                    raise ValueError("review required before ACTIVE")
                if not effective(version, date.today()):
                    raise ValueError("publish outside effective dates")
                for old in self.rows(
                    s,
                    k.KnowledgeDocumentVersionEntity,
                    k.KnowledgeDocumentVersionEntity.document_id == version.document_id,
                    k.KnowledgeDocumentVersionEntity.lifecycle == "ACTIVE",
                ):
                    old.lifecycle = "SUPERSEDED"
                    old.record_version += 1
                    self.change(
                        s,
                        old.knowledge_version_id,
                        "SUPERSEDED",
                        {"replacement_version_id": version_id},
                    )
                    self.diff(s, old, version)
                s.add(
                    m.AdminPublishRecordEntity(
                        publish_record_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        object_kind="KNOWLEDGE_DOCUMENT",
                        version_id=version_id,
                        published_by=actor,
                    )
                )
            version.lifecycle = after
            version.record_version += 1
            self.change(s, version_id, after, {"actor": actor})
            s.flush()
            return result(version)

    def diff(self, s, old, new):
        def nodes(version):
            return {
                n.canonical_locator: hash_value((n.original_text, n.heading, n.node_type))
                for n in self.rows(
                    s,
                    k.KnowledgeStructureNodeEntity,
                    k.KnowledgeStructureNodeEntity.knowledge_version_id
                    == version.knowledge_version_id,
                )
            }

        def bindings(version):
            return sorted(
                hash_value((r.scope_type, r.dimensions_json, r.permission_scopes_json))
                for r in self.rows(
                    s,
                    m.KnowledgeBindingEntity,
                    m.KnowledgeBindingEntity.knowledge_version_id == version.knowledge_version_id,
                )
            )

        left, right = nodes(old), nodes(new)
        changes = dict(
            added_structure_nodes=sorted(right.keys() - left.keys()),
            removed_structure_nodes=sorted(left.keys() - right.keys()),
            modified_structure_nodes=sorted(
                key for key in left.keys() & right.keys() if left[key] != right[key]
            ),
            effective_date_changed=(old.effective_from, old.effective_to)
            != (new.effective_from, new.effective_to),
            binding_changed=bindings(old) != bindings(new),
            source_changed=(
                old.provenance_json.get("source_id"),
                old.provenance_json.get("source_hash"),
            )
            != (new.provenance_json.get("source_id"), new.provenance_json.get("source_hash")),
        )
        s.add(
            k.KnowledgeVersionDiffEntity(
                diff_id=str(uuid4()),
                tenant_id=self.tenant_id,
                old_version_id=old.knowledge_version_id,
                new_version_id=new.knowledge_version_id,
                changes_json=changes,
            )
        )
        return changes

    def compare_versions(self, old_id, new_id):
        self.admin()
        with self.sessions() as s, s.begin():
            return self.diff(
                s,
                self.get(s, k.KnowledgeDocumentVersionEntity, old_id),
                self.get(s, k.KnowledgeDocumentVersionEntity, new_id),
            )

    def get_version(self, version_id):
        self.admin()
        with self.sessions() as s:
            return result(self.get(s, k.KnowledgeDocumentVersionEntity, version_id))

    def get_run(self, run_id):
        self.admin()
        with self.sessions() as s:
            return {
                key: value
                for key, value in result(self.get(s, k.KnowledgeIngestionRunEntity, run_id)).items()
                if key not in {"input_json", "audit_json"}
            }

    def list_component(self, version_id, component):
        self.admin()
        with self.sessions() as s:
            self.get(s, k.KnowledgeDocumentVersionEntity, version_id)
            models = {
                "structure": k.KnowledgeStructureNodeEntity,
                "chunks": k.KnowledgeChunkEntity,
                "bindings": m.KnowledgeBindingEntity,
                "quality": k.KnowledgeQualityResultEntity,
            }
            rows = self.rows(
                s, models[component], models[component].knowledge_version_id == version_id
            )
            if component == "bindings":
                return [self.binding(row) for row in rows]
            if component == "quality":
                return [
                    dict(
                        knowledge_version_id=r.knowledge_version_id,
                        status=r.status,
                        checks=r.checks_json,
                        reason_codes=r.reason_codes_json,
                    )
                    for r in rows
                ]
            if component == "structure":
                return [result(row) for row in sorted(rows, key=lambda n: n.sequence)]
            return [
                dict(
                    result(row),
                    structure_node_ids=[
                        link.structure_node_id
                        for link in self.rows(
                            s,
                            k.KnowledgeChunkNodeEntity,
                            k.KnowledgeChunkNodeEntity.chunk_id == row.chunk_id,
                        )
                    ],
                    citation_refs=[
                        self.get(
                            s, k.KnowledgeStructureNodeEntity, link.structure_node_id
                        ).citation_id
                        for link in self.rows(
                            s,
                            k.KnowledgeChunkNodeEntity,
                            k.KnowledgeChunkNodeEntity.chunk_id == row.chunk_id,
                        )
                    ],
                )
                for row in sorted(rows, key=lambda n: n.sequence)
            ]

    def create_translation(self, version_id, payload):
        self.admin()
        translation = KnowledgeTranslation.model_validate(
            dict(payload, translation_id=str(uuid4()), knowledge_version_id=version_id)
        )
        if translation.review_status != "PENDING" or translation.reviewer:
            raise ValueError("translation must enter review")
        if translation.translation_method == "AI" and not translation.model_config_id:
            raise ValueError("AI translation requires model registry config")
        with self.sessions() as s, s.begin():
            version = self.get(s, k.KnowledgeDocumentVersionEntity, version_id)
            if translation.source_language != version.language:
                raise ValueError("source language mismatch")
            if translation.model_config_id:
                self.get(s, m.ModelDeploymentEntity, translation.model_config_id)
            row = k.KnowledgeTranslationEntity(
                **translation.model_dump(exclude={"provenance"}),
                tenant_id=self.tenant_id,
                provenance_json=dict(
                    translation.provenance, submitted_by=self.context.user_context.user_id
                ),
            )
            s.add(row)
            s.flush()
            return dict(result(row), official_evidence=False)

    def approve_translation(self, translation_id, expected):
        self.admin()
        with self.sessions() as s, s.begin():
            row = self.get(s, k.KnowledgeTranslationEntity, translation_id, True)
            if row.record_version != expected:
                raise OptimisticConcurrencyError("stale translation")
            if (
                self.context.permission.system
                or row.provenance_json["submitted_by"] == self.context.user_context.user_id
            ):
                raise ValueError("independent translation reviewer required")
            row.review_status = "APPROVED"
            row.reviewer = self.context.user_context.user_id
            row.record_version += 1
            return dict(result(row), official_evidence=row.translation_method == "OFFICIAL")

    def snapshot_date(self, snapshot_id):
        with self.sessions() as s:
            return self.get(s, b.AnalysisSnapshotEntity, snapshot_id).analysis_as_of_date

    def formal_context(self, project_id, subject_type, subject_id, snapshot_id):
        with self.sessions() as s:
            self.get(s, b.ProjectEntity, project_id)
            runs = self.rows(
                s,
                c.ContextResolutionRunEntity,
                c.ContextResolutionRunEntity.project_id == project_id,
                c.ContextResolutionRunEntity.status == "COMPLETED",
            )
            if not runs:
                raise ValueError("PHASE1E_FORMAL_CONTEXT_REQUIRED")
            run = max(runs, key=lambda r: r.version)
            when = date.today()
            if snapshot_id:
                snapshot = self.get(s, b.AnalysisSnapshotEntity, snapshot_id)
                when = snapshot.analysis_as_of_date
                pins = self.rows(
                    s,
                    c.AnalysisSnapshotContextPinEntity,
                    c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == snapshot_id,
                )
                if pins:
                    if pins[0].project_id != project_id:
                        raise LookupError("snapshot project mismatch")
                    run = self.get(
                        s, c.ContextResolutionRunEntity, pins[0].context_resolution_run_id
                    )
                else:
                    pv = self.get(s, b.ProjectVersionEntity, snapshot.project_version_id)
                    if pv.project_id != project_id:
                        raise LookupError("snapshot project mismatch")
            dims = {d: set() for d in DIMENSIONS}
            reasons = []
            systems = set()
            parties = set()
            locations = None
            scopes = self.rows(
                s,
                c.ProductScopeResolutionEntity,
                c.ProductScopeResolutionEntity.project_id == project_id,
                c.ProductScopeResolutionEntity.version == run.product_context_version,
            )
            unresolved = (
                not scopes
                or scopes[0].review_required
                or not scopes[0].effective_product_scope_json
            )
            products = set(scopes[0].effective_product_scope_json) if not unresolved else set()
            project_products = set(products)
            if unresolved:
                reasons.append("UNRESOLVED_PRODUCT_SCOPE")
            if subject_type in {"DATA_ITEM", "DATA_FLOW"}:
                item_ids = [subject_id]
                if subject_type == "DATA_FLOW":
                    flow = self.get(s, b.DataFlowEdgeEntity, subject_id)
                    detail = self.get(s, c.DataFlowEdgeDetailEntity, subject_id)
                    if (
                        flow.project_id != project_id
                        or detail.version != run.data_flow_version
                        or detail.validation_status != "VALIDATED"
                    ):
                        raise ValueError("FORMAL_FLOW_VERSION_UNAVAILABLE")
                    item_ids = [
                        link.data_item_id
                        for link in self.rows(
                            s,
                            b.DataItemFlowLinkEntity,
                            b.DataItemFlowLinkEntity.flow_edge_id == subject_id,
                        )
                    ]
                    known_locations = set()
                    for node_id in (flow.source_node_id, flow.target_node_id):
                        details = self.rows(
                            s,
                            c.DataFlowNodeDetailEntity,
                            c.DataFlowNodeDetailEntity.flow_node_id == node_id,
                        )
                        if details:
                            node = details[0]
                            if node.system_id:
                                systems.add(node.system_id)
                            if node.party_id:
                                parties.add(node.party_id)
                            if node.jurisdiction_context_id:
                                known_locations.add(node.jurisdiction_context_id)
                    if known_locations:
                        locations = known_locations
                products = set()
                for item_id in item_ids:
                    item = self.get(s, b.DataItemEntity, item_id)
                    detail = self.get(s, c.DataItemResolutionDetailEntity, item_id)
                    if (
                        item.project_id != project_id
                        or detail.version != run.data_inventory_version
                        or detail.validation_status != "VALIDATED"
                        or detail.review_required
                    ):
                        raise ValueError("FORMAL_ITEM_VERSION_UNAVAILABLE")
                    products.update(
                        link.product_ref
                        for link in self.rows(
                            s,
                            b.DataItemProductLinkEntity,
                            b.DataItemProductLinkEntity.data_item_id == item_id,
                        )
                    )
                    systems.update(detail.system_ids_json)
                    for device_id in detail.device_ids_json:
                        device = self.get(s, c.DeviceContextEntity, device_id)
                        if device.project_id != project_id:
                            raise ValueError("formal device project mismatch")
                        if device.system_id:
                            systems.add(device.system_id)
                bounded = set()
                for linked in products:
                    lineage = self.product_lineage(s, linked, when)
                    for selected in project_products:
                        if selected in lineage:
                            bounded.add(linked)
                        elif linked in self.product_lineage(s, selected, when):
                            bounded.add(selected)
                products = bounded
                if not products:
                    unresolved = True
                    reasons.append("UNRESOLVED_SUBJECT_PRODUCT_SCOPE")
            elif subject_type != "PROJECT" or subject_id != project_id:
                raise ValueError("invalid subject")
            for system_id in systems:
                system = self.get(s, c.SystemContextEntity, system_id)
                if system.project_id != project_id or system.validation_status != "VALIDATED":
                    raise ValueError("formal system unavailable")
                parties.update(system.party_refs_json)
            for party_id in parties:
                party = self.get(s, b.ProjectPartyEntity, party_id)
                if party.project_id != project_id:
                    raise ValueError("formal party project mismatch")
            for ref in products:
                current = self.metadata(s, ref, when=when)
                seen = set()
                while current:
                    if current.definition_id in seen:
                        raise ValueError("cyclic product registry")
                    seen.add(current.definition_id)
                    if current.kind.lower() in PRODUCT_DIMENSIONS:
                        dims[current.kind.lower()].add(current.definition_id)
                    current = (
                        self.metadata(s, current.parent_definition_id, when=when)
                        if current.parent_definition_id
                        else None
                    )
                for link in self.rows(
                    s, m.MetadataBindingEntity, m.MetadataBindingEntity.source_definition_id == ref
                ):
                    if effective(link, when):
                        target = self.metadata(s, link.target_definition_id, when=when)
                        if target.kind == "PRODUCT_TAG":
                            dims["product_tag"].add(target.definition_id)
            for scenario in self.rows(
                s,
                c.ScenarioContextEntity,
                c.ScenarioContextEntity.project_id == project_id,
                c.ScenarioContextEntity.version == run.version,
            ):
                if (
                    scenario.scenario_definition_id
                    and not scenario.review_required
                    and scenario.validation_status == "VALIDATED"
                ):
                    dims["scenario"].add(scenario.scenario_definition_id)
                else:
                    reasons.append("UNRESOLVED_SCENARIO_SCOPE")
            for jurisdiction in self.rows(
                s,
                c.JurisdictionContextEntity,
                c.JurisdictionContextEntity.project_id == project_id,
                c.JurisdictionContextEntity.version == run.version,
            ):
                if locations is not None and jurisdiction.jurisdiction_context_id not in locations:
                    continue
                if jurisdiction.jurisdiction_id and jurisdiction.validation_status == "VALIDATED":
                    dims["jurisdiction"].add(jurisdiction.jurisdiction_id)
                else:
                    reasons.append("UNRESOLVED_JURISDICTION_SCOPE")
            for fact in self.rows(
                s,
                c.BusinessFactEntity,
                c.BusinessFactEntity.project_id == project_id,
                c.BusinessFactEntity.version == run.version,
            ):
                if (
                    fact.validation_status != "VALIDATED"
                    or fact.review_required
                    or not isinstance(fact.normalized_value_json, dict)
                ):
                    continue
                for dimension in ("industry", "data_category", "jurisdiction_group"):
                    for ref in fact.normalized_value_json.get("metadata_refs", {}).get(
                        dimension, []
                    ):
                        self.metadata(s, ref, dimension.upper(), when)
                        dims[dimension].add(ref)
            return dict(
                project_id=project_id,
                subject_type=subject_type,
                subject_id=subject_id,
                context_version=run.version,
                dimensions={key: sorted(values) for key, values in dims.items()},
                product_unresolved=unresolved,
                reason_codes=sorted(set(reasons)),
                system_ids=sorted(systems),
                party_ids=sorted(parties),
            )

    def scope_candidates(self, when, pinned_version_ids=()):
        with self.sessions() as s:
            candidates = []
            for binding in self.rows(
                s,
                m.KnowledgeBindingEntity,
                m.KnowledgeBindingEntity.knowledge_version_id.is_not(None),
            ):
                if pinned_version_ids and binding.knowledge_version_id not in pinned_version_ids:
                    continue
                version = self.get(
                    s, k.KnowledgeDocumentVersionEntity, binding.knowledge_version_id
                )
                doc = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
                source = self.get(s, m.KnowledgeSourceDefinitionEntity, doc.source_id)
                collection = self.get(
                    s, m.KnowledgeCollectionVersionEntity, version.collection_version_id
                )
                states = (
                    {"ACTIVE", "SUPERSEDED", "EXPIRED", "ARCHIVED"}
                    if pinned_version_ids
                    else {"ACTIVE"}
                )
                lifecycle = (
                    version.lifecycle in states
                    and bool(version.approved_by)
                    and binding.review_status == "APPROVED"
                    and collection.lifecycle_status in states
                    and source.config_json.get("enabled", False)
                    and source.config_json.get("validation_status") == "VALIDATED"
                    and version.status == "ACTIVE"
                    and binding.status == "ACTIVE"
                )
                candidates.append(
                    dict(
                        self.binding(binding),
                        language=version.language,
                        lifecycle_allowed=bool(lifecycle),
                        effective_allowed=effective(version, when)
                        and effective(binding, when)
                        and effective(collection, when),
                    )
                )
            return candidates

    def saved_scope(self, project_id, subject_type, subject_id, snapshot_id):
        with self.sessions() as s:
            self.get(s, b.ProjectEntity, project_id)
            self.get(s, b.AnalysisSnapshotEntity, snapshot_id)
            rows = self.rows(
                s,
                k.KnowledgeScopeResolutionEntity,
                k.KnowledgeScopeResolutionEntity.analysis_snapshot_id == snapshot_id,
                k.KnowledgeScopeResolutionEntity.subject_type == subject_type,
                k.KnowledgeScopeResolutionEntity.subject_id == subject_id,
            )
            if not rows:
                return None
            if rows[0].project_id != project_id:
                raise LookupError("snapshot project mismatch")
            return dict(scope=rows[0].scope_json, formal_context=rows[0].context_json)

    def save_scope(self, payload):
        scope, formal = payload["scope"], payload["formal_context"]
        with self.sessions() as s, s.begin():
            self.get(s, b.ProjectEntity, scope["project_id"], True)
            snapshot = scope["analysis_snapshot_id"]
            if snapshot:
                self.get(s, b.AnalysisSnapshotEntity, snapshot, True)
                rows = self.rows(
                    s,
                    k.KnowledgeScopeResolutionEntity,
                    k.KnowledgeScopeResolutionEntity.analysis_snapshot_id == snapshot,
                    k.KnowledgeScopeResolutionEntity.subject_type == scope["subject_type"],
                    k.KnowledgeScopeResolutionEntity.subject_id == scope["subject_id"],
                )
                if rows:
                    return dict(scope=rows[0].scope_json, formal_context=rows[0].context_json)
                context_pins = self.rows(
                    s,
                    c.AnalysisSnapshotContextPinEntity,
                    c.AnalysisSnapshotContextPinEntity.analysis_snapshot_id == snapshot,
                )
                if context_pins:
                    if context_pins[0].context_resolution_version != formal["context_version"]:
                        raise ValueError("immutable snapshot context version mismatch")
                else:
                    runs = self.rows(
                        s,
                        c.ContextResolutionRunEntity,
                        c.ContextResolutionRunEntity.project_id == scope["project_id"],
                        c.ContextResolutionRunEntity.version == formal["context_version"],
                    )
                    run = runs[0]
                    s.add(
                        c.AnalysisSnapshotContextPinEntity(
                            analysis_snapshot_context_pin_id=str(uuid4()),
                            tenant_id=self.tenant_id,
                            analysis_snapshot_id=snapshot,
                            project_id=scope["project_id"],
                            context_resolution_run_id=run.context_resolution_run_id,
                            context_resolution_version=run.version,
                            product_context_version=run.product_context_version,
                            data_inventory_version=run.data_inventory_version,
                            data_flow_version=run.data_flow_version,
                        )
                    )
                for version_id in scope["filter_spec"]["version_filter"]:
                    version = self.get(s, k.KnowledgeDocumentVersionEntity, version_id)
                    self.pin(s, snapshot, "KNOWLEDGE_VERSION", version_id, version.version)
                    for binding_id in scope["filter_spec"]["binding_filter"]:
                        binding = self.get(s, m.KnowledgeBindingEntity, binding_id)
                        if binding.knowledge_version_id == version_id:
                            self.pin(
                                s,
                                snapshot,
                                "KNOWLEDGE_BINDING",
                                binding_id,
                                binding.binding_version,
                            )
                    indexes = self.rows(
                        s,
                        k.KnowledgeIndexVersionEntity,
                        k.KnowledgeIndexVersionEntity.knowledge_version_id == version_id,
                        k.KnowledgeIndexVersionEntity.build_status == "BUILT",
                    )
                    for index in indexes:
                        self.pin(s, snapshot, "KNOWLEDGE_INDEX_VERSION", index.index_version_id, 1)
                        if index.embedding_config_id:
                            self.pin(
                                s,
                                snapshot,
                                "EMBEDDING_CONFIG_VERSION",
                                index.embedding_config_id,
                                self.get(
                                    s, m.ModelDeploymentEntity, index.embedding_config_id
                                ).record_version,
                            )
            s.add(
                k.KnowledgeScopeResolutionEntity(
                    resolution_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    project_id=scope["project_id"],
                    analysis_snapshot_id=snapshot,
                    subject_type=scope["subject_type"],
                    subject_id=scope["subject_id"],
                    scope_json=scope,
                    context_json=formal,
                )
            )
            return payload

    def pin(self, s, snapshot, kind, ident, number):
        rows = self.rows(
            s,
            m.AnalysisSnapshotRegistryPinEntity,
            m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == snapshot,
            m.AnalysisSnapshotRegistryPinEntity.pin_type == kind,
            m.AnalysisSnapshotRegistryPinEntity.logical_key == ident,
        )
        if rows:
            if rows[0].version_id != ident:
                raise ValueError("immutable analysis snapshot pin")
            return
        s.add(
            m.AnalysisSnapshotRegistryPinEntity(
                pin_id=str(uuid4()),
                tenant_id=self.tenant_id,
                analysis_snapshot_id=snapshot,
                pin_type=kind,
                logical_key=ident,
                object_id=ident,
                version_id=ident,
                version_no=number,
            )
        )

    def subject_project(self, subject_type, ident):
        with self.sessions() as s:
            return self.get(
                s, b.DataItemEntity if subject_type == "DATA_ITEM" else b.DataFlowEdgeEntity, ident
            ).project_id

    def embedding_dimension(self, config_id):
        self.admin()
        from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
            PostgresModelRegistryRepository,
        )
        from crossborder_compliance.infrastructure.registry import ModelRegistry

        registry = ModelRegistry(PostgresModelRegistryRepository(self.sessions, self.context))
        registry.refresh()
        with self.sessions() as s:
            config = self.get(s, m.ModelDeploymentEntity, config_id)
            model = self.get(s, m.ModelDefinitionEntity, config.model_definition_id)
            resolved = registry.resolve(
                model_definition_id=model.model_definition_id, capability="EMBEDDING"
            )
            provider_version = self.get(s, m.ModelProviderVersionEntity, config.provider_version_id)
            if (
                not resolved
                or "EMBEDDING" not in resolved["capabilities"]
                or model.active_deployment_id != config_id
                or not effective(provider_version, date.today())
            ):
                raise ValueError("embedding model unavailable from Phase 1C registry")
            if (
                not config.enabled
                or not model.enabled
                or config.lifecycle_status != "ACTIVE"
                or not effective(config, date.today())
            ):
                raise ValueError("inactive embedding config")
            capabilities = self.rows(
                s,
                m.ModelCapabilityEntity,
                m.ModelCapabilityEntity.model_definition_id == model.model_definition_id,
                m.ModelCapabilityEntity.capability == "EMBEDDING",
            )
            if not capabilities or capabilities[0].status != "ACTIVE":
                raise ValueError("embedding capability required")
            dimension = int(capabilities[0].metadata_json["embedding_dimension"])
            if not 0 < dimension <= 16000:
                raise ValueError("invalid embedding dimension")
            return dimension

    def build_index(self, version_id, config_id=None, embeddings=()):
        self.admin()
        with self.sessions() as s, s.begin():
            version = self.version(s, version_id)
            if version.lifecycle not in {"APPROVED", "ACTIVE"}:
                raise ValueError("index requires approved canonical knowledge")
            chunks = self.rows(
                s, k.KnowledgeChunkEntity, k.KnowledgeChunkEntity.knowledge_version_id == version_id
            )
            if not chunks:
                raise ValueError("canonical chunks required")
            content_hash = hash_value(sorted((row.chunk_id, row.content_hash) for row in chunks))
            previous = self.rows(
                s,
                k.KnowledgeIndexVersionEntity,
                k.KnowledgeIndexVersionEntity.knowledge_version_id == version_id,
                k.KnowledgeIndexVersionEntity.embedding_config_id == config_id,
                k.KnowledgeIndexVersionEntity.content_hash == content_hash,
            )
            if previous:
                return result(previous[0])
            if config_id:
                dimension = self.embedding_dimension(config_id)
                if {ch["chunk_id"] for ch, v in embeddings} != {
                    row.chunk_id for row in chunks
                } or any(
                    len(v) != dimension or not all(math.isfinite(x) for x in v)
                    for ch, v in embeddings
                ):
                    raise ValueError("embedding set does not match canonical chunks")
                job = str(uuid4())
                s.add(
                    k.EmbeddingJobEntity(
                        embedding_job_id=job,
                        tenant_id=self.tenant_id,
                        knowledge_version_id=version_id,
                        model_config_id=config_id,
                        status="COMPLETED",
                    )
                )
                s.flush()
                for chunk, vector in embeddings:
                    row = k.EmbeddingRecordEntity(
                        embedding_record_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        embedding_job_id=job,
                        chunk_id=chunk["chunk_id"],
                        model_config_id=config_id,
                        embedding_dimension=dimension,
                        embedding_version="embedding-v1",
                        vector_hash=hash_value(vector),
                        status="GENERATED",
                    )
                    s.add(row)
                    s.flush()
                    s.execute(
                        text(
                            "UPDATE embedding_records SET embedding_vector=CAST(:vector AS vector) "
                            "WHERE embedding_record_id=:id AND tenant_id=:tenant"
                        ),
                        dict(
                            vector=json.dumps(vector),
                            id=row.embedding_record_id,
                            tenant=self.tenant_id,
                        ),
                    )
                if dimension <= 2000:
                    config = str(UUID(config_id))
                    name = "ix_embedding_model_" + UUID(config_id).hex
                    s.execute(
                        text(
                            f"CREATE INDEX IF NOT EXISTS {name} ON embedding_records USING hnsw "
                            f"((embedding_vector::vector({dimension})) vector_cosine_ops) "
                            f"WHERE model_config_id = '{config}' AND status = 'GENERATED'"
                        )
                    )
            row = k.KnowledgeIndexVersionEntity(
                index_version_id=str(uuid4()),
                tenant_id=self.tenant_id,
                knowledge_version_id=version_id,
                chunking_strategy_version=chunks[0].chunking_strategy_version,
                embedding_config_id=config_id,
                fts_config_version="postgres-simple-v1",
                build_status="BUILT",
                content_hash=content_hash,
                derived=True,
            )
            s.add(row)
            s.flush()
            return result(row)
