"""Exact scoped PostgreSQL retrieval over Phase 1F derived indexes."""

import json
import math

from sqlalchemy import bindparam, text

from crossborder_compliance.domain.retrieval import (
    LexicalRetrievalResult,
    RetrievalCandidate,
    VectorRetrievalResult,
)

# Materialization prevents global ranking before tenant/permission/version filtering.
HARD_FILTER_CTE = """
WITH filtered AS MATERIALIZED (
 SELECT c.chunk_id,c.knowledge_version_id,c.search_vector,
        i.index_version_id,i.embedding_config_id
 FROM knowledge_chunks c
 JOIN knowledge_document_versions v ON v.knowledge_version_id=c.knowledge_version_id
 JOIN knowledge_documents d ON d.document_id=v.document_id
 JOIN knowledge_source_definitions s ON s.knowledge_source_definition_id=d.source_id
 JOIN knowledge_index_versions i ON i.knowledge_version_id=v.knowledge_version_id
 JOIN knowledge_runtime_publications r ON r.knowledge_version_id=v.knowledge_version_id
 WHERE c.tenant_id=:tenant AND v.tenant_id=:tenant AND d.tenant_id=:tenant
   AND s.tenant_id=:tenant AND i.tenant_id=:tenant
   AND c.status='ACTIVE' AND v.status='ACTIVE' AND d.status='ACTIVE' AND s.status='ACTIVE'
   AND c.knowledge_version_id IN :versions AND i.index_version_id IN :indexes
   AND v.lifecycle IN :statuses AND v.approved_by IS NOT NULL
   AND (v.effective_from IS NULL OR v.effective_from<=:as_of)
   AND (v.effective_to IS NULL OR v.effective_to>=:as_of)
   AND s.config_json->>'enabled'='true' AND s.config_json->>'validation_status'='VALIDATED'
   AND s.config_json->>'source_type' IN :source_types
   AND r.tenant_id=:tenant AND r.status='READY' AND i.index_version_id=r.index_version_id
   AND i.build_status='BUILT' AND i.derived=true
   AND i.fts_config_version='postgres-simple-v1'
   AND (:any_language OR c.language IN :languages)
   AND EXISTS (SELECT 1 FROM knowledge_quality_results q
      WHERE q.tenant_id=:tenant AND q.knowledge_version_id=v.knowledge_version_id
        AND q.status='PASS')
   AND EXISTS (SELECT 1 FROM knowledge_bindings b
      WHERE b.tenant_id=:tenant AND b.knowledge_version_id=v.knowledge_version_id
        AND b.knowledge_binding_id IN :bindings AND b.review_status='APPROVED' AND b.status='ACTIVE'
        AND (b.effective_from IS NULL OR b.effective_from<=:as_of)
        AND (b.effective_to IS NULL OR b.effective_to>=:as_of)
        AND (:system_actor OR CAST(b.permission_scopes_json AS jsonb)
                                    <@ CAST(:permissions AS jsonb)))
)
"""


class ScopedPostgresSearch:
    def __init__(self, sessions, context):
        self.sessions, self.context = sessions, context

    def execute(self, suffix, plan, **extra):
        if plan.scope.tenant_id != str(self.context.tenant_id):
            raise PermissionError("foreign retrieval scope")
        if not plan.index_versions or not plan.filter_spec.binding_filter:
            return []
        params = dict(
            tenant=str(self.context.tenant_id),
            versions=tuple(plan.index_versions),
            indexes=tuple(plan.index_versions.values()),
            statuses=plan.policy.allowed_statuses,
            as_of=plan.scope.effective_as_of,
            source_types=plan.policy.allowed_knowledge_types,
            any_language=not plan.languages,
            languages=plan.languages or ("",),
            bindings=plan.filter_spec.binding_filter,
            permissions=json.dumps(sorted(self.context.permission.scopes)),
            system_actor=self.context.permission.system,
            **extra,
        )
        query = text(HARD_FILTER_CTE + suffix)
        arrays = ["versions", "indexes", "statuses", "source_types", "languages", "bindings"]
        arrays.extend(key for key in ("record_ids", "chunk_ids") if key in extra)
        query = query.bindparams(*(bindparam(key, expanding=True) for key in arrays))
        with self.sessions() as session:
            return session.execute(query, params).mappings().all()

    def eligible_chunk_ids(self, plan, ids):
        if not ids:
            return ()
        rows = self.execute(
            "SELECT chunk_id FROM filtered WHERE chunk_id IN :chunk_ids ORDER BY chunk_id",
            plan,
            chunk_ids=ids,
        )
        return tuple(row["chunk_id"] for row in rows)


class PostgresFTSRetrieverAdapter(ScopedPostgresSearch):
    def retrieve(self, query_text, plan):
        rows = self.execute(
            "SELECT chunk_id,knowledge_version_id,index_version_id, "
            "ts_rank_cd(search_vector,plainto_tsquery('simple',:query)) AS score "
            "FROM filtered WHERE search_vector @@ plainto_tsquery('simple',:query) "
            "ORDER BY score DESC,chunk_id ASC LIMIT :limit",
            plan,
            query=query_text,
            limit=plan.policy.candidate_limit,
        )
        return LexicalRetrievalResult(
            candidates=tuple(
                RetrievalCandidate(
                    chunk_id=r["chunk_id"],
                    knowledge_version_id=r["knowledge_version_id"],
                    index_version_id=r["index_version_id"],
                    lexical_score=float(r["score"]),
                    channels=("LEXICAL",),
                )
                for r in rows
            )
        )


class PgvectorRetrieverAdapter(ScopedPostgresSearch):
    def retrieve(self, vector, plan):
        if not vector or not all(math.isfinite(v) for v in vector) or not any(vector):
            raise ValueError("nonzero finite query embedding required")
        if not plan.embedding_record_ids:
            return VectorRetrievalResult(candidates=())
        rows = self.execute(
            ",vectors AS MATERIALIZED (SELECT f.*,e.embedding_vector FROM filtered f "
            "JOIN embedding_records e ON e.chunk_id=f.chunk_id "
            "AND e.model_config_id=f.embedding_config_id "
            "WHERE e.tenant_id=:tenant AND e.embedding_record_id IN :record_ids "
            "AND e.status='GENERATED' AND e.embedding_vector IS NOT NULL "
            "AND e.embedding_dimension=:dimension AND vector_norm(e.embedding_vector)>0) "
            "SELECT chunk_id,knowledge_version_id,index_version_id, "
            "1-(embedding_vector <=> CAST(:vector AS vector)) AS score FROM vectors "
            "ORDER BY embedding_vector <=> CAST(:vector AS vector),chunk_id ASC LIMIT :limit",
            plan,
            record_ids=plan.embedding_record_ids,
            dimension=len(vector),
            vector=json.dumps(vector),
            limit=plan.policy.candidate_limit,
        )
        return VectorRetrievalResult(
            candidates=tuple(
                RetrievalCandidate(
                    chunk_id=r["chunk_id"],
                    knowledge_version_id=r["knowledge_version_id"],
                    index_version_id=r["index_version_id"],
                    vector_score=float(r["score"]),
                    channels=("VECTOR",),
                )
                for r in rows
            )
        )
