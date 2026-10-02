"""Phase 1G derived stores. Canonical knowledge remains in Phase 1F tables."""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)

from crossborder_compliance.infrastructure.persistence.knowledge_models import (
    col,
    entity,
    ident,
    ref,
)

POLICY_MODELS = {}
for kind in ("retrieval", "sufficiency", "trusted_source"):
    table = {
        "retrieval": "retrieval_policies",
        "sufficiency": "knowledge_sufficiency_policies",
        "trusted_source": "trusted_source_policies",
    }[kind]
    POLICY_MODELS[kind] = entity(
        kind.title().replace("_", "") + "PolicyEntity",
        table,
        dict(
            policy_version_id=ident(),
            policy_id=col(String(36)),
            version=col(Integer),
            lifecycle=col(String(30), default="DRAFT"),
            payload_json=col(JSON),
        ),
        (
            UniqueConstraint(
                "tenant_id", "policy_id", "version", name="uq_" + kind + "_policy_version"
            ),
            CheckConstraint(
                "lifecycle IN ('DRAFT','ACTIVE','SUPERSEDED')", name="ck_" + kind + "_lifecycle"
            ),
            CheckConstraint("version > 0", name="ck_" + kind + "_version"),
        ),
    )

RetrievalRunEntity = entity(
    "RetrievalRunEntity",
    "retrieval_runs",
    dict(
        retrieval_run_id=ident(),
        project_id=ref("projects.project_id"),
        analysis_snapshot_id=ref("analysis_snapshots.analysis_snapshot_id"),
        policy_version_id=ref("retrieval_policies.policy_version_id"),
        owner_actor_id=col(String(160)),
        idempotency_key=col(String(120)),
        request_hash=col(String(64)),
        query_json=col(JSON),
        plan_json=col(JSON),
        traces_json=col(JSON, default=list),
        statistics_json=col(JSON, default=dict),
        error_code=col(String(100), nullable=True),
    ),
    (
        UniqueConstraint(
            "tenant_id", "project_id", "idempotency_key", name="uq_retrieval_idempotency"
        ),
        CheckConstraint(
            "status IN ('RUNNING','COMPLETED','FAILED')", name="ck_retrieval_run_status"
        ),
    ),
)
EvidencePackEntity = entity(
    "EvidencePackEntity",
    "evidence_packs",
    dict(
        evidence_pack_id=ident(),
        retrieval_run_id=ref("retrieval_runs.retrieval_run_id"),
        analysis_snapshot_id=ref("analysis_snapshots.analysis_snapshot_id"),
        manifest_json=col(JSON),
        context_pack_json=col(JSON),
        derived=col(Boolean, default=True),
        legal_source_of_truth=col(Boolean, default=False),
    ),
    (
        UniqueConstraint("retrieval_run_id", name="uq_retrieval_pack"),
        CheckConstraint("derived AND NOT legal_source_of_truth", name="ck_pack_derived"),
    ),
)
KnowledgeSufficiencyResultEntity = entity(
    "KnowledgeSufficiencyResultEntity",
    "knowledge_sufficiency_results",
    dict(
        sufficiency_result_id=ident(),
        evidence_pack_id=ref("evidence_packs.evidence_pack_id"),
        policy_version_id=ref("knowledge_sufficiency_policies.policy_version_id"),
        result_json=col(JSON),
    ),
    (
        UniqueConstraint("evidence_pack_id", name="uq_pack_sufficiency"),
        CheckConstraint(
            "status IN ('SUFFICIENT','PARTIALLY_SUFFICIENT','INSUFFICIENT','CONFLICTED')",
            name="ck_sufficiency_status",
        ),
    ),
)
ExternalEvidenceCandidateEntity = entity(
    "ExternalEvidenceCandidateEntity",
    "external_evidence_candidates",
    dict(
        candidate_id=ident(),
        retrieval_run_id=ref("retrieval_runs.retrieval_run_id"),
        source_id=ref("knowledge_source_definitions.knowledge_source_definition_id"),
        payload_json=col(JSON),
    ),
)
ExternalEvidenceValidationEntity = entity(
    "ExternalEvidenceValidationEntity",
    "external_evidence_validation_results",
    dict(
        validation_result_id=ident(),
        candidate_id=ref("external_evidence_candidates.candidate_id"),
        result_json=col(JSON),
    ),
    (
        CheckConstraint(
            "status IN ('VERIFIED','REJECTED','DISCOVERY_ONLY')", name="ck_external_validation"
        ),
    ),
)
RuntimeExternalEvidenceEntity = entity(
    "RuntimeExternalEvidenceEntity",
    "runtime_verified_external_evidence",
    dict(
        external_evidence_id=ident(),
        analysis_snapshot_id=ref("analysis_snapshots.analysis_snapshot_id"),
        source_id=ref("knowledge_source_definitions.knowledge_source_definition_id"),
        trusted_policy_version_id=ref("trusted_source_policies.policy_version_id"),
        retrieval_policy_version_id=ref("retrieval_policies.policy_version_id"),
        sufficiency_policy_version_id=ref("knowledge_sufficiency_policies.policy_version_id"),
        candidate_id=ref("external_evidence_candidates.candidate_id"),
        content_hash=col(String(64)),
        original_content=col(LargeBinary),
        payload_json=col(JSON),
        active_knowledge=col(Boolean, default=False),
    ),
    (
        UniqueConstraint(
            "tenant_id",
            "analysis_snapshot_id",
            "source_id",
            "trusted_policy_version_id",
            name="uq_snapshot_external_source",
        ),
        CheckConstraint(
            "status='VERIFIED' AND NOT active_knowledge", name="ck_runtime_external_not_active"
        ),
    ),
)
EvidencePackItemEntity = entity(
    "EvidencePackItemEntity",
    "evidence_pack_items",
    dict(
        evidence_item_id=ident(),
        evidence_pack_id=ref("evidence_packs.evidence_pack_id"),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id", nullable=True),
        chunk_id=ref("knowledge_chunks.chunk_id", nullable=True),
        structure_node_id=ref("knowledge_structure_nodes.structure_node_id", nullable=True),
        external_evidence_id=ref(
            "runtime_verified_external_evidence.external_evidence_id", nullable=True
        ),
        citation_id=ref("citations.citation_id"),
        payload_json=col(JSON),
    ),
    (
        CheckConstraint(
            "(knowledge_version_id IS NOT NULL AND chunk_id IS NOT NULL AND "
            "structure_node_id IS NOT NULL AND external_evidence_id IS NULL) OR "
            "(knowledge_version_id IS NULL AND chunk_id IS NULL AND "
            "structure_node_id IS NULL AND external_evidence_id IS NOT NULL)",
            name="ck_evidence_exact_source_chain",
        ),
    ),
)
WikiPageEntity = entity(
    "WikiPageEntity",
    "wiki_pages",
    dict(
        wiki_page_id=ident(),
        title=col(String(250)),
        legal_basis=col(Boolean, default=False),
    ),
    (CheckConstraint("NOT legal_basis", name="ck_wiki_not_legal_basis"),),
)
WikiVersionEntity = entity(
    "WikiVersionEntity",
    "wiki_versions",
    dict(
        wiki_version_id=ident(),
        wiki_page_id=ref("wiki_pages.wiki_page_id"),
        version=col(Integer),
        content=col(Text),
        content_hash=col(String(64)),
        lifecycle=col(String(30), default="DRAFT"),
        generated_by=col(String(160)),
        reviewed_by=col(String(160), nullable=True),
        official_evidence=col(Boolean, default=False),
        legal_basis=col(Boolean, default=False),
    ),
    (
        UniqueConstraint("tenant_id", "wiki_page_id", "version", name="uq_wiki_version"),
        CheckConstraint("NOT official_evidence AND NOT legal_basis", name="ck_wiki_derived"),
        CheckConstraint(
            "lifecycle IN ('DRAFT','VALIDATED','PENDING_REVIEW','APPROVED','ACTIVE','SUPERSEDED')",
            name="ck_wiki_lifecycle",
        ),
        CheckConstraint(
            "lifecycle NOT IN ('APPROVED','ACTIVE') OR (reviewed_by IS NOT NULL "
            "AND reviewed_by<>generated_by)",
            name="ck_wiki_review_boundary",
        ),
    ),
)
WikiSourceBindingEntity = entity(
    "WikiSourceBindingEntity",
    "wiki_source_bindings",
    dict(
        source_binding_id=ident(),
        wiki_version_id=ref("wiki_versions.wiki_version_id"),
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
    ),
    (UniqueConstraint("wiki_version_id", "knowledge_version_id", name="uq_wiki_source"),),
)
WikiCitationEntity = entity(
    "WikiCitationEntity",
    "wiki_citations",
    dict(
        wiki_citation_id=ident(),
        wiki_version_id=ref("wiki_versions.wiki_version_id"),
        citation_id=ref("citations.citation_id"),
    ),
    (UniqueConstraint("wiki_version_id", "citation_id", name="uq_wiki_citation"),),
)
WikiReviewEntity = entity(
    "WikiReviewEntity",
    "wiki_reviews",
    dict(
        wiki_review_id=ident(),
        wiki_version_id=ref("wiki_versions.wiki_version_id"),
        review_task_id=ref("admin_review_tasks.review_task_id"),
        reviewer=col(String(160), nullable=True),
    ),
    (UniqueConstraint("wiki_version_id", name="uq_wiki_review"),),
)
WikiPublishRecordEntity = entity(
    "WikiPublishRecordEntity",
    "wiki_publish_records",
    dict(
        publish_record_id=ident(),
        wiki_version_id=ref("wiki_versions.wiki_version_id"),
        published_by=col(String(160)),
        published_at=col(DateTime(timezone=True)),
    ),
    (UniqueConstraint("wiki_version_id", name="uq_wiki_publish"),),
)
GRAPH_MODELS = {}
for kind in ("node", "edge"):
    fields = dict(
        source_knowledge_id=ref("knowledge_documents.document_id"),
        source_knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id"),
        source_evidence_id=ref("evidence_references.evidence_id"),
        jurisdiction_id=ref("jurisdictions.jurisdiction_id"),
        payload_json=col(JSON),
        generated_by=col(String(160)),
        reviewed_by=col(String(160), nullable=True),
        review_task_id=ref("admin_review_tasks.review_task_id", nullable=True),
        derived=col(Boolean, default=True),
        legal_applicability=col(Boolean, default=False),
    )
    fields["graph_" + kind + "_id"] = ident()
    if kind == "edge":
        fields.update(
            source_node_id=ref("knowledge_graph_nodes.graph_node_id"),
            target_node_id=ref("knowledge_graph_nodes.graph_node_id"),
            relation_type_ref=ref("metadata_definitions.definition_id"),
        )
    GRAPH_MODELS[kind] = entity(
        "KnowledgeGraph" + kind.title() + "Entity",
        "knowledge_graph_" + kind + "s",
        fields,
        (
            CheckConstraint(
                "derived AND NOT legal_applicability", name="ck_graph_" + kind + "_derived"
            ),
            CheckConstraint(
                "status IN ('DRAFT','ACTIVE','ARCHIVED')", name="ck_graph_" + kind + "_status"
            ),
            CheckConstraint(
                "status<>'ACTIVE' OR (reviewed_by IS NOT NULL AND "
                "reviewed_by<>generated_by AND review_task_id IS NOT NULL)",
                name="ck_graph_" + kind + "_review",
            ),
        ),
    )

