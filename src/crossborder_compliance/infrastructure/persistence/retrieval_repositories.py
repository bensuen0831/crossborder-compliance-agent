"""Tenant-scoped policies and derived evidence; no parallel canonical knowledge store."""

from uuid import uuid4

from sqlalchemy import select

from crossborder_compliance.domain.knowledge import FormalContext
from crossborder_compliance.domain.retrieval import (
    EvidencePackItem,
    KnowledgeRetrievalPolicy,
    KnowledgeSufficiencyPolicy,
    RAGContextPack,
    RetrievalSearchPlan,
    TrustedSourcePolicy,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
    hash_value,
)
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)
from crossborder_compliance.infrastructure.retrieval_search import ScopedPostgresSearch

POLICY_CONTRACTS = {
    "retrieval": KnowledgeRetrievalPolicy,
    "sufficiency": KnowledgeSufficiencyPolicy,
    "trusted_source": TrustedSourcePolicy,
}


class PostgresRetrievalRepository(PostgresKnowledgeRepository):
    def create_policy(self, kind, payload, policy_id=None):
        self.admin()
        model = g.POLICY_MODELS[kind]
        policy_id = policy_id or str(uuid4())
        with self.sessions() as s, s.begin():
            # Serialize versions on tenant; publication locks the same tenant row.
            self.get(s, b.TenantEntity, self.tenant_id, True)
            prior = self.rows(s, model, model.policy_id == policy_id)
            version = max((p.version for p in prior), default=0) + 1
            contract = POLICY_CONTRACTS[kind].model_validate(
                dict(payload, policy_id=policy_id, policy_version_id=str(uuid4()), version=version)
            )
            if kind == "sufficiency":
                for ref in contract.required_topic_refs:
                    self.metadata(s, ref, "KNOWLEDGE_TOPIC")
                for ref in contract.required_regulation_refs:
                    self.metadata(s, ref, "REGULATION_REFERENCE")
            if kind == "trusted_source":
                for rule in contract.source_rules:
                    src = self.get(s, m.KnowledgeSourceDefinitionEntity, rule.source_id)
                    self.metadata(s, rule.authority_ref, "AUTHORITY")
                    if src.config_json.get("authority_ref") != rule.authority_ref:
                        raise ValueError("source authority mismatch")
                    for jurisdiction in rule.jurisdiction_ids:
                        self.get(s, b.JurisdictionEntity, jurisdiction)
                    self.validate_rule_dimensions(s, rule.dimensions)
            if kind == "retrieval":
                self.active_policy(s, "sufficiency", contract.sufficiency_policy_id)
                if contract.trusted_source_policy_id:
                    self.active_policy(s, "trusted_source", contract.trusted_source_policy_id)
            s.add(
                model(
                    tenant_id=self.tenant_id,
                    policy_version_id=contract.policy_version_id,
                    policy_id=policy_id,
                    version=version,
                    payload_json=contract.model_dump(mode="json"),
                )
            )
            return dict(contract.model_dump(mode="json"), lifecycle="DRAFT", record_version=1)

    def active_policy(self, s, kind, policy_id):
        model = g.POLICY_MODELS[kind]
        row = s.scalar(
            select(model).where(
                model.tenant_id == self.tenant_id,
                model.policy_id == policy_id,
                model.lifecycle == "ACTIVE",
            )
        )
        if row is None:
            raise LookupError("active policy not found")
        return row

    def publish_policy(self, kind, version_id, expected):
        self.admin()
        model = g.POLICY_MODELS[kind]
        with self.sessions() as s, s.begin():
            self.get(s, b.TenantEntity, self.tenant_id, True)
            row = self.get(s, model, version_id, True)
            if row.record_version != expected:
                raise OptimisticConcurrencyError("stale policy version")
            if row.lifecycle != "DRAFT":
                raise ValueError("only draft policy may publish")
            for prior in self.rows(
                s, model, model.policy_id == row.policy_id, model.lifecycle == "ACTIVE"
            ):
                prior.lifecycle = "SUPERSEDED"
                prior.record_version += 1
            s.flush()
            row.lifecycle = "ACTIVE"
            row.record_version += 1
            return dict(
                row.payload_json, lifecycle=row.lifecycle, record_version=row.record_version
            )

    def resolve_policy(self, kind, policy_id, snapshot_id):
        model = g.POLICY_MODELS[kind]
        pin_type = "PHASE1G_" + kind.upper() + "_POLICY"
        with self.sessions() as s, s.begin():
            self.get(s, b.AnalysisSnapshotEntity, snapshot_id, True)
            pins = self.rows(
                s,
                m.AnalysisSnapshotRegistryPinEntity,
                m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == snapshot_id,
                m.AnalysisSnapshotRegistryPinEntity.pin_type == pin_type,
                m.AnalysisSnapshotRegistryPinEntity.logical_key == policy_id,
            )
            if pins:
                row = self.get(s, model, pins[0].version_id)
                if row.lifecycle not in ("ACTIVE", "SUPERSEDED"):
                    raise ValueError("pinned policy unavailable")
            else:
                # One retrieval/sufficiency/trust policy family per snapshot prevents bypass.
                existing = self.rows(
                    s,
                    m.AnalysisSnapshotRegistryPinEntity,
                    m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id == snapshot_id,
                    m.AnalysisSnapshotRegistryPinEntity.pin_type == pin_type,
                )
                if existing:
                    raise ValueError("snapshot policy family immutable")
                row = self.active_policy(s, kind, policy_id)
                s.add(
                    m.AnalysisSnapshotRegistryPinEntity(
                        pin_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        analysis_snapshot_id=snapshot_id,
                        pin_type=pin_type,
                        logical_key=policy_id,
                        object_id=policy_id,
                        version_id=row.policy_version_id,
                        version_no=row.version,
                    )
                )
            return row.payload_json

    def prepare_search(self, scope, policy):
        if not scope.analysis_snapshot_id:
            raise ValueError("retrieval requires immutable snapshot")
        with self.sessions() as s:
            pins = self.rows(
                s,
                m.AnalysisSnapshotRegistryPinEntity,
                m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id
                == scope.analysis_snapshot_id,
                m.AnalysisSnapshotRegistryPinEntity.pin_type == "KNOWLEDGE_INDEX_VERSION",
            )
            candidates = []
            for pin in pins:
                index = self.get(s, k.KnowledgeIndexVersionEntity, pin.version_id)
                if (
                    index.knowledge_version_id in scope.filter_spec.version_filter
                    and (
                        index.embedding_config_id == policy.embedding_config_id
                        or not policy.vector_weight
                    )
                    and index.build_status == "BUILT"
                ):
                    candidates.append(index)
            indexes = {}
            records = []
            for index in sorted(candidates, key=lambda i: i.index_version_id):
                if index.knowledge_version_id in indexes:
                    continue
                indexes[index.knowledge_version_id] = index.index_version_id
                if index.embedding_config_id:
                    cfg = self.get(s, m.ModelDeploymentEntity, index.embedding_config_id)
                    cfgpins = self.rows(
                        s,
                        m.AnalysisSnapshotRegistryPinEntity,
                        m.AnalysisSnapshotRegistryPinEntity.analysis_snapshot_id
                        == scope.analysis_snapshot_id,
                        m.AnalysisSnapshotRegistryPinEntity.pin_type == "EMBEDDING_CONFIG_VERSION",
                        m.AnalysisSnapshotRegistryPinEntity.version_id == cfg.model_deployment_id,
                    )
                    if not cfgpins or cfg.record_version != cfgpins[0].version_no:
                        raise ValueError("embedding config pin changed")
                    chunkids = [
                        r.chunk_id
                        for r in self.rows(
                            s,
                            k.KnowledgeChunkEntity,
                            k.KnowledgeChunkEntity.knowledge_version_id
                            == index.knowledge_version_id,
                        )
                    ]
                    records.extend(
                        r.embedding_record_id
                        for r in self.rows(
                            s,
                            k.EmbeddingRecordEntity,
                            k.EmbeddingRecordEntity.chunk_id.in_(chunkids),
                            k.EmbeddingRecordEntity.model_config_id == index.embedding_config_id,
                            k.EmbeddingRecordEntity.generated_at <= index.built_at,
                            k.EmbeddingRecordEntity.status == "GENERATED",
                        )
                    )
        languages = scope.filter_spec.language_filter
        if policy.allowed_languages:
            languages = tuple(
                x for x in (languages or policy.allowed_languages) if x in policy.allowed_languages
            )
            if not languages:
                languages = ("__NO_ALLOWED_LANGUAGE__",)
        return RetrievalSearchPlan(
            scope=scope,
            filter_spec=scope.filter_spec,
            policy=policy,
            index_versions=indexes,
            embedding_record_ids=tuple(sorted(records)),
            languages=languages,
        )

    def eligible_chunk_ids(self, plan, ids):
        return ScopedPostgresSearch(self.sessions, self.context).eligible_chunk_ids(plan, ids)

    def retrieval_context(self, scope):
        data = self.saved_scope(
            scope.project_id, scope.subject_type, scope.subject_id, scope.analysis_snapshot_id
        )
        return FormalContext.model_validate(data["formal_context"])

    def begin_run(self, query, policy, plan):
        with self.sessions() as s, s.begin():
            self.get(s, b.ProjectEntity, query.project_id, True)
            rows = self.rows(
                s,
                g.RetrievalRunEntity,
                g.RetrievalRunEntity.project_id == query.project_id,
                g.RetrievalRunEntity.idempotency_key == query.idempotency_key,
            )
            request_hash = hash_value(query.model_dump(mode="json"))
            if rows:
                row = rows[0]
                if row.owner_actor_id != self.context.permission.actor_id:
                    raise PermissionError("retrieval belongs to another actor")
                if row.request_hash != request_hash:
                    raise OptimisticConcurrencyError("idempotency key payload mismatch")
                if row.status != "COMPLETED":
                    raise OptimisticConcurrencyError("retrieval not completed")
                return dict(retrieval_run_id=row.retrieval_run_id, reused=True)
            row = g.RetrievalRunEntity(
                tenant_id=self.tenant_id,
                retrieval_run_id=str(uuid4()),
                project_id=query.project_id,
                analysis_snapshot_id=query.analysis_snapshot_id,
                policy_version_id=policy.policy_version_id,
                owner_actor_id=self.context.permission.actor_id,
                idempotency_key=query.idempotency_key,
                request_hash=request_hash,
                query_json=query.model_dump(mode="json"),
                plan_json=plan.model_dump(mode="json"),
                status="RUNNING",
            )
            s.add(row)
            return dict(retrieval_run_id=row.retrieval_run_id, reused=False)

    def internal_evidence(self, run_id, plan, candidates):
        allowed = set(self.eligible_chunk_ids(plan, tuple(c.chunk_id for c in candidates)))
        items = []
        with self.sessions() as s:
            for candidate in candidates:
                if candidate.chunk_id not in allowed:
                    continue
                chunk = self.get(s, k.KnowledgeChunkEntity, candidate.chunk_id)
                version = self.get(s, k.KnowledgeDocumentVersionEntity, chunk.knowledge_version_id)
                doc = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
                source = self.get(s, m.KnowledgeSourceDefinitionEntity, doc.source_id).config_json
                nodes = self.rows(
                    s,
                    k.KnowledgeChunkNodeEntity,
                    k.KnowledgeChunkNodeEntity.chunk_id == chunk.chunk_id,
                )
                bindings = self.rows(
                    s,
                    m.KnowledgeBindingEntity,
                    m.KnowledgeBindingEntity.knowledge_binding_id.in_(
                        plan.filter_spec.binding_filter
                    ),
                    m.KnowledgeBindingEntity.knowledge_version_id == version.knowledge_version_id,
                )
                jurisdictions = sorted(
                    {
                        j
                        for binding in bindings
                        for j in binding.dimensions_json.get("jurisdiction", [])
                        if j in plan.scope.allowed_jurisdiction_ids
                    }
                )
                tier = {
                    "OFFICIAL_LEGISLATION": "T1_PRIMARY_OFFICIAL",
                    "OFFICIAL_REGULATOR": "T2_OFFICIAL_GUIDANCE",
                }.get(source["source_type"], "T3_APPROVED_SECONDARY")
                for link in sorted(nodes, key=lambda n: n.structure_node_id):
                    node = self.get(s, k.KnowledgeStructureNodeEntity, link.structure_node_id)
                    citation = self.get(s, b.CitationEntity, node.citation_id)
                    evidence = self.get(s, b.EvidenceReferenceEntity, citation.evidence_id)
                    authority = source.get("authority_ref")
                    if authority:
                        self.metadata(s, authority, "AUTHORITY", plan.scope.effective_as_of)
                    provenance = dict(
                        node.provenance_json,
                        source_evidence_id=evidence.evidence_id,
                        source_hash=source.get("source_hash"),
                        chunking_strategy=chunk.chunking_strategy_version,
                    )
                    for jurisdiction in jurisdictions or [None]:
                        items.append(
                            EvidencePackItem(
                                evidence_item_id=str(uuid4()),
                                knowledge_document_id=doc.document_id,
                                knowledge_version_id=version.knowledge_version_id,
                                structure_node_id=node.structure_node_id,
                                chunk_id=chunk.chunk_id,
                                citation_id=node.citation_id,
                                source_id=doc.source_id,
                                source_url=source.get("canonical_url") or "",
                                source_authority=authority,
                                source_tier=tier,
                                jurisdiction_id=jurisdiction,
                                jurisdiction_specific=bool(jurisdiction),
                                canonical_locator=node.canonical_locator,
                                language=chunk.language,
                                effective_from=version.effective_from,
                                effective_to=version.effective_to,
                                lexical_score=candidate.lexical_score,
                                vector_score=candidate.vector_score,
                                hybrid_score=candidate.hybrid_score,
                                rerank_score=candidate.rerank_score,
                                evidence_quality=1,
                                content_hash=chunk.content_hash,
                                retrieval_run_id=run_id,
                                analysis_snapshot_id=plan.scope.analysis_snapshot_id,
                                knowledge_index_version=candidate.index_version_id,
                                retrieval_policy_version=plan.policy.policy_version_id,
                                original_text=chunk.original_text,
                                topic_refs=tuple(node.provenance_json.get("topic_refs", ())),
                                regulation_refs=tuple(
                                    node.provenance_json.get("regulation_refs", ())
                                ),
                                conflict_key=node.provenance_json.get("conflict_key"),
                                claim_hash=node.provenance_json.get("claim_hash"),
                                provenance=provenance,
                            )
                        )
        return tuple(items)

    def complete_run(self, run_id, rag, traces, statistics):
        with self.sessions() as s, s.begin():
            row = self.get(s, g.RetrievalRunEntity, run_id, True)
            if row.status != "RUNNING":
                raise OptimisticConcurrencyError("retrieval already finalized")
            pack = rag.evidence_pack
            s.add(
                g.EvidencePackEntity(
                    tenant_id=self.tenant_id,
                    evidence_pack_id=pack.evidence_pack_id,
                    retrieval_run_id=run_id,
                    analysis_snapshot_id=pack.analysis_snapshot_id,
                    manifest_json=pack.manifest,
                    context_pack_json=rag.model_dump(mode="json"),
                )
            )
            s.flush()
            for item in pack.items:
                external = bool(item.external_evidence_id)
                s.add(
                    g.EvidencePackItemEntity(
                        tenant_id=self.tenant_id,
                        evidence_item_id=item.evidence_item_id,
                        evidence_pack_id=pack.evidence_pack_id,
                        knowledge_version_id=item.knowledge_version_id,
                        chunk_id=None if external else item.chunk_id,
                        structure_node_id=None if external else item.structure_node_id,
                        external_evidence_id=item.external_evidence_id,
                        citation_id=item.citation_id,
                        payload_json=item.model_dump(mode="json"),
                    )
                )
            suff = rag.knowledge_sufficiency
            s.add(
                g.KnowledgeSufficiencyResultEntity(
                    tenant_id=self.tenant_id,
                    sufficiency_result_id=suff.sufficiency_result_id,
                    evidence_pack_id=pack.evidence_pack_id,
                    policy_version_id=suff.policy_version,
                    result_json=suff.model_dump(mode="json"),
                    status=suff.status,
                )
            )
            row.status = "COMPLETED"
            row.record_version += 1
            row.traces_json = [t.model_dump(mode="json") for t in traces]
            row.statistics_json = statistics.model_dump(mode="json")
        return self.scoped_saved_response(run_id)

    def fail_run(self, run_id, reason_code):
        with self.sessions() as s, s.begin():
            row = self.get(s, g.RetrievalRunEntity, run_id, True)
            row.status = "FAILED"
            row.error_code = reason_code
            row.record_version += 1

    def saved_response(self, run_id):
        with self.sessions() as s:
            row = self.get(s, g.RetrievalRunEntity, run_id)
            if row.owner_actor_id != self.context.permission.actor_id:
                raise PermissionError("retrieval belongs to another actor")
            packs = self.rows(
                s, g.EvidencePackEntity, g.EvidencePackEntity.retrieval_run_id == run_id
            )
            return dict(
                retrieval_run_id=run_id,
                status=row.status,
                query=row.query_json,
                traces=row.traces_json,
                statistics=row.statistics_json,
                record_version=row.record_version,
                rag_context_pack=packs[0].context_pack_json if packs else None,
            )

    def scoped_saved_response(self, run_id):
        from crossborder_compliance.application.knowledge_services import KnowledgeScopeResolver
        from crossborder_compliance.application.retrieval_algorithms import (
            FallbackGuidanceService,
            KnowledgeSufficiencyService,
        )

        response = self.saved_response(run_id)
        if response["rag_context_pack"] is None:
            return response
        rag = RAGContextPack.model_validate(response["rag_context_pack"])
        q = response["query"]
        scope = KnowledgeScopeResolver(self, self.context).resolve(
            q["project_id"],
            subject_type=q["subject_type"],
            subject_id=q["subject_id"],
            snapshot_id=q["analysis_snapshot_id"],
            languages=tuple(q["languages"]),
        )
        policy = KnowledgeRetrievalPolicy.model_validate(
            self.resolve_policy("retrieval", q["policy_id"], q["analysis_snapshot_id"])
        )
        plan = self.prepare_search(scope, policy)
        allowed = set(
            self.eligible_chunk_ids(
                plan,
                tuple(i.chunk_id for i in rag.evidence_pack.items if not i.external_evidence_id),
            )
        )
        items = tuple(
            i
            for i in rag.evidence_pack.items
            if i.chunk_id in allowed or (i.external_evidence_id and self.external_visible(i, scope))
        )
        pack = rag.evidence_pack.model_copy(update={"items": items})
        suffpolicy = KnowledgeSufficiencyPolicy.model_validate(
            self.resolve_policy(
                "sufficiency", policy.sufficiency_policy_id, scope.analysis_snapshot_id
            )
        )
        suff = KnowledgeSufficiencyService().assess(pack, scope, suffpolicy)
        suff = suff.model_copy(
            update={"sufficiency_result_id": rag.knowledge_sufficiency.sufficiency_result_id}
        )
        fallback = FallbackGuidanceService().build(suff, suffpolicy)
        # Excluded objects and request-private trace details are never rendered as evidence.
        response["rag_context_pack"] = rag.model_copy(
            update={
                "scope": scope,
                "evidence_pack": pack,
                "knowledge_sufficiency": suff,
                "fallback_guidance_context": fallback,
            }
        ).model_dump(mode="json")
        return response

    def source(self, source_id):
        with self.sessions() as s:
            row = self.get(s, m.KnowledgeSourceDefinitionEntity, source_id)
            data = dict(row.config_json)
            if (
                row.status != "ACTIVE"
                or not data.get("enabled")
                or data.get("validation_status") != "VALIDATED"
            ):
                raise PermissionError("source unavailable")
            return data

    def validate_rule_dimensions(self, s, dimensions):
        from crossborder_compliance.domain.knowledge import DIMENSIONS

        for dimension, refs in dimensions.items():
            if dimension not in DIMENSIONS:
                raise ValueError("unknown binding dimension")
            for ref in refs:
                if dimension == "jurisdiction":
                    self.get(s, b.JurisdictionEntity, ref)
                else:
                    self.metadata(s, ref, dimension.upper())

    def model_config(self, config_id, capability):
        from datetime import date

        from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
            effective,
        )
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
                model_definition_id=model.model_definition_id, capability=capability
            )
            provider = self.get(s, m.ModelProviderVersionEntity, config.provider_version_id)
            caps = self.rows(
                s,
                m.ModelCapabilityEntity,
                m.ModelCapabilityEntity.model_definition_id == model.model_definition_id,
                m.ModelCapabilityEntity.capability == capability,
                m.ModelCapabilityEntity.status == "ACTIVE",
            )
            if (
                not resolved
                or not caps
                or not effective(config, date.today())
                or not effective(provider, date.today())
                or model.active_deployment_id != config_id
            ):
                raise ValueError("model unavailable from Phase 1C registry")
            return caps[0].metadata_json

    def validate_external_metadata(self, payload):
        with self.sessions() as s:
            self.metadata(s, payload["authority_ref"], "AUTHORITY")
            for node in payload["nodes"]:
                for ref in node.get("topic_refs", ()):
                    self.metadata(s, ref, "KNOWLEDGE_TOPIC")
                for ref in node.get("regulation_refs", ()):
                    self.metadata(s, ref, "REGULATION_REFERENCE")

    def external_candidate(self, run_id, candidate, validation):
        with self.sessions() as s, s.begin():
            self.get(s, g.RetrievalRunEntity, run_id)
            self.get(s, m.KnowledgeSourceDefinitionEntity, candidate.source_id)
            s.add(
                g.ExternalEvidenceCandidateEntity(
                    tenant_id=self.tenant_id,
                    candidate_id=candidate.candidate_id,
                    retrieval_run_id=run_id,
                    source_id=candidate.source_id,
                    payload_json=candidate.model_dump(mode="json"),
                )
            )
            s.flush()
            s.add(
                g.ExternalEvidenceValidationEntity(
                    tenant_id=self.tenant_id,
                    validation_result_id=str(uuid4()),
                    candidate_id=candidate.candidate_id,
                    result_json=validation.model_dump(mode="json"),
                    status=validation.status,
                )
            )

    def saved_external(self, snapshot_id, source_id, trusted_policy_version):
        from crossborder_compliance.domain.retrieval import RuntimeVerifiedExternalEvidence

        with self.sessions() as s:
            rows = self.rows(
                s,
                g.RuntimeExternalEvidenceEntity,
                g.RuntimeExternalEvidenceEntity.analysis_snapshot_id == snapshot_id,
                g.RuntimeExternalEvidenceEntity.source_id == source_id,
                g.RuntimeExternalEvidenceEntity.trusted_policy_version_id == trusted_policy_version,
            )
            if not rows:
                return None
            return RuntimeVerifiedExternalEvidence.model_validate(rows[0].payload_json)

    def persist_external(self, run_id, candidate, raw_content, payload, validation):
        import hashlib

        from crossborder_compliance.domain.retrieval import RuntimeVerifiedExternalEvidence

        with self.sessions() as s, s.begin():
            self.get(s, b.AnalysisSnapshotEntity, payload.analysis_snapshot_id, True)
            self.get(s, g.RetrievalRunEntity, run_id)
            self.get(s, m.KnowledgeSourceDefinitionEntity, payload.source_id)
            prior = self.rows(
                s,
                g.RuntimeExternalEvidenceEntity,
                g.RuntimeExternalEvidenceEntity.analysis_snapshot_id
                == payload.analysis_snapshot_id,
                g.RuntimeExternalEvidenceEntity.source_id == payload.source_id,
                g.RuntimeExternalEvidenceEntity.trusted_policy_version_id
                == payload.trusted_source_policy_version,
            )
            if prior:
                return RuntimeVerifiedExternalEvidence.model_validate(prior[0].payload_json)
            if hashlib.sha256(raw_content).hexdigest() != payload.content_hash:
                raise ValueError("runtime external content hash mismatch")
            s.add(
                g.ExternalEvidenceCandidateEntity(
                    tenant_id=self.tenant_id,
                    candidate_id=candidate.candidate_id,
                    retrieval_run_id=run_id,
                    source_id=candidate.source_id,
                    payload_json=candidate.model_dump(mode="json"),
                )
            )
            s.flush()
            s.add(
                g.ExternalEvidenceValidationEntity(
                    tenant_id=self.tenant_id,
                    validation_result_id=str(uuid4()),
                    candidate_id=candidate.candidate_id,
                    result_json=validation.model_dump(mode="json"),
                    status="VERIFIED",
                )
            )
            nodes = []
            for node in payload.parsed_structure:
                evidence_id, citation_id = str(uuid4()), str(uuid4())
                quote_hash = hashlib.sha256(node["original_text"].encode()).hexdigest()
                s.add(
                    b.EvidenceReferenceEntity(
                        tenant_id=self.tenant_id,
                        evidence_id=evidence_id,
                        evidence_type="RUNTIME_VERIFIED_EXTERNAL",
                        source_ref=payload.source_url,
                        excerpt_hash=quote_hash,
                        validation_status="VALIDATED",
                    )
                )
                s.flush()
                s.add(
                    b.CitationEntity(
                        tenant_id=self.tenant_id,
                        citation_id=citation_id,
                        evidence_id=evidence_id,
                        locator=node["canonical_locator"],
                        quote_hash=quote_hash,
                    )
                )
                nodes.append(dict(node, citation_id=citation_id, evidence_id=evidence_id))
            payload = payload.model_copy(update={"parsed_structure": tuple(nodes)})
            s.add(
                g.RuntimeExternalEvidenceEntity(
                    tenant_id=self.tenant_id,
                    external_evidence_id=payload.external_evidence_id,
                    analysis_snapshot_id=payload.analysis_snapshot_id,
                    source_id=payload.source_id,
                    trusted_policy_version_id=payload.trusted_source_policy_version,
                    retrieval_policy_version_id=payload.retrieval_policy_version,
                    sufficiency_policy_version_id=payload.sufficiency_policy_version,
                    candidate_id=candidate.candidate_id,
                    content_hash=payload.content_hash,
                    original_content=raw_content,
                    payload_json=payload.model_dump(mode="json"),
                    status="VERIFIED",
                )
            )
            self.pin(
                s,
                payload.analysis_snapshot_id,
                "RUNTIME_EXTERNAL_EVIDENCE",
                payload.external_evidence_id,
                1,
            )
            return payload

    def external_items(self, run_id, policy_version, records):
        items = []
        for record in records:
            for node in record.parsed_structure:
                for jurisdiction in record.jurisdiction_ids:
                    items.append(
                        EvidencePackItem(
                            evidence_item_id=str(uuid4()),
                            external_evidence_id=record.external_evidence_id,
                            structure_node_id=node["structure_node_id"],
                            chunk_id=node["chunk_id"],
                            citation_id=node["citation_id"],
                            source_id=record.source_id,
                            source_url=record.canonical_url,
                            source_authority=record.source_authority,
                            source_tier=record.source_tier,
                            jurisdiction_id=jurisdiction,
                            jurisdiction_specific=True,
                            canonical_locator=node["canonical_locator"],
                            language=record.language,
                            effective_from=record.effective_from,
                            effective_to=record.effective_to,
                            evidence_quality=1,
                            content_hash=record.content_hash,
                            retrieval_run_id=run_id,
                            analysis_snapshot_id=record.analysis_snapshot_id,
                            retrieval_policy_version=policy_version,
                            original_text=node["original_text"],
                            topic_refs=tuple(node.get("topic_refs", ())),
                            regulation_refs=tuple(node.get("regulation_refs", ())),
                            conflict_key=node.get("conflict_key"),
                            claim_hash=node.get("claim_hash"),
                            provenance=dict(
                                record.provenance,
                                parsed_artifact_version=record.parsed_artifact_version,
                                retrieved_at=record.retrieved_at.isoformat(),
                                source_evidence_id=node["evidence_id"],
                            ),
                        )
                    )
        return tuple(items)

    def external_visible(self, item, scope):
        from crossborder_compliance.application.external_evidence_services import rule_permits

        try:
            source = self.source(item.source_id)
            with self.sessions() as s:
                ext = self.get(s, g.RuntimeExternalEvidenceEntity, item.external_evidence_id)
                policy = TrustedSourcePolicy.model_validate(
                    self.get(
                        s, g.POLICY_MODELS["trusted_source"], ext.trusted_policy_version_id
                    ).payload_json
                )
                rule = next((r for r in policy.source_rules if r.source_id == item.source_id), None)
                return bool(
                    rule
                    and source.get("authority_ref") == rule.authority_ref
                    and rule_permits(rule, self.retrieval_context(scope), self.context)
                )
        except (PermissionError, LookupError, ValueError):
            return False
