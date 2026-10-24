"""Management adapter over canonical metadata; the original lifecycle remains authoritative."""

import hashlib
import json
import re
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import cast, delete, func, literal, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from sqlalchemy.orm import aliased

from crossborder_compliance.application.knowledge_taxonomy import OPERATIONS
from crossborder_compliance.domain.knowledge_management import (
    TAXONOMY_KINDS,
    KnowledgeManagementPolicy,
    TaxonomyPayload,
    require_management_permission,
)
from crossborder_compliance.domain.localized_metadata import (
    LocalizedDisplayMetadata,
    resolve_display,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
    AdminOperationReceiptEntity,
    KnowledgeManagementHoldEntity,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresAdminMetadataRepository,
)
from crossborder_compliance.infrastructure.persistence.taxonomy_governance import (
    KnowledgeManagementConflict,
    validate_taxonomy_payload,
)


class KnowledgeManagementCapabilityError(ValueError):
    pass


class PostgresKnowledgeTaxonomyRepository:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant_id, self.actor = str(context.tenant_id), context.permission.actor_id
        self.lifecycle = PostgresAdminMetadataRepository(sessions, context)

    def audit_history(self, identity, *, page=1, page_size=50):
        require_management_permission(self.context, "audit:read")
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("INVALID_PAGINATION")
        with self.sessions() as s:
            q = (
                select(AdminOperationReceiptEntity, m.AdminChangeSetEntity)
                .join(
                    m.AdminChangeSetEntity,
                    (
                        m.AdminChangeSetEntity.change_set_id
                        == AdminOperationReceiptEntity.change_set_id
                    )
                    & (m.AdminChangeSetEntity.tenant_id == AdminOperationReceiptEntity.tenant_id),
                )
                .where(
                    AdminOperationReceiptEntity.tenant_id == self.tenant_id,
                    AdminOperationReceiptEntity.resource_id == str(identity),
                )
            )
            total = s.scalar(select(func.count()).select_from(q.subquery()))
            rows = s.execute(
                q.order_by(
                    m.AdminChangeSetEntity.created_at, AdminOperationReceiptEntity.receipt_id
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        "receipt_id": r.receipt_id,
                        "operation": r.operation,
                        "reason": r.reason,
                        "actor_id": c.actor_id,
                        "created_at": c.created_at.isoformat(),
                        "resource_id": r.resource_id,
                        "resource_kind": r.resource_kind,
                    }
                    for r, c in rows
                ],
            }

    def _hold_resource(self, s, kind, identity, lock=True):
        if kind == "TAXONOMY":
            return self._definition(s, identity, lock)
        q = select(k.KnowledgeDocumentEntity).where(
            k.KnowledgeDocumentEntity.tenant_id == self.tenant_id,
            k.KnowledgeDocumentEntity.document_id == str(identity),
        )
        row = s.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise LookupError("knowledge document not found")
        return row

    @staticmethod
    def _hold_view(row):
        return {
            "hold_id": row.hold_id,
            "resource_type": "TAXONOMY" if row.metadata_definition_id else "KNOWLEDGE_DOCUMENT",
            "resource_id": row.metadata_definition_id or row.knowledge_document_id,
            "reason": row.reason,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat(),
            "released_by": row.released_by,
            "released_at": row.released_at.isoformat() if row.released_at else None,
            "record_version": row.record_version,
        }

    def list_holds(self, resource_type, identity):
        require_management_permission(self.context, "hold:read")
        with self.sessions() as s:
            self._hold_resource(s, resource_type, identity, False)
            col = (
                KnowledgeManagementHoldEntity.metadata_definition_id
                if resource_type == "TAXONOMY"
                else KnowledgeManagementHoldEntity.knowledge_document_id
            )
            rows = s.scalars(
                select(KnowledgeManagementHoldEntity)
                .where(
                    KnowledgeManagementHoldEntity.tenant_id == self.tenant_id, col == str(identity)
                )
                .order_by(KnowledgeManagementHoldEntity.created_at)
            ).all()
            return [self._hold_view(row) for row in rows]

    def create_hold(self, request):
        require_management_permission(self.context, "hold:create")
        with self.sessions() as s, s.begin():
            idem, cached = self._key(
                s, "HOLD_CREATE", request.idempotency_key, request.model_dump(mode="json")
            )
            if cached is not None:
                return cached
            resource = self._hold_resource(s, request.resource_type, request.resource_id)
            if resource.record_version != request.expected_record_version:
                raise KnowledgeManagementConflict("KNOWLEDGE_RESOURCE_VERSION_CONFLICT")
            row = KnowledgeManagementHoldEntity(
                hold_id=str(uuid4()),
                tenant_id=self.tenant_id,
                metadata_definition_id=str(request.resource_id)
                if request.resource_type == "TAXONOMY"
                else None,
                knowledge_document_id=str(request.resource_id)
                if request.resource_type == "KNOWLEDGE_DOCUMENT"
                else None,
                created_by=self.actor,
                reason=request.reason,
            )
            s.add(row)
            s.flush()
            audit_resource = SimpleNamespace(
                kind=request.resource_type, definition_id=str(request.resource_id)
            )
            return self._audit(
                s, "HOLD_CREATE", audit_resource, request.reason, idem, self._hold_view(row)
            )

    def release_hold(self, identity, request):
        require_management_permission(self.context, "hold:release")
        with self.sessions() as s, s.begin():
            idem, cached = self._key(
                s,
                "HOLD_RELEASE",
                request.idempotency_key,
                {"hold_id": str(identity), "request": request.model_dump(mode="json")},
            )
            if cached is not None:
                return cached
            row = s.scalar(
                select(KnowledgeManagementHoldEntity)
                .where(
                    KnowledgeManagementHoldEntity.tenant_id == self.tenant_id,
                    KnowledgeManagementHoldEntity.hold_id == str(identity),
                )
                .with_for_update()
            )
            if row is None:
                raise LookupError("hold not found")
            if row.released_at or row.record_version != request.expected_record_version:
                raise KnowledgeManagementConflict("KNOWLEDGE_HOLD_VERSION_CONFLICT")
            row.released_by, row.released_at, row.status = self.actor, datetime.now(UTC), "RELEASED"
            row.record_version += 1
            s.flush()
            result = self._hold_view(row)
            audit_resource = SimpleNamespace(
                kind=result["resource_type"], definition_id=result["resource_id"]
            )
            return self._audit(s, "HOLD_RELEASE", audit_resource, request.reason, idem, result)

    def _definition(self, s, ident, lock=False):
        q = select(m.MetadataDefinitionEntity).where(
            m.MetadataDefinitionEntity.tenant_id == self.tenant_id,
            m.MetadataDefinitionEntity.definition_id == str(ident),
            m.MetadataDefinitionEntity.kind.in_(TAXONOMY_KINDS),
        )
        row = s.scalar(q.with_for_update() if lock else q)
        if row is None:
            raise LookupError("taxonomy not found")
        return row

    def _version(self, s, ident, lock=False):
        q = select(m.MetadataVersionEntity).where(
            m.MetadataVersionEntity.tenant_id == self.tenant_id,
            m.MetadataVersionEntity.version_id == str(ident),
        )
        row = s.scalar(q)
        if row is None:
            raise LookupError("taxonomy version not found")
        self._definition(s, row.definition_id, lock)
        if lock:
            row = s.scalar(q.with_for_update().execution_options(populate_existing=True))
        return row

    def _latest(self, s, definition):
        if definition.active_version_id:
            return self._version(s, definition.active_version_id)
        return s.scalar(
            select(m.MetadataVersionEntity)
            .where(
                m.MetadataVersionEntity.tenant_id == self.tenant_id,
                m.MetadataVersionEntity.definition_id == definition.definition_id,
            )
            .order_by(m.MetadataVersionEntity.version_no.desc())
            .limit(1)
        )

    def _view(self, s, row, locale="en-US"):
        version = self._latest(s, row)
        created_by = s.scalar(
            select(m.MetadataVersionEntity.created_by)
            .where(
                m.MetadataVersionEntity.tenant_id == self.tenant_id,
                m.MetadataVersionEntity.definition_id == row.definition_id,
            )
            .order_by(m.MetadataVersionEntity.version_no)
            .limit(1)
        )
        updated_by = s.scalar(
            select(m.AdminChangeSetEntity.actor_id)
            .join(
                AdminOperationReceiptEntity,
                AdminOperationReceiptEntity.change_set_id == m.AdminChangeSetEntity.change_set_id,
            )
            .where(
                AdminOperationReceiptEntity.tenant_id == self.tenant_id,
                m.AdminChangeSetEntity.tenant_id == self.tenant_id,
                AdminOperationReceiptEntity.resource_id == row.definition_id,
            )
            .order_by(
                m.AdminChangeSetEntity.created_at.desc(), AdminOperationReceiptEntity.receipt_id
            )
            .limit(1)
        )
        return self._project_view(row, version, created_by, updated_by, locale)

    @staticmethod
    def _project_view(row, version, created_by, updated_by, locale):
        """One response projection for individual and bounded batch reads."""
        payload = version.payload_json if version else {}
        display = resolve_display(
            row.code,
            row.display_name,
            LocalizedDisplayMetadata.model_validate(payload.get("localized_display", {})),
            locale,
        )
        return {
            "definition_id": row.definition_id,
            "canonical_object_id": row.canonical_object_id,
            "kind": row.kind,
            "code": row.code,
            "display_name": display.display_name,
            "display": display.model_dump(mode="json"),
            "record_version": row.record_version,
            "active_version_id": row.active_version_id,
            "version_id": version.version_id if version else None,
            "lifecycle": version.lifecycle_status if version else "DRAFT",
            "enabled": payload.get("enabled", True),
            "payload": {k: v for k, v in payload.items() if k in TaxonomyPayload.model_fields},
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "created_by": created_by,
            "updated_by": updated_by,
        }

    def _page_views(self, s, rows, locale):
        """Three tenant-bound reads for a page; no shared or long-lived cache."""
        if not rows:
            return []
        ids = [row.definition_id for row in rows]
        active_ids = [row.active_version_id for row in rows if row.active_version_id]
        draft_ids = [row.definition_id for row in rows if not row.active_version_id]
        draft_versions = (
            select(m.MetadataVersionEntity.version_id)
            .where(
                m.MetadataVersionEntity.tenant_id == self.tenant_id,
                m.MetadataVersionEntity.definition_id.in_(draft_ids),
            )
            .distinct(m.MetadataVersionEntity.definition_id)
            .order_by(
                m.MetadataVersionEntity.definition_id, m.MetadataVersionEntity.version_no.desc()
            )
        )
        # Exact active versions and the latest draft versions are both fetched
        # in one query. Validate the owning taxonomy like the single-row reader.
        versions = s.scalars(
            select(m.MetadataVersionEntity)
            .join(
                m.MetadataDefinitionEntity,
                (m.MetadataDefinitionEntity.definition_id == m.MetadataVersionEntity.definition_id)
                & (m.MetadataDefinitionEntity.tenant_id == m.MetadataVersionEntity.tenant_id),
            )
            .where(
                m.MetadataVersionEntity.tenant_id == self.tenant_id,
                m.MetadataDefinitionEntity.kind.in_(TAXONOMY_KINDS),
                or_(
                    m.MetadataVersionEntity.version_id.in_(active_ids),
                    m.MetadataVersionEntity.version_id.in_(draft_versions),
                ),
            )
        ).all()
        by_id = {version.version_id: version for version in versions}
        latest = {}
        for version in versions:
            previous = latest.get(version.definition_id)
            if previous is None or version.version_no > previous.version_no:
                latest[version.definition_id] = version
        creators = dict(
            s.execute(
                select(m.MetadataVersionEntity.definition_id, m.MetadataVersionEntity.created_by)
                .where(
                    m.MetadataVersionEntity.tenant_id == self.tenant_id,
                    m.MetadataVersionEntity.definition_id.in_(ids),
                )
                .distinct(m.MetadataVersionEntity.definition_id)
                .order_by(m.MetadataVersionEntity.definition_id, m.MetadataVersionEntity.version_no)
            ).all()
        )
        actors = dict(
            s.execute(
                select(AdminOperationReceiptEntity.resource_id, m.AdminChangeSetEntity.actor_id)
                .join(
                    m.AdminChangeSetEntity,
                    m.AdminChangeSetEntity.change_set_id
                    == AdminOperationReceiptEntity.change_set_id,
                )
                .where(
                    AdminOperationReceiptEntity.tenant_id == self.tenant_id,
                    m.AdminChangeSetEntity.tenant_id == self.tenant_id,
                    AdminOperationReceiptEntity.resource_id.in_(ids),
                )
                .distinct(AdminOperationReceiptEntity.resource_id)
                .order_by(
                    AdminOperationReceiptEntity.resource_id,
                    m.AdminChangeSetEntity.created_at.desc(),
                    AdminOperationReceiptEntity.receipt_id,
                )
            ).all()
        )
        result = []
        for row in rows:
            version = (
                by_id.get(row.active_version_id)
                if row.active_version_id
                else latest.get(row.definition_id)
            )
            if row.active_version_id and version is None:
                raise LookupError("taxonomy version not found")
            result.append(
                self._project_view(
                    row,
                    version,
                    creators.get(row.definition_id),
                    actors.get(row.definition_id),
                    locale,
                )
            )
        return result

    def tree(
        self,
        *,
        kind="JURISDICTION_CONFIG",
        parent_definition_id=None,
        page=1,
        page_size=50,
        locale="en-US",
    ):
        """Paged children of the published canonical hierarchy, never a draft proposal."""
        require_management_permission(self.context, "taxonomy:read")
        if kind not in TAXONOMY_KINDS or page < 1 or not 1 <= page_size <= 100:
            raise ValueError("INVALID_TAXONOMY_TREE_QUERY")
        definition, version = m.MetadataDefinitionEntity, m.MetadataVersionEntity

        def visible(d, v):
            return (
                d.tenant_id == self.tenant_id,
                d.kind == kind,
                v.tenant_id == self.tenant_id,
                v.lifecycle_status == "ACTIVE",
                cast(v.payload_json, JSONB)["enabled"].as_boolean().is_not(False),
            )

        with self.sessions() as s:
            if parent_definition_id is not None:
                parent = s.scalar(
                    select(definition)
                    .join(version, version.version_id == definition.active_version_id)
                    .where(
                        *visible(definition, version),
                        definition.definition_id == str(parent_definition_id),
                    )
                )
                if parent is None:
                    raise LookupError("published taxonomy parent not found")
            child, child_version = aliased(definition), aliased(version)
            children = (
                select(func.count())
                .select_from(child)
                .join(child_version, child_version.version_id == child.active_version_id)
                .where(
                    *visible(child, child_version),
                    child.parent_definition_id == definition.definition_id,
                )
                .correlate(definition)
                .scalar_subquery()
            )
            query = (
                select(definition, version, children.label("child_count"))
                .join(version, version.version_id == definition.active_version_id)
                .where(
                    *visible(definition, version),
                    definition.parent_definition_id == str(parent_definition_id)
                    if parent_definition_id is not None
                    else definition.parent_definition_id.is_(None),
                )
            )
            total = s.scalar(select(func.count()).select_from(query.subquery()))
            rows = s.execute(
                query.order_by(definition.code, definition.definition_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            items = []
            for row, active, count in rows:
                display = resolve_display(
                    row.code,
                    row.display_name,
                    LocalizedDisplayMetadata.model_validate(
                        active.payload_json.get("localized_display", {})
                    ),
                    locale,
                )
                items.append(
                    {
                        "definition_id": row.definition_id,
                        "version_id": active.version_id,
                        "parent_definition_id": row.parent_definition_id,
                        "kind": row.kind,
                        "code": row.code,
                        "display_name": display.display_name,
                        "child_count": count,
                    }
                )
            return {
                "parent_definition_id": parent_definition_id,
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }

    def list(self, *, kind=None, query="", page=1, page_size=50, locale="en-US", enabled=None):
        require_management_permission(self.context, "taxonomy:read")
        if not 1 <= page_size <= 100 or page < 1:
            raise ValueError("INVALID_PAGINATION")
        with self.sessions() as s:
            candidate = aliased(m.MetadataVersionEntity)
            selected_version = func.coalesce(
                m.MetadataDefinitionEntity.active_version_id,
                select(candidate.version_id)
                .where(
                    candidate.tenant_id == self.tenant_id,
                    candidate.definition_id == m.MetadataDefinitionEntity.definition_id,
                )
                .order_by(candidate.version_no.desc())
                .limit(1)
                .correlate(m.MetadataDefinitionEntity)
                .scalar_subquery(),
            )
            q = select(m.MetadataDefinitionEntity).where(
                m.MetadataDefinitionEntity.tenant_id == self.tenant_id,
                m.MetadataDefinitionEntity.kind.in_(TAXONOMY_KINDS),
            )
            if kind:
                q = q.where(m.MetadataDefinitionEntity.kind == kind)
            if query:
                q = q.where(
                    or_(
                        m.MetadataDefinitionEntity.code.ilike(f"%{query}%"),
                        m.MetadataDefinitionEntity.display_name.ilike(f"%{query}%"),
                        select(m.MetadataVersionEntity.version_id)
                        .where(
                            m.MetadataVersionEntity.tenant_id == self.tenant_id,
                            m.MetadataVersionEntity.version_id == selected_version,
                            func.jsonb_path_exists(
                                cast(m.MetadataVersionEntity.payload_json, JSONB),
                                cast(
                                    "$.aliases[*] ? (@ like_regex "
                                    + json.dumps(re.escape(query))
                                    + ' flag "i")',
                                    JSONPATH,
                                ),
                            ),
                        )
                        .exists(),
                        select(m.MetadataVersionEntity.version_id)
                        .where(
                            m.MetadataVersionEntity.tenant_id == self.tenant_id,
                            m.MetadataVersionEntity.version_id == selected_version,
                            func.jsonb_path_exists(
                                cast(m.MetadataVersionEntity.payload_json, JSONB),
                                cast(
                                    "$.localized_display.localized_display_names.* ? (@ like_regex "
                                    + json.dumps(re.escape(query))
                                    + ' flag "i")',
                                    JSONPATH,
                                ),
                            ),
                        )
                        .exists(),
                    )
                )
            # Enablement is versioned data. The correlated latest/active version
            # query keeps filtering/counts in PostgreSQL, before pagination.
            if enabled is not None:
                value = (
                    select(candidate.payload_json["enabled"].as_boolean())
                    .where(candidate.version_id == selected_version)
                    .correlate(m.MetadataDefinitionEntity)
                    .scalar_subquery()
                )
                q = q.where(func.coalesce(value, True) == enabled)
            total = s.scalar(select(func.count()).select_from(q.subquery()))
            rows = s.scalars(
                q.order_by(
                    m.MetadataDefinitionEntity.code, m.MetadataDefinitionEntity.definition_id
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": self._page_views(s, rows, locale),
            }

    def detail(self, identity):
        require_management_permission(self.context, "taxonomy:read")
        with self.sessions() as s:
            row = self._definition(s, identity)
            versions = s.scalars(
                select(m.MetadataVersionEntity)
                .where(
                    m.MetadataVersionEntity.tenant_id == self.tenant_id,
                    m.MetadataVersionEntity.definition_id == row.definition_id,
                )
                .order_by(m.MetadataVersionEntity.version_no.desc())
            ).all()
            return {**self._view(s, row), "versions": [self._version_view(v) for v in versions]}

    def aliases(self, identity):
        require_management_permission(self.context, "taxonomy:read")
        with self.sessions() as s:
            source = self._definition(s, identity)
            targets = s.scalars(
                select(m.MetadataDefinitionEntity)
                .join(
                    m.MetadataVersionEntity,
                    m.MetadataVersionEntity.version_id
                    == m.MetadataDefinitionEntity.active_version_id,
                )
                .where(
                    m.MetadataDefinitionEntity.tenant_id == self.tenant_id,
                    m.MetadataDefinitionEntity.kind == source.kind,
                    m.MetadataVersionEntity.tenant_id == self.tenant_id,
                    m.MetadataVersionEntity.lifecycle_status == "ACTIVE",
                    cast(m.MetadataVersionEntity.payload_json, JSONB)[
                        "merge_source_definition_ids"
                    ].contains([source.definition_id]),
                )
            ).all()
            if len(targets) > 1:
                raise KnowledgeManagementConflict("TAXONOMY_ALIAS_AMBIGUOUS")
            return {
                "source_definition_id": source.definition_id,
                "display_only": True,
                "historical_rebinding": False,
                "targets": [self._view(s, target) for target in targets],
            }

    def _version_view(self, row):
        return {
            "version_id": row.version_id,
            "definition_id": row.definition_id,
            "version_no": row.version_no,
            "lifecycle_status": row.lifecycle_status,
            "record_version": row.record_version,
            "payload": {
                k: v for k, v in row.payload_json.items() if k in TaxonomyPayload.model_fields
            },
            "created_by": row.created_by,
            "approved_by": row.approved_by,
        }

    def _validate(self, s, definition, payload):
        return validate_taxonomy_payload(s, definition, payload)

    def _new_version(self, s, definition, payload):
        self._validate(s, definition, payload)
        number = (
            s.scalar(
                select(func.coalesce(func.max(m.MetadataVersionEntity.version_no), 0)).where(
                    m.MetadataVersionEntity.tenant_id == self.tenant_id,
                    m.MetadataVersionEntity.definition_id == definition.definition_id,
                )
            )
            + 1
        )
        version = m.MetadataVersionEntity(
            version_id=str(uuid4()),
            tenant_id=self.tenant_id,
            definition_id=definition.definition_id,
            version_no=number,
            lifecycle_status="DRAFT",
            payload_json=payload,
            created_by=self.actor,
        )
        s.add(version)
        definition.record_version += 1
        s.flush()
        return self._version_view(version)

    def _key(self, s, operation, key, payload):
        client = hashlib.sha256(f"{self.tenant_id}:{self.actor}".encode()).hexdigest()
        namespace = f"kb01:taxonomy:{operation}:{key}"
        request_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        s.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"{client}:{namespace}"},
        )
        existing = s.scalar(
            select(b.ApiIdempotencyEntity).where(
                b.ApiIdempotencyEntity.tenant_id == self.tenant_id,
                b.ApiIdempotencyEntity.api_client_id == client,
                b.ApiIdempotencyEntity.idempotency_key == namespace,
            )
        )
        if existing:
            if existing.request_hash != request_hash:
                raise KnowledgeManagementConflict("IDEMPOTENCY_PAYLOAD_CONFLICT")
            receipt = s.scalar(
                select(AdminOperationReceiptEntity).where(
                    AdminOperationReceiptEntity.tenant_id == self.tenant_id,
                    AdminOperationReceiptEntity.receipt_id == existing.response_ref,
                )
            )
            if receipt is None:
                raise KnowledgeManagementConflict("IDEMPOTENCY_RECEIPT_INCOMPLETE")
            return existing, receipt.result_json
        row = b.ApiIdempotencyEntity(
            api_idempotency_id=str(uuid4()),
            tenant_id=self.tenant_id,
            api_client_id=client,
            idempotency_key=namespace,
            request_hash=request_hash,
        )
        s.add(row)
        return row, None

    def _audit(self, s, operation, definition, reason, idem, result):
        change_id, receipt_id = str(uuid4()), str(uuid4())
        s.add(
            m.AdminChangeSetEntity(
                change_set_id=change_id,
                tenant_id=self.tenant_id,
                actor_id=self.actor,
                lifecycle_status="DRAFT",
                summary=f"KB01 {operation} {definition.kind}",
            )
        )
        s.flush()
        result = {**result, "receipt_id": receipt_id, "operation": operation}
        s.add(
            AdminOperationReceiptEntity(
                receipt_id=receipt_id,
                tenant_id=self.tenant_id,
                change_set_id=change_id,
                resource_kind=definition.kind,
                resource_id=definition.definition_id,
                operation=operation,
                reason=reason,
                request_hash=idem.request_hash,
                result_json=result,
            )
        )
        idem.response_ref = receipt_id
        return result

    def _impact(self, s, definition):
        versions = s.scalars(
            select(m.MetadataVersionEntity).where(
                m.MetadataVersionEntity.tenant_id == self.tenant_id,
                m.MetadataVersionEntity.definition_id == definition.definition_id,
            )
        ).all()
        targets = {
            "metadata_definitions": [definition.definition_id],
            "metadata_versions": [v.version_id for v in versions],
        }
        if definition.canonical_object_id:
            targets["jurisdictions"] = [definition.canonical_object_id]
        refs = {}
        for table in b.Base.metadata.sorted_tables:
            if table.name in {"metadata_versions", "admin_operation_receipts"}:
                continue
            checks = [
                column.in_(targets[fk.column.table.name])
                for column in table.columns
                for fk in column.foreign_keys
                if fk.column.table.name in targets
                and fk.column.name != "tenant_id"
                and targets[fk.column.table.name]
            ]
            if not checks:
                continue
            conditions = [or_(*checks)]
            if "tenant_id" in table.c:
                conditions.append(table.c.tenant_id == self.tenant_id)
            count = s.scalar(select(func.count()).select_from(table).where(*conditions))
            if count:
                refs[table.name] = count
        # Core versioned configuration may carry governed references in JSON.
        for model, column, label in (
            (
                m.MetadataVersionEntity,
                m.MetadataVersionEntity.payload_json,
                "metadata_payload_refs",
            ),
            (
                m.KnowledgeBindingEntity,
                m.KnowledgeBindingEntity.dimensions_json,
                "knowledge_scope_refs",
            ),
            (
                m.KnowledgeSourceDefinitionEntity,
                m.KnowledgeSourceDefinitionEntity.config_json,
                "knowledge_source_refs",
            ),
        ):
            clauses = [
                func.jsonb_path_exists(
                    cast(column, JSONB),
                    cast(literal("$.** ? (@ == $id)"), JSONPATH),
                    literal({"id": identity}, type_=JSONB),
                )
                for ids in targets.values()
                for identity in ids
            ]
            query = (
                select(func.count())
                .select_from(model)
                .where(model.tenant_id == self.tenant_id, or_(*clauses))
            )
            if model is m.MetadataVersionEntity:
                query = query.where(model.definition_id != definition.definition_id)
            count = s.scalar(query)
            if count:
                refs[label] = count
        pins = s.scalar(
            select(func.count())
            .select_from(m.AnalysisSnapshotRegistryPinEntity)
            .where(
                m.AnalysisSnapshotRegistryPinEntity.tenant_id == self.tenant_id,
                or_(
                    m.AnalysisSnapshotRegistryPinEntity.object_id.in_(sum(targets.values(), [])),
                    m.AnalysisSnapshotRegistryPinEntity.version_id.in_(
                        targets["metadata_versions"]
                    ),
                ),
            )
        )
        if pins:
            refs["snapshot_pins"] = pins
        protected = any(
            v.lifecycle_status != "DRAFT" or v.approved_by or v.published_at for v in versions
        )
        return {
            "definition_id": definition.definition_id,
            "references": refs,
            "protected_version_history": protected,
            "eligible_draft": not refs and not protected,
        }

    def impact(self, identity):
        require_management_permission(self.context, "taxonomy:read")
        with self.sessions() as s:
            return self._impact(s, self._definition(s, identity))

    def _retention_policy(self, s):
        rows = s.execute(
            select(m.MetadataDefinitionEntity, m.MetadataVersionEntity)
            .join(
                m.MetadataVersionEntity,
                m.MetadataVersionEntity.version_id == m.MetadataDefinitionEntity.active_version_id,
            )
            .where(
                m.MetadataDefinitionEntity.tenant_id == self.tenant_id,
                m.MetadataDefinitionEntity.kind == "KNOWLEDGE_MANAGEMENT_POLICY",
                m.MetadataDefinitionEntity.status == "ACTIVE",
                m.MetadataVersionEntity.tenant_id == self.tenant_id,
                m.MetadataVersionEntity.lifecycle_status == "ACTIVE",
            )
        ).all()
        if len(rows) != 1:
            raise KnowledgeManagementCapabilityError(
                "KNOWLEDGE_MANAGEMENT_POLICY_NOT_CONFIGURED_OR_AMBIGUOUS"
            )
        _, version = rows[0]
        now = datetime.now(UTC).date()
        if (
            not version.approved_by
            or version.approved_by == version.created_by
            or not version.published_at
            or (version.effective_from and version.effective_from > now)
            or (version.effective_to and version.effective_to < now)
        ):
            raise KnowledgeManagementCapabilityError("KNOWLEDGE_MANAGEMENT_POLICY_NOT_AUTHORIZED")
        publication = s.scalar(
            select(m.AdminPublishRecordEntity.publish_record_id).where(
                m.AdminPublishRecordEntity.tenant_id == self.tenant_id,
                m.AdminPublishRecordEntity.version_id == version.version_id,
                m.AdminPublishRecordEntity.object_kind == "KNOWLEDGE_MANAGEMENT_POLICY",
            )
        )
        if not publication:
            raise KnowledgeManagementCapabilityError("KNOWLEDGE_MANAGEMENT_POLICY_NOT_AUTHORIZED")
        return KnowledgeManagementPolicy.model_validate(version.payload_json)

    def mutate(self, operation, identity, request):
        require_management_permission(self.context, OPERATIONS[operation])
        payload = request.model_dump(mode="json")
        with self.sessions() as s, s.begin():
            # Only small taxonomy mutations serialize per tenant; no file I/O
            # or archive work runs under this transaction/lock. Root-before-
            # version locking also matches the existing metadata owner.
            s.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": f"kb01:taxonomy-mutations:{self.tenant_id}"},
            )
            idem, existing = self._key(
                s,
                operation,
                request.idempotency_key,
                {"identity": str(identity) if identity else None, "request": payload},
            )
            if existing is not None:
                return existing
            if operation == "CREATE":
                if request.kind == "JURISDICTION_CONFIG" and len(request.display_name) > 200:
                    raise ValueError("TAXONOMY_DISPLAY_NAME_TOO_LONG")
                definition = m.MetadataDefinitionEntity(
                    definition_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    kind=request.kind,
                    code=request.code,
                    display_name=request.display_name,
                )
                if request.kind == "JURISDICTION_CONFIG":
                    jurisdiction = b.JurisdictionEntity(
                        jurisdiction_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        code=request.code,
                        name=request.display_name,
                        status="DRAFT",
                    )
                    s.add(jurisdiction)
                    s.flush()
                    definition.canonical_object_type = "JURISDICTION_CONFIG"
                    definition.canonical_object_id = jurisdiction.jurisdiction_id
                s.add(definition)
                s.flush()
                result = self._new_version(s, definition, request.payload.model_dump(mode="json"))
                result.update(canonical_object_id=definition.canonical_object_id)
            elif operation in {
                "EDIT_DRAFT",
                "SUBMIT_REVIEW",
                "APPROVE",
                "REJECT",
                "PUBLISH",
                "ARCHIVE",
            }:
                version = self._version(s, identity, True)
                definition = self._definition(s, version.definition_id, True)
                if version.record_version != request.expected_record_version:
                    raise KnowledgeManagementConflict("TAXONOMY_VERSION_CONFLICT")
                if operation == "EDIT_DRAFT":
                    if version.lifecycle_status != "DRAFT":
                        raise KnowledgeManagementConflict("TAXONOMY_VERSION_IMMUTABLE")
                    new = {
                        **version.payload_json,
                        **request.payload.model_dump(mode="json", exclude_unset=True),
                    }
                    new["management_schema"] = "KB01_TAXONOMY_V1"
                    self._validate(s, definition, new)
                    version.payload_json = new
                    version.record_version += 1
                    definition.record_version += 1
                    result = self._version_view(version)
                else:
                    if operation == "APPROVE" and (
                        version.created_by == self.actor or self.context.permission.system
                    ):
                        raise KnowledgeManagementConflict("INDEPENDENT_HUMAN_REVIEW_REQUIRED")
                    self._validate(s, definition, version.payload_json)
                    target = {
                        "SUBMIT_REVIEW": "PENDING_REVIEW",
                        "APPROVE": "APPROVED",
                        "REJECT": "DRAFT",
                        "PUBLISH": "ACTIVE",
                        "ARCHIVE": "ARCHIVED",
                    }[operation]
                    if (
                        operation == "ARCHIVE"
                        and definition.kind == "JURISDICTION_CONFIG"
                        and self._impact(s, definition)["references"]
                    ):
                        raise KnowledgeManagementConflict(
                            "REFERENCED_JURISDICTION_USE_VERSIONED_DEACTIVATION"
                        )
                    self.lifecycle._transition_in_session(
                        s,
                        UUID(version.version_id),
                        target_status=target,
                        actor_id=self.actor,
                        expected_record_version=request.expected_record_version,
                    )
                    if operation == "PUBLISH":
                        self._publish_projection(s, definition, version)
                    elif operation == "ARCHIVE" and definition.canonical_object_id:
                        row = s.get(b.JurisdictionEntity, definition.canonical_object_id)
                        row.status = "ARCHIVED"
                    result = self._version_view(version)
            else:
                definition = self._definition(s, identity, True)
                if definition.record_version != request.expected_record_version:
                    raise KnowledgeManagementConflict("TAXONOMY_DEFINITION_CONFLICT")
                current = self._latest(s, definition)
                if operation == "DELETE_DRAFT":
                    impact = self._impact(s, definition)
                    policy = self._retention_policy(s)
                    elapsed = (datetime.now(UTC) - definition.created_at).total_seconds()
                    if (
                        not impact["eligible_draft"]
                        or not policy.draft_delete_allowed
                        or elapsed < policy.draft_retention_seconds
                    ):
                        raise KnowledgeManagementConflict("TAXONOMY_DELETE_PROTECTED")
                    result = {
                        "definition_id": definition.definition_id,
                        "deleted": True,
                        "impact": impact,
                    }
                    canonical = definition.canonical_object_id
                    s.execute(
                        delete(m.MetadataVersionEntity).where(
                            m.MetadataVersionEntity.tenant_id == self.tenant_id,
                            m.MetadataVersionEntity.definition_id == definition.definition_id,
                        )
                    )
                    s.delete(definition)
                    s.flush()
                    if canonical:
                        s.execute(
                            delete(b.JurisdictionEntity).where(
                                b.JurisdictionEntity.tenant_id == self.tenant_id,
                                b.JurisdictionEntity.jurisdiction_id == canonical,
                            )
                        )
                elif operation in {"NEW_VERSION", "DEACTIVATE", "REACTIVATE"}:
                    value = {
                        **(current.payload_json if current else {}),
                        **(
                            request.payload.model_dump(mode="json", exclude_unset=True)
                            if operation == "NEW_VERSION"
                            else {}
                        ),
                    }
                    if operation in {"DEACTIVATE", "REACTIVATE"}:
                        value["enabled"] = operation == "REACTIVATE"
                        value["management_schema"] = "KB01_TAXONOMY_V1"
                    result = self._new_version(s, definition, value)
                    result["effect"] = "GOVERNED_PROPOSAL_NOT_YET_ACTIVE"
                elif operation == "MERGE_PROPOSAL":
                    target = self._definition(s, request.target_definition_id, True)
                    if (
                        target.definition_id == definition.definition_id
                        or target.kind != definition.kind
                    ):
                        raise ValueError("INVALID_TAXONOMY_MERGE_TARGET")
                    if target.record_version != request.expected_target_record_version:
                        raise KnowledgeManagementConflict("TAXONOMY_TARGET_CONFLICT")
                    latest = self._latest(s, target)
                    value = dict(latest.payload_json if latest else {})
                    value["merge_source_definition_ids"] = sorted(
                        {*value.get("merge_source_definition_ids", []), definition.definition_id}
                    )
                    value["merge_source_record_versions"] = {
                        **value.get("merge_source_record_versions", {}),
                        definition.definition_id: definition.record_version,
                    }
                    value["management_schema"] = "KB01_TAXONOMY_V1"
                    result = self._new_version(s, target, value)
                    result["effect"] = "ALIAS_PROPOSAL_NO_HISTORICAL_REBINDING"
                else:
                    raise ValueError("UNSUPPORTED_TAXONOMY_OPERATION")
            s.flush()
            return self._audit(
                s, operation, definition, getattr(request, "reason", "CREATE"), idem, result
            )

    def _publish_projection(self, s, definition, version):
        value = self._validate(s, definition, version.payload_json)
        definition.parent_definition_id = (
            str(value.parent_definition_id) if value.parent_definition_id else None
        )
        names = value.localized_display.localized_display_names
        label = names.get(value.localized_display.fallback_locale)
        if label:
            definition.display_name = label
        if definition.canonical_object_id:
            jurisdiction = s.scalar(
                select(b.JurisdictionEntity).where(
                    b.JurisdictionEntity.tenant_id == self.tenant_id,
                    b.JurisdictionEntity.jurisdiction_id == definition.canonical_object_id,
                )
            )
            if jurisdiction is None:
                raise LookupError("canonical jurisdiction missing")
            jurisdiction.name = definition.display_name
            # Identity remains valid for exact historical analysis; a versioned
            # availability flag filters discovery/new selection, not old rows.
            jurisdiction.status = "ACTIVE"
            jurisdiction.record_version += 1
        for source_id in value.merge_source_definition_ids:
            prior = s.scalar(
                select(m.MetadataBindingEntity).where(
                    m.MetadataBindingEntity.tenant_id == self.tenant_id,
                    m.MetadataBindingEntity.binding_type == "KB_TAXONOMY_ALIAS",
                    m.MetadataBindingEntity.source_definition_id == str(source_id),
                    m.MetadataBindingEntity.target_definition_id == definition.definition_id,
                )
            )
            if prior is None:
                s.add(
                    m.MetadataBindingEntity(
                        binding_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        binding_type="KB_TAXONOMY_ALIAS",
                        source_definition_id=str(source_id),
                        target_definition_id=definition.definition_id,
                        scope_json={
                            "target_version_id": version.version_id,
                            "display_only": True,
                            "historical_rebinding": False,
                        },
                    )
                )
