"""SQL aggregates over the same authorized document scope as the list API."""

from sqlalchemy import func, select, text

from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence.knowledge_document_management import (
    PostgresKnowledgeDocumentManagement,
)
from crossborder_compliance.infrastructure.persistence.knowledge_management_models import (
    KnowledgeDocumentLabelEntity as Label,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeBinaryAttachmentEntity as Attachment,
)
from crossborder_compliance.infrastructure.persistence.knowledge_upload_models import (
    KnowledgeUploadSessionEntity as Upload,
)


class PostgresKnowledgeStatistics:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context
        self.tenant = str(context.tenant_id)
        self.documents = PostgresKnowledgeDocumentManagement(sessions, context)

    def summary(self, *, query="", label_id=None, label_ids=(), lifecycle=None, language=None):
        require_management_permission(self.context, "statistics:read")
        require_management_permission(self.context, "document:read")
        if len(query) > 250 or language and len(language) > 80:
            raise ValueError("INVALID_STATISTICS_FILTER")
        d, v = k.KnowledgeDocumentEntity, k.KnowledgeDocumentVersionEntity
        scoped, selection = self.documents.scoped_query(
            query=query,
            label_id=label_id,
            label_ids=label_ids,
            lifecycle=lifecycle,
            language=language,
        )
        ids = scoped.with_only_columns(d.document_id)
        representative = scoped.with_only_columns(
            d.document_id, selection.label("version_id")
        ).subquery()
        versions = select(v).where(v.tenant_id == self.tenant, v.document_id.in_(ids))
        chosen = select(v).join(
            representative, representative.c.version_id == v.knowledge_version_id
        )
        with self.sessions() as s, s.begin():
            s.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            cutoff = s.scalar(select(func.now())).isoformat()

            def count(q):
                return s.scalar(select(func.count()).select_from(q.subquery()))

            def groups(q, key):
                group = q.with_only_columns(
                    key.label("key"), func.count(func.distinct(v.document_id)).label("documents")
                )
                return [
                    {"key": key, "documents": number}
                    for key, number in s.execute(group.group_by(key).order_by(key)).all()
                ]

            physical = (
                select(Upload.upload_session_id, Upload.declared_bytes)
                .join(
                    Attachment,
                    (Attachment.tenant_id == Upload.tenant_id)
                    & (Attachment.upload_session_id == Upload.upload_session_id),
                )
                .join(
                    v,
                    (v.tenant_id == Attachment.tenant_id)
                    & (v.knowledge_version_id == Attachment.knowledge_version_id),
                )
                .where(Upload.tenant_id == self.tenant, v.document_id.in_(ids))
                .distinct()
            ).subquery()
            parse = select(k.KnowledgeIngestionRunEntity).join(
                v,
                (v.tenant_id == k.KnowledgeIngestionRunEntity.tenant_id)
                & (v.knowledge_version_id == k.KnowledgeIngestionRunEntity.knowledge_version_id),
            )
            parse = parse.where(v.tenant_id == self.tenant, v.document_id.in_(ids))
            parse_status = dict(
                s.execute(
                    parse.with_only_columns(
                        k.KnowledgeIngestionRunEntity.status, func.count()
                    ).group_by(k.KnowledgeIngestionRunEntity.status)
                ).all()
            )
            labels = chosen.join(
                Label,
                (Label.tenant_id == v.tenant_id)
                & (Label.knowledge_version_id == v.knowledge_version_id),
            ).join(
                m.MetadataDefinitionEntity,
                (m.MetadataDefinitionEntity.tenant_id == Label.tenant_id)
                & (m.MetadataDefinitionEntity.definition_id == Label.definition_id),
            )
            label_rows = s.execute(
                labels.with_only_columns(
                    Label.kind,
                    Label.definition_id,
                    m.MetadataDefinitionEntity.code,
                    func.count(func.distinct(v.document_id)),
                )
                .group_by(Label.kind, Label.definition_id, m.MetadataDefinitionEntity.code)
                .order_by(Label.kind, Label.definition_id)
                .limit(1001)
            ).all()
            return {
                "as_of": cutoff,
                "documents": count(scoped),
                "versions": count(versions),
                "attached_originals": s.scalar(select(func.count()).select_from(physical)),
                "attached_bytes": s.scalar(
                    select(func.coalesce(func.sum(physical.c.declared_bytes), 0))
                ),
                "parse_status": parse_status,
                "by_lifecycle": groups(chosen, v.lifecycle),
                "by_language": groups(chosen, v.language),
                "by_classification": [
                    {"kind": kind, "definition_id": identity, "code": code, "documents": number}
                    for kind, identity, code, number in label_rows[:1000]
                ],
                "classification_groups_truncated": len(label_rows) > 1000,
                "representative_version": "ACTIVE_ELSE_LATEST_MATCHING_LIST",
                "many_to_many_group_totals_are_not_global_totals": True,
                "scope": {
                    "query": query,
                    "label_id": str(label_id) if label_id else None,
                    "label_ids": sorted(set(map(str, label_ids))),
                    "lifecycle": lifecycle,
                    "language": language,
                },
            }
