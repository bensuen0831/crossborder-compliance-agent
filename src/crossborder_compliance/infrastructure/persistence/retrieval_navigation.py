"""Reviewed, derived Wiki/Graph projections reuse durable Phase 1C admin review."""

import hashlib
from uuid import uuid4

from crossborder_compliance.domain.retrieval import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    RetrievalCandidate,
)
from crossborder_compliance.infrastructure.persistence import knowledge_models as k
from crossborder_compliance.infrastructure.persistence import metadata_models as m
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence import retrieval_models as g
from crossborder_compliance.infrastructure.persistence.models import utcnow
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    OptimisticConcurrencyError,
)
from crossborder_compliance.infrastructure.persistence.retrieval_repositories import (
    PostgresRetrievalRepository,
)


class PostgresRetrievalNavigationRepository(PostgresRetrievalRepository):
    def approved_nodes(self, s, version_ids):
        nodes = []
        for ident in version_ids:
            version = self.get(s, k.KnowledgeDocumentVersionEntity, ident)
            source = self.get(s, k.KnowledgeDocumentEntity, version.document_id)
            self.source(source.source_id)
            if version.lifecycle not in ("APPROVED", "ACTIVE") or not version.approved_by:
                raise ValueError("approved canonical knowledge required")
            bindings = self.rows(
                s,
                m.KnowledgeBindingEntity,
                m.KnowledgeBindingEntity.knowledge_version_id == ident,
                m.KnowledgeBindingEntity.review_status == "APPROVED",
            )
            if not any(
                self.context.permission.system
                or set(row.permission_scopes_json) <= self.context.permission.scopes
                for row in bindings
            ):
                raise PermissionError("source permission denied")
            nodes.extend(
                self.rows(
                    s,
                    k.KnowledgeStructureNodeEntity,
                    k.KnowledgeStructureNodeEntity.knowledge_version_id == ident,
                )
            )
        return nodes

    def generate_wiki(self, title, version_ids, generator):
        self.admin()
        if not version_ids or len(set(version_ids)) != len(version_ids):
            raise ValueError("distinct approved sources required")
        with self.sessions() as s, s.begin():
            nodes = self.approved_nodes(s, version_ids)
            content = generator.generate(
                tuple(
                    dict(
                        canonical_locator=n.canonical_locator,
                        heading=n.heading,
                        original_text=n.original_text,
                    )
                    for n in nodes
                )
            )
            if not content or len(content) > 1000000:
                raise ValueError("invalid wiki draft")
            page, version = str(uuid4()), str(uuid4())
            s.add(g.WikiPageEntity(tenant_id=self.tenant_id, wiki_page_id=page, title=title))
            s.flush()
            s.add(
                g.WikiVersionEntity(
                    tenant_id=self.tenant_id,
                    wiki_version_id=version,
                    wiki_page_id=page,
                    version=1,
                    content=content,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    generated_by=self.context.permission.actor_id,
                    lifecycle="DRAFT",
                )
            )
            s.flush()
            for ident in version_ids:
                s.add(
                    g.WikiSourceBindingEntity(
                        tenant_id=self.tenant_id,
                        source_binding_id=str(uuid4()),
                        wiki_version_id=version,
                        knowledge_version_id=ident,
                    )
                )
            for citation in sorted({n.citation_id for n in nodes}):
                s.add(
                    g.WikiCitationEntity(
                        tenant_id=self.tenant_id,
                        wiki_citation_id=str(uuid4()),
                        wiki_version_id=version,
                        citation_id=citation,
                    )
                )
        return self.wiki_version(version)

    def wiki_version(self, ident):
        self.admin()
        with self.sessions() as s:
            row = self.get(s, g.WikiVersionEntity, ident)
            return dict(
                wiki_version_id=row.wiki_version_id,
                wiki_page_id=row.wiki_page_id,
                version=row.version,
                content=row.content,
                content_hash=row.content_hash,
                lifecycle=row.lifecycle,
                generated_by=row.generated_by,
                reviewed_by=row.reviewed_by,
                official_evidence=False,
                legal_basis=False,
                record_version=row.record_version,
            )

    def review_task(self, s, summary):
        change, task = str(uuid4()), str(uuid4())
        s.add(
            m.AdminChangeSetEntity(
                tenant_id=self.tenant_id,
                change_set_id=change,
                actor_id=self.context.permission.actor_id,
                lifecycle_status="PENDING_REVIEW",
                summary=summary,
            )
        )
        s.flush()
        s.add(
            m.AdminReviewTaskEntity(
                tenant_id=self.tenant_id,
                review_task_id=task,
                change_set_id=change,
                review_status="PENDING",
            )
        )
        s.flush()
        return task

    def approve_task(self, s, ident):
        task = self.get(s, m.AdminReviewTaskEntity, ident, True)
        change = self.get(s, m.AdminChangeSetEntity, task.change_set_id, True)
        actor = self.context.permission.actor_id
        if (
            self.context.permission.system
            or change.actor_id == actor
            or task.review_status != "PENDING"
        ):
            raise ValueError("independent pending human review required")
        task.review_status = "APPROVED"
        task.reviewer_id = actor
        task.decision_comment = "Derived navigation evidence review approved"
        change.lifecycle_status = "APPROVED"
        return actor

    def wiki_action(self, ident, action, expected):
        self.admin()
        with self.sessions() as s, s.begin():
            row = self.get(s, g.WikiVersionEntity, ident, True)
            if row.record_version != expected:
                raise OptimisticConcurrencyError("stale wiki version")
            sources = self.rows(
                s, g.WikiSourceBindingEntity, g.WikiSourceBindingEntity.wiki_version_id == ident
            )
            nodes = self.approved_nodes(s, [r.knowledge_version_id for r in sources])
            citations = self.rows(
                s, g.WikiCitationEntity, g.WikiCitationEntity.wiki_version_id == ident
            )
            if (
                not sources
                or not citations
                or not {c.citation_id for c in citations} <= {n.citation_id for n in nodes}
            ):
                raise ValueError("wiki citation validation failed")
            before, after = {
                "validate": ("DRAFT", "VALIDATED"),
                "submit-review": ("VALIDATED", "PENDING_REVIEW"),
                "approve": ("PENDING_REVIEW", "APPROVED"),
                "publish": ("APPROVED", "ACTIVE"),
            }[action]
            if row.lifecycle != before:
                raise ValueError("invalid wiki lifecycle")
            if action == "submit-review":
                task = self.review_task(s, "Wiki " + ident)
                s.add(
                    g.WikiReviewEntity(
                        tenant_id=self.tenant_id,
                        wiki_review_id=str(uuid4()),
                        wiki_version_id=ident,
                        review_task_id=task,
                        status="PENDING",
                    )
                )
            if action == "approve":
                review = self.rows(
                    s, g.WikiReviewEntity, g.WikiReviewEntity.wiki_version_id == ident
                )[0]
                row.reviewed_by = self.approve_task(s, review.review_task_id)
                review.status = "APPROVED"
                review.reviewer = row.reviewed_by
            if action == "publish":
                review = self.rows(
                    s, g.WikiReviewEntity, g.WikiReviewEntity.wiki_version_id == ident
                )[0]
                task = self.get(s, m.AdminReviewTaskEntity, review.review_task_id)
                if task.review_status != "APPROVED" or not row.reviewed_by:
                    raise ValueError("wiki review required")
                s.add(
                    g.WikiPublishRecordEntity(
                        tenant_id=self.tenant_id,
                        publish_record_id=str(uuid4()),
                        wiki_version_id=ident,
                        published_by=self.context.permission.actor_id,
                        published_at=utcnow(),
                    )
                )
                s.add(
                    m.AdminPublishRecordEntity(
                        tenant_id=self.tenant_id,
                        publish_record_id=str(uuid4()),
                        object_kind="WIKI_VERSION",
                        version_id=ident,
                        published_by=self.context.permission.actor_id,
                    )
                )
            row.lifecycle = after
            row.record_version += 1
        return self.wiki_version(ident)

    def runtime_wiki(self, scope, page_id):
        with self.sessions() as s:
            self.get(s, g.WikiPageEntity, page_id)
            versions = self.rows(
                s,
                g.WikiVersionEntity,
                g.WikiVersionEntity.wiki_page_id == page_id,
                g.WikiVersionEntity.lifecycle == "ACTIVE",
            )
            if not versions:
                raise LookupError("active wiki unavailable")
            row = versions[0]
            sources = self.rows(
                s,
                g.WikiSourceBindingEntity,
                g.WikiSourceBindingEntity.wiki_version_id == row.wiki_version_id,
            )
            if not sources or not {r.knowledge_version_id for r in sources} <= set(
                scope.filter_spec.version_filter
            ):
                raise LookupError("wiki outside allowed scope")
            return dict(
                wiki_page_id=page_id,
                wiki_version_id=row.wiki_version_id,
                content=row.content,
                legal_basis=False,
                official_evidence=False,
                lifecycle="ACTIVE",
            )

    def graph_provenance(self, s, contract):
        version = self.get(
            s, k.KnowledgeDocumentVersionEntity, contract.source_knowledge_version_id
        )
        if version.document_id != contract.source_knowledge_id:
            raise ValueError("graph source document mismatch")
        nodes = self.approved_nodes(s, [version.knowledge_version_id])
        citations = [self.get(s, b.CitationEntity, n.citation_id) for n in nodes]
        if contract.source_evidence_id not in {c.evidence_id for c in citations}:
            raise ValueError("graph evidence outside source chain")
        source = self.source(self.get(s, k.KnowledgeDocumentEntity, version.document_id).source_id)
        if contract.jurisdiction_id not in source.get("jurisdiction_refs", ()):
            raise ValueError("graph jurisdiction mismatch")
        self.get(s, b.JurisdictionEntity, contract.jurisdiction_id)

    def create_graph(self, kind, payload):
        self.admin()
        model = g.GRAPH_MODELS[kind]
        ident = str(uuid4())
        contract = (KnowledgeGraphNode if kind == "node" else KnowledgeGraphEdge).model_validate(
            dict(
                payload,
                **{"graph_" + kind + "_id": ident},
                generated_by=self.context.permission.actor_id,
                reviewed_by=None,
                status="DRAFT",
                version=1,
            )
        )
        with self.sessions() as s, s.begin():
            self.graph_provenance(s, contract)
            fields = dict(
                tenant_id=self.tenant_id,
                **{"graph_" + kind + "_id": ident},
                source_knowledge_id=contract.source_knowledge_id,
                source_knowledge_version_id=contract.source_knowledge_version_id,
                source_evidence_id=contract.source_evidence_id,
                jurisdiction_id=contract.jurisdiction_id,
                generated_by=contract.generated_by,
                payload_json=contract.model_dump(mode="json"),
                status="DRAFT",
            )
            if kind == "edge":
                self.metadata(s, contract.relation_type_ref, "GRAPH_RELATION_TYPE")
                for node_id in (contract.source_node_id, contract.target_node_id):
                    self.get(s, g.GRAPH_MODELS["node"], node_id)
                fields.update(
                    source_node_id=contract.source_node_id,
                    target_node_id=contract.target_node_id,
                    relation_type_ref=contract.relation_type_ref,
                )
            s.add(model(**fields))
        return dict(contract.model_dump(mode="json"), record_version=1)

    def graph_action(self, kind, ident, action, expected):
        self.admin()
        model = g.GRAPH_MODELS[kind]
        with self.sessions() as s, s.begin():
            row = self.get(s, model, ident, True)
            if row.record_version != expected:
                raise OptimisticConcurrencyError("stale graph version")
            contract = (
                KnowledgeGraphNode if kind == "node" else KnowledgeGraphEdge
            ).model_validate(row.payload_json)
            self.graph_provenance(s, contract)
            if action == "submit-review" and row.status == "DRAFT" and not row.review_task_id:
                row.review_task_id = self.review_task(s, "Derived Graph " + ident)
            elif action == "approve" and row.status == "DRAFT" and row.review_task_id:
                row.reviewed_by = self.approve_task(s, row.review_task_id)
                row.status = "ACTIVE"
            else:
                raise ValueError("invalid graph review action")
            row.record_version += 1
            row.payload_json = dict(
                row.payload_json, status=row.status, reviewed_by=row.reviewed_by
            )
            return dict(row.payload_json, record_version=row.record_version)

    def graph_effective(self, row, scope):
        from datetime import date

        data = row.payload_json
        start = data.get("effective_from")
        end = data.get("effective_to")
        return (
            row.source_knowledge_version_id in scope.filter_spec.version_filter
            and row.jurisdiction_id in scope.allowed_jurisdiction_ids
            and (not start or date.fromisoformat(start) <= scope.effective_as_of)
            and (not end or date.fromisoformat(end) >= scope.effective_as_of)
        )

    def graph_neighbors(self, plan, candidates, limit):
        # All expansion endpoints must map to canonical chunks inside the same hard-filtered set.
        with self.sessions() as s:
            node_model, edge_model = g.GRAPH_MODELS["node"], g.GRAPH_MODELS["edge"]
            nodes = {
                n.graph_node_id: n
                for n in self.rows(s, node_model, node_model.status == "ACTIVE")
                if self.graph_effective(n, plan.scope)
            }
            starting = set()
            for c in candidates:
                for link in self.rows(
                    s, k.KnowledgeChunkNodeEntity, k.KnowledgeChunkNodeEntity.chunk_id == c.chunk_id
                ):
                    citation = self.get(
                        s,
                        b.CitationEntity,
                        self.get(
                            s, k.KnowledgeStructureNodeEntity, link.structure_node_id
                        ).citation_id,
                    )
                    starting.update(
                        key
                        for key, n in nodes.items()
                        if n.source_evidence_id == citation.evidence_id
                    )
            targets = set()
            for edge in self.rows(s, edge_model, edge_model.status == "ACTIVE"):
                if (
                    self.graph_effective(edge, plan.scope)
                    and edge.source_node_id in starting
                    and edge.target_node_id in nodes
                    and edge.source_node_id in nodes
                ):
                    targets.add(nodes[edge.target_node_id].source_evidence_id)
            chunks = []
            for version, index in plan.index_versions.items():
                for node in self.rows(
                    s,
                    k.KnowledgeStructureNodeEntity,
                    k.KnowledgeStructureNodeEntity.knowledge_version_id == version,
                ):
                    if self.get(s, b.CitationEntity, node.citation_id).evidence_id not in targets:
                        continue
                    for link in self.rows(
                        s,
                        k.KnowledgeChunkNodeEntity,
                        k.KnowledgeChunkNodeEntity.structure_node_id == node.structure_node_id,
                    ):
                        chunks.append(
                            RetrievalCandidate(
                                chunk_id=link.chunk_id,
                                knowledge_version_id=version,
                                index_version_id=index,
                                channels=("GRAPH",),
                            )
                        )
        eligible = set(self.eligible_chunk_ids(plan, tuple(c.chunk_id for c in chunks)))
        return tuple(
            {
                c.chunk_id: c
                for c in sorted(chunks, key=lambda x: x.chunk_id)
                if c.chunk_id in eligible
            }.values()
        )[:limit]
