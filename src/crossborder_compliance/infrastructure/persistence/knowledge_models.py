"""Tenant-audited extensions of Phase 1C sources/bindings and Phase 1B legal nodes."""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import mapped_column

from crossborder_compliance.infrastructure.persistence.models import Base, TenantAuditMixin, utcnow


def col(type_, *, nullable=False, default=None):
    return mapped_column(type_, nullable=nullable, default=default)


def ref(target, *, nullable=False, primary=False):
    return mapped_column(String(36), ForeignKey(target), nullable=nullable, primary_key=primary)


def entity(name, table, fields, constraints=()):
    return type(
        name,
        (TenantAuditMixin, Base),
        dict(__tablename__=table, __table_args__=constraints, **fields),
    )


def ident():
    return mapped_column(String(36), primary_key=True)


KnowledgeDocumentEntity = entity(
    "KnowledgeDocumentEntity",
    "knowledge_documents",
    dict(
        document_id=ident(),
        source_id=ref("knowledge_source_definitions.knowledge_source_definition_id"),
        display_name=col(String(250)),
    ),
)
KnowledgeDocumentVersionEntity = entity(
    "KnowledgeDocumentVersionEntity",
    "knowledge_document_versions",
    dict(
        knowledge_version_id=ident(),
        document_id=ref("knowledge_documents.document_id"),
        collection_version_id=ref("knowledge_collection_versions.knowledge_collection_version_id"),
        version=col(Integer),
        lifecycle=col(String(40), default="DRAFT"),
        language=col(String(80)),
        content_hash=col(String(64), nullable=True),
        original_artifact_ref=col(String(500), nullable=True),
        effective_from=col(Date, nullable=True),
        effective_to=col(Date, nullable=True),
        provenance_json=col(JSON),
        review_task_id=ref("admin_review_tasks.review_task_id", nullable=True),
        approved_by=col(String(160), nullable=True),
    ),
    (
        UniqueConstraint(
            "tenant_id", "document_id", "version", name="uq_knowledge_document_version"
        ),
        CheckConstraint("version > 0", name="ck_knowledge_document_version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_knowledge_effective_dates",
        ),
        CheckConstraint(
            "lifecycle IN ('DRAFT','INGESTED','VALIDATED','PENDING_REVIEW',"
            "'APPROVED','ACTIVE','SUPERSEDED','EXPIRED','ARCHIVED')",
            name="ck_knowledge_lifecycle",
        ),
    ),
)
KnowledgeStructureNodeEntity = entity(
    "KnowledgeStructureNodeEntity",
    "knowledge_structure_nodes",
    dict(
        structure_node_id=ident(),
        regulatory_structure_node_id=ref(
            "regulatory_structure_nodes.regulatory_structure_node_id", nullable=True
        ),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        parent_node_id=ref("knowledge_structure_nodes.structure_node_id", nullable=True),
        node_type=col(String(40)),
        sequence=col(Integer),
        canonical_locator=col(String(500)),
        official_number=col(String(100), nullable=True),
        heading=col(Text),
        original_text=col(Text),
        normalized_text=col(Text),
        language=col(String(80)),
        effective_date=col(Date, nullable=True),
        source_trace_json=col(JSON),
        provenance_json=col(JSON),
        citation_id=ref("citations.citation_id"),
    ),
    (
        UniqueConstraint(
            "tenant_id",
            "knowledge_version_id",
            "canonical_locator",
            name="uq_knowledge_structure_locator",
        ),
        UniqueConstraint("regulatory_structure_node_id", name="uq_knowledge_legal_node_extension"),
    ),
)
KnowledgeChunkEntity = entity(
    "KnowledgeChunkEntity",
    "knowledge_chunks",
    dict(
        chunk_id=ident(),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        chunk_type=col(String(40)),
        original_text=col(Text),
        normalized_text=col(Text),
        token_count=col(Integer),
        language=col(String(80)),
        sequence=col(Integer),
        canonical_locator=col(String(500)),
        content_hash=col(String(64)),
        chunking_strategy_version=col(String(80)),
    ),
    (
        UniqueConstraint(
            "tenant_id", "knowledge_version_id", "sequence", name="uq_knowledge_chunk_sequence"
        ),
        CheckConstraint("token_count > 0", name="ck_knowledge_chunk_tokens"),
    ),
)
KnowledgeChunkNodeEntity = entity(
    "KnowledgeChunkNodeEntity",
    "knowledge_chunk_nodes",
    dict(
        chunk_id=ref("knowledge_chunks.chunk_id", primary=True),
        structure_node_id=ref("knowledge_structure_nodes.structure_node_id", primary=True),
    ),
)
KnowledgeIngestionRunEntity = entity(
    "KnowledgeIngestionRunEntity",
    "knowledge_ingestion_runs",
    dict(
        ingestion_run_id=ident(),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        idempotency_key=col(String(160)),
        request_hash=col(String(64)),
        input_json=col(JSON),
        audit_json=col(JSON, default=dict),
        error_code=col(String(80), nullable=True),
        outbox_event_id=ref("registry_sync_events.registry_sync_event_id"),
    ),
    (
        UniqueConstraint(
            "tenant_id",
            "knowledge_version_id",
            "idempotency_key",
            name="uq_knowledge_ingestion_idempotency",
        ),
    ),
)
KnowledgeQualityResultEntity = entity(
    "KnowledgeQualityResultEntity",
    "knowledge_quality_results",
    dict(
        quality_id=ident(),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        checks_json=col(JSON),
        reason_codes_json=col(JSON),
    ),
    (UniqueConstraint("knowledge_version_id", name="uq_knowledge_quality_version"),),
)
KnowledgeTranslationEntity = entity(
    "KnowledgeTranslationEntity",
    "knowledge_translations",
    dict(
        translation_id=ident(),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        source_language=col(String(80)),
        target_language=col(String(80)),
        translated_text_ref=col(String(500)),
        translation_method=col(String(40)),
        model_config_id=ref("model_deployments.model_deployment_id", nullable=True),
        reviewer=col(String(160), nullable=True),
        review_status=col(String(40), default="PENDING"),
        provenance_json=col(JSON),
        version=col(Integer, default=1),
    ),
    (
        CheckConstraint(
            "review_status <> 'APPROVED' OR reviewer IS NOT NULL", name="ck_translation_reviewer"
        ),
    ),
)
KnowledgeIndexVersionEntity = entity(
    "KnowledgeIndexVersionEntity",
    "knowledge_index_versions",
    dict(
        index_version_id=ident(),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        chunking_strategy_version=col(String(80)),
        embedding_config_id=ref("model_deployments.model_deployment_id", nullable=True),
        fts_config_version=col(String(80)),
        build_status=col(String(40)),
        built_at=col(DateTime(timezone=True), default=utcnow),
        content_hash=col(String(64)),
        derived=col(Boolean, default=True),
    ),
)
EmbeddingJobEntity = entity(
    "EmbeddingJobEntity",
    "embedding_jobs",
    dict(
        embedding_job_id=ident(),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        model_config_id=ref("model_deployments.model_deployment_id"),
    ),
)
EmbeddingRecordEntity = entity(
    "EmbeddingRecordEntity",
    "embedding_records",
    dict(
        embedding_record_id=ident(),
        embedding_job_id=ref("embedding_jobs.embedding_job_id"),
        chunk_id=ref("knowledge_chunks.chunk_id"),
        model_config_id=ref("model_deployments.model_deployment_id"),
        embedding_dimension=col(Integer),
        embedding_version=col(String(80)),
        vector_hash=col(String(64)),
        generated_at=col(DateTime(timezone=True), default=utcnow),
    ),
    (
        UniqueConstraint(
            "tenant_id",
            "chunk_id",
            "model_config_id",
            "embedding_version",
            name="uq_embedding_record_version",
        ),
        CheckConstraint("embedding_dimension > 0", name="ck_embedding_dimension"),
    ),
)
KnowledgeChangeEventEntity = entity(
    "KnowledgeChangeEventEntity",
    "knowledge_change_events",
    dict(
        event_id=ident(),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        event_type=col(String(80)),
        provenance_json=col(JSON),
    ),
)
KnowledgeVersionDiffEntity = entity(
    "KnowledgeVersionDiffEntity",
    "knowledge_version_diffs",
    dict(
        diff_id=ident(),
        old_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        new_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        changes_json=col(JSON),
    ),
)
KnowledgeScopeResolutionEntity = entity(
    "KnowledgeScopeResolutionEntity",
    "knowledge_scope_resolutions",
    dict(
        resolution_id=ident(),
        project_id=ref("projects.project_id"),
        analysis_snapshot_id=ref("analysis_snapshots.analysis_snapshot_id", nullable=True),
        subject_type=col(String(40)),
        subject_id=col(String(36)),
        scope_json=col(JSON),
        context_json=col(JSON),
    ),
    (
        UniqueConstraint(
            "tenant_id",
            "analysis_snapshot_id",
            "subject_type",
            "subject_id",
            name="uq_snapshot_knowledge_scope",
        ),
    ),
)