KnowledgeRuntimePublicationEntity = entity(
    "KnowledgeRuntimePublicationEntity",
    "knowledge_runtime_publications",
    dict(
        knowledge_version_id=ref("knowledge_document_versions.knowledge_version_id", primary=True),
        publication_event_id=ref("registry_sync_events.registry_sync_event_id"),
        event_version=col(Integer),
        policy_version_id=ref("retrieval_policies.policy_version_id", nullable=True),
        index_version_id=ref("knowledge_index_versions.index_version_id", nullable=True),
        embedding_config_id=ref("model_deployments.model_deployment_id", nullable=True),
        registry_projection_version=col(String(64), nullable=True),
        cache_generation=col(String(100), nullable=True),
        checks_json=col(JSON, default=dict),
        assets_json=col(JSON, default=dict),
        reason_codes_json=col(JSON, default=list),
    ),
    (
        UniqueConstraint("publication_event_id", name="uq_runtime_publication_event"),
        CheckConstraint(
            "status IN ('PENDING','BUILDING','READY','FAILED')",
            name="ck_runtime_publication_status",
        ),
        CheckConstraint(
            "status<>'READY' OR (index_version_id IS NOT NULL AND registry_projection_version "
            "IS NOT NULL AND cache_generation IS NOT NULL)",
            name="ck_runtime_ready_barrier",
        ),
    ),
)
