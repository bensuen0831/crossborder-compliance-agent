"""Scope-first retrieval orchestration; provider execution is supplied only through ports."""

from uuid import uuid4

from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
from crossborder_compliance.application.retrieval_algorithms import (
    FallbackGuidanceService,
    HybridMergeStrategy,
    KnowledgeSufficiencyService,
    RerankService,
    RetrievalScopeValidator,
)
from crossborder_compliance.domain.retrieval import (
    EvidencePack,
    KnowledgeRetrievalPolicy,
    KnowledgeSufficiencyPolicy,
    RAGContextPack,
    RetrievalStatistics,
    RetrievalTrace,
    VectorRetrievalResult,
)


class KnowledgeRetrievalService:
    def __init__(
        self, repository, context, lexical, vector, *, embedding=None, reranker=None, external=None
    ):
        self.repository, self.context, self.lexical, self.vector = (
            repository,
            context,
            lexical,
            vector,
        )
        self.embedding, self.reranker, self.external = embedding, reranker, external

    def retrieve(self, query):
        repo = self.repository
        scope = KnowledgeScopeResolver(repo, self.context).resolve(
            query.project_id,
            subject_type=query.subject_type,
            subject_id=query.subject_id,
            snapshot_id=query.analysis_snapshot_id,
            languages=query.languages,
        )
        policy = KnowledgeRetrievalPolicy.model_validate(
            repo.resolve_policy("retrieval", query.policy_id, query.analysis_snapshot_id)
        )
        suffpolicy = KnowledgeSufficiencyPolicy.model_validate(
            repo.resolve_policy(
                "sufficiency", policy.sufficiency_policy_id, query.analysis_snapshot_id
            )
        )
        plan = repo.prepare_search(scope, policy)
        run = repo.begin_run(query, policy, plan)
        run_id = run["retrieval_run_id"]
        if run["reused"]:
            return repo.scoped_saved_response(run_id)
        traces = [
            RetrievalTrace(
                stage="SCOPE",
                reason_code="PHASE1F_HARD_FILTERS_APPLIED",
                details={"filter_order": plan.filter_spec.filter_order},
            )
        ]
        try:
            lexical = self.lexical.retrieve(query.query_text, plan)
            vector = VectorRetrievalResult(candidates=())
            if policy.vector_weight:
                if self.embedding is None:
                    raise ValueError("EMBEDDING_PORT_NOT_CONFIGURED")
                cfg = repo.model_config(policy.embedding_config_id, "EMBEDDING")
                embedding = self.embedding.embed(
                    [query.query_text],
                    model_config_id=policy.embedding_config_id,
                    dimension=int(cfg["embedding_dimension"]),
                )
                if len(embedding) != 1 or len(embedding[0]) != int(cfg["embedding_dimension"]):
                    raise ValueError("QUERY_EMBEDDING_DIMENSION_INVALID")
                vector = self.vector.retrieve(tuple(embedding[0]), plan)
            merged = HybridMergeStrategy().merge(lexical, vector, policy)
            candidates = merged.candidates
            rerank_dropped = ()
            if policy.rerank_enabled:
                if self.reranker is None:
                    raise ValueError("RERANKER_PORT_NOT_CONFIGURED")
                if policy.rerank_config_id:
                    repo.model_config(policy.rerank_config_id, "RERANK")
                result = RerankService(self.reranker).rerank(query.query_text, candidates, policy)
                candidates, rerank_dropped = result.candidates, result.dropped
            if policy.graph_expansion_enabled:
                neighbors = repo.graph_neighbors(plan, candidates, policy.graph_expansion_limit)
                existing = {c.chunk_id for c in candidates}
                candidates = candidates + tuple(c for c in neighbors if c.chunk_id not in existing)
                traces.append(
                    RetrievalTrace(
                        stage="GRAPH",
                        reason_code="DERIVED_REVIEWED_GRAPH_ONLY",
                        details={"expanded_count": len(neighbors)},
                    )
                )
            # Resolve again against immutable snapshot and current revocations after adapters ran.
            current = KnowledgeScopeResolver(repo, self.context).resolve(
                query.project_id,
                subject_type=query.subject_type,
                subject_id=query.subject_id,
                snapshot_id=query.analysis_snapshot_id,
                languages=query.languages,
            )
            plan = repo.prepare_search(current, policy)
            validation = RetrievalScopeValidator(repo).validate(candidates, plan)
            allowed = set(validation.allowed_chunk_ids)
            selected = tuple(c for c in candidates if c.chunk_id in allowed)[: policy.top_k]
            traces.append(
                RetrievalTrace(
                    stage="REVALIDATION",
                    reason_code=validation.status,
                    details={"dropped": list(rerank_dropped + validation.dropped)},
                )
            )
            items = repo.internal_evidence(run_id, plan, selected)
            pack = EvidencePack(
                evidence_pack_id=str(uuid4()),
                retrieval_run_id=run_id,
                analysis_snapshot_id=query.analysis_snapshot_id,
                items=items,
                manifest={
                    "retrieval_policy_version": policy.policy_version_id,
                    "sufficiency_policy_version": suffpolicy.policy_version_id,
                    "scope_version": current.version,
                    "knowledge_indexes": plan.index_versions,
                    "embedding_record_ids": plan.embedding_record_ids,
                    "derived": True,
                    "external_artifacts": [],
                },
            )
            suff = KnowledgeSufficiencyService().assess(pack, current, suffpolicy)
            external_meta = {"attempted": False, "reason_codes": []}
            if policy.external_augmentation_enabled and suff.status in (
                "PARTIALLY_SUFFICIENT",
                "INSUFFICIENT",
            ):
                if self.external is None:
                    external_meta = {
                        "attempted": False,
                        "reason_codes": ["EXTERNAL_PORT_NOT_CONFIGURED"],
                    }
                else:
                    extra = self.external.augment(query, plan, suff, suffpolicy)
                    extitems = repo.external_items(run_id, policy.policy_version_id, extra.records)
                    manifest = dict(
                        pack.manifest,
                        external_artifacts=[
                            {
                                "external_evidence_id": r.external_evidence_id,
                                "content_hash": r.content_hash,
                                "parsed_artifact_version": r.parsed_artifact_version,
                                "retrieved_at": r.retrieved_at.isoformat(),
                                "trusted_source_policy_version": r.trusted_source_policy_version,
                            }
                            for r in extra.records
                        ],
                    )
                    pack = pack.model_copy(update={"items": items + extitems, "manifest": manifest})
                    suff = KnowledgeSufficiencyService().assess(pack, current, suffpolicy)
                    external_meta = {
                        "attempted": True,
                        "validations": [v.model_dump(mode="json") for v in extra.validations],
                        "reason_codes": extra.reason_codes,
                    }
            rag = RAGContextPack(
                structured_context=repo.retrieval_context(current),
                scope=current,
                evidence_pack=pack,
                knowledge_sufficiency=suff,
                external_augmentation_metadata=external_meta,
                fallback_guidance_context=FallbackGuidanceService().build(suff, suffpolicy),
            )
            statistics = RetrievalStatistics(
                lexical_count=len(lexical.candidates),
                vector_count=len(vector.candidates),
                deduplicated_count=len(merged.candidates),
                reranked_count=len(candidates) if policy.rerank_enabled else 0,
                dropped_count=len(rerank_dropped) + len(validation.dropped),
                internal_evidence_count=len(items),
                external_evidence_count=len(pack.items) - len(items),
            )
            return repo.complete_run(run_id, rag, tuple(traces), statistics)
        except Exception:
            repo.fail_run(run_id, "RETRIEVAL_EXECUTION_FAILED")
            raise
