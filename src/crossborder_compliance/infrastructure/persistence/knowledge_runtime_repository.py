"""Runtime publication barrier, reusing canonical indexes and registry outbox."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text

from crossborder_compliance.domain.retrieval import KnowledgeRuntimeReadinessResult
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.retrieval_navigation import (
    PostgresRetrievalNavigationRepository,
)


def stable_id(*parts):
    return str(uuid5(NAMESPACE_URL, ":".join(parts)))


class KnowledgeRuntimeRepository(PostgresRetrievalNavigationRepository):
    def claim_publication(self, event):
        version_id = str(event["version_id"])
        with self.sessions() as s, s.begin():
            version = self.get(s, k.KnowledgeDocumentVersionEntity, version_id, True)
            eventrow = self.get(
                s, m.RegistrySyncEventEntity, str(event["registry_sync_event_id"]), True
            )
            if (
                eventrow.object_kind != "KNOWLEDGE_VERSION_PUBLISHED"
                or eventrow.version_id != version_id
                or (
                    version.document_id != str(event["object_id"])
                    or eventrow.event_version != version.version
                    or int(event["event_version"]) != version.version
                )
            ):
                raise ValueError("invalid publication event version")
            state = s.get(g.KnowledgeRuntimePublicationEntity, version_id)
            if state and state.tenant_id != self.tenant_id:
                raise PermissionError("foreign runtime publication")
            if state and state.status == "READY":
                return {"completed": True}
            # A superseded, not-yet-built event is not allowed to replace the newer runtime.
            if version.lifecycle != "ACTIVE" or not version.approved_by:
                return {"completed": True}
            if state is None or state.status == "PENDING":
                policies = self.rows(
                    s,
                    g.POLICY_MODELS["retrieval"],
                    g.POLICY_MODELS["retrieval"].lifecycle == "ACTIVE",
                )
                # Ambiguous configuration fails closed instead of arbitrarily choosing a model.
                configs = {
                    p.payload_json.get("embedding_config_id")
                    for p in policies
                    if p.payload_json.get("vector_weight")
                }
                if len(configs) > 1:
                    raise ValueError("ambiguous runtime embedding config")
                config = next(iter(configs), None)
                selected = next(
                    (
                        p
                        for p in sorted(policies, key=lambda x: x.policy_version_id)
                        if p.payload_json.get("embedding_config_id") == config
                    ),
                    None,
                )
                if state is None:
                    state = g.KnowledgeRuntimePublicationEntity(
                        tenant_id=self.tenant_id,
                        knowledge_version_id=version_id,
                        publication_event_id=eventrow.registry_sync_event_id,
                        event_version=version.version,
                        status="PENDING",
                    )
                    s.add(state)
                state.policy_version_id = selected.policy_version_id if selected else None
                state.embedding_config_id = config
            state.status = "BUILDING"
            state.reason_codes_json = []
            state.record_version = (state.record_version or 0) + 1
            return dict(
                completed=False,
                knowledge_version_id=version_id,
                document_id=version.document_id,
                embedding_config_id=state.embedding_config_id,
                event_version=version.version,
            )

    def materialize_graph(self, version_id):
        with self.sessions() as s, s.begin():
            version = self.get(s, k.KnowledgeDocumentVersionEntity, version_id)
            doc = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
            source = self.source(doc.source_id)
            nodes = self.rows(
                s,
                k.KnowledgeStructureNodeEntity,
                k.KnowledgeStructureNodeEntity.knowledge_version_id == version_id,
            )
            count = 0
            for node in nodes:
                citation = self.get(s, b.CitationEntity, node.citation_id)
                for jurisdiction in source.get("jurisdiction_refs", ()):
                    ident = stable_id(
                        self.tenant_id,
                        version_id,
                        node.structure_node_id,
                        jurisdiction,
                        "runtime-graph",
                    )
                    if s.get(g.GRAPH_MODELS["node"], ident):
                        count += 1
                        continue
                    payload = dict(
                        graph_node_id=ident,
                        node_type="CANONICAL_STRUCTURE",
                        display_name=node.canonical_locator,
                        source_knowledge_id=doc.document_id,
                        source_knowledge_version_id=version_id,
                        source_evidence_id=citation.evidence_id,
                        jurisdiction_id=jurisdiction,
                        effective_from=version.effective_from.isoformat()
                        if version.effective_from
                        else None,
                        effective_to=version.effective_to.isoformat()
                        if version.effective_to
                        else None,
                        confidence=1,
                        status="ACTIVE",
                        generated_by="publication-worker",
                        reviewed_by=version.approved_by,
                        version=version.version,
                        derived=True,
                        legal_applicability=False,
                    )
                    # Exact projection inherits canonical human review; no inferred applicability.
                    s.add(
                        g.GRAPH_MODELS["node"](
                            tenant_id=self.tenant_id,
                            graph_node_id=ident,
                            source_knowledge_id=doc.document_id,
                            source_knowledge_version_id=version_id,
                            source_evidence_id=citation.evidence_id,
                            jurisdiction_id=jurisdiction,
                            payload_json=payload,
                            generated_by="publication-worker",
                            reviewed_by=version.approved_by,
                            review_task_id=version.review_task_id,
                            status="ACTIVE",
                        )
                    )
                    count += 1
            return dict(source_version_id=version_id, node_count=count, derived=True)

    def finish_publication(self, version_id, index, projection, generation, graph):
        with self.sessions() as s, s.begin():
            state = self.get(s, g.KnowledgeRuntimePublicationEntity, version_id, True)
            version = self.get(s, k.KnowledgeDocumentVersionEntity, version_id)
            target = self.get(s, k.KnowledgeIndexVersionEntity, index["index_version_id"])
            chunks = self.rows(
                s, k.KnowledgeChunkEntity, k.KnowledgeChunkEntity.knowledge_version_id == version_id
            )
            chunk_ids = [c.chunk_id for c in chunks]
            checks = dict(
                approved=bool(version.approved_by),
                fts=bool(chunks)
                and s.scalar(
                    text(
                        "SELECT count(*) FROM knowledge_chunks "
                        "WHERE knowledge_version_id=:v AND tenant_id=:t "
                        "AND search_vector IS NOT NULL"
                    ),
                    {"v": version_id, "t": self.tenant_id},
                )
                == len(chunks),
                index=target.build_status == "BUILT"
                and target.derived
                and target.knowledge_version_id == version_id,
                embedding_config=target.embedding_config_id == state.embedding_config_id,
                graph=graph["source_version_id"] == version_id,
                registry=bool(projection),
                cache=bool(generation),
            )
            if state.embedding_config_id:
                rows = self.rows(
                    s,
                    k.EmbeddingRecordEntity,
                    k.EmbeddingRecordEntity.chunk_id.in_(chunk_ids),
                    k.EmbeddingRecordEntity.model_config_id == state.embedding_config_id,
                    k.EmbeddingRecordEntity.status == "GENERATED",
                )
                vectors = s.scalar(
                    text(
                        "SELECT count(*) FROM embedding_records WHERE tenant_id=:t "
                        "AND model_config_id=:config AND chunk_id IN "
                        "(SELECT chunk_id FROM knowledge_chunks "
                        "WHERE knowledge_version_id=:v) AND embedding_vector IS NOT NULL"
                    ),
                    {"t": self.tenant_id, "v": version_id, "config": state.embedding_config_id},
                )
                checks["vector"] = len(rows) == len(chunks) and vectors == len(chunks)
            if not all(checks.values()):
                raise ValueError("runtime readiness validation failed")
            if state.status == "READY":
                return
            state.index_version_id = target.index_version_id
            state.registry_projection_version = projection
            state.cache_generation = generation
            state.checks_json = checks
            state.assets_json = dict(
                index_version_id=target.index_version_id,
                embedding_config_id=target.embedding_config_id,
                graph=graph,
                cache_generation=generation,
                publication_version=state.event_version,
            )
            state.status = "READY"
            state.record_version += 1

    def fail_publication(self, version_id, reason):
        with self.sessions() as s, s.begin():
            state = self.get(s, g.KnowledgeRuntimePublicationEntity, version_id, True)
            if state.status != "READY":
                state.status = "FAILED"
                state.reason_codes_json = [reason]
                state.record_version += 1

    def runtime_readiness(self, version_id):
        with self.sessions() as s:
            state = self.get(s, g.KnowledgeRuntimePublicationEntity, version_id)
            return KnowledgeRuntimeReadinessResult(
                knowledge_version_id=version_id,
                tenant_id=self.tenant_id,
                publication_event_id=state.publication_event_id,
                event_version=state.event_version,
                status=state.status,
                index_version_id=state.index_version_id,
                embedding_config_id=state.embedding_config_id,
                registry_projection_version=state.registry_projection_version,
                cache_generation=state.cache_generation,
                checks=state.checks_json,
                assets=state.assets_json,
                reason_codes=tuple(state.reason_codes_json),
                record_version=state.record_version,
            )

    def registry_rows(self):
        with self.sessions() as s:
            return [
                dict(
                    definition_id=v.knowledge_version_id,
                    version_id=v.knowledge_version_id,
                    version_no=v.version,
                )
                for v in self.rows(
                    s,
                    k.KnowledgeDocumentVersionEntity,
                    k.KnowledgeDocumentVersionEntity.lifecycle == "ACTIVE",
                )
            ]

    def publication_lease(self, event):
        import hashlib
        from contextlib import contextmanager

        @contextmanager
        def lease():
            key = int.from_bytes(
                hashlib.sha256((self.tenant_id + str(event["object_id"])).encode()).digest()[:8],
                "big",
                signed=True,
            )
            with self.sessions() as s:
                s.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
                try:
                    yield
                finally:
                    s.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})

        return lease()
