import hashlib
import json
import math
from datetime import date
from uuid import UUID, uuid4

from crossborder_compliance.application.document_ports import ObjectStoragePort, TaskQueuePort
from crossborder_compliance.application.knowledge_ports import (
    ChunkingStrategyPort,
    ControlledDownloaderPort,
    EmbeddingPort,
    KnowledgeRepositoryPort,
)
from crossborder_compliance.domain.knowledge import (
    PRODUCT_DIMENSIONS,
    FormalContext,
    KnowledgeChunk,
    KnowledgeFilterSpec,
    KnowledgeScope,
    KnowledgeStructureNode,
)
from crossborder_compliance.domain.security import RepositoryContext


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class StructureAwareChunkingStrategy:
    strategy_version = "structure-aware-v1"
    strategies = frozenset(
        {"STRUCTURE_AWARE", "ARTICLE", "SECTION", "PARAGRAPH", "TABLE", "SLIDING_WINDOW"}
    )

    def chunk(self, nodes: list[KnowledgeStructureNode], strategy: str) -> list[KnowledgeChunk]:
        if strategy not in self.strategies:
            raise ValueError("unknown chunk strategy")
        chunks = []
        for node in nodes:
            if strategy not in {"STRUCTURE_AWARE", "SLIDING_WINDOW"} and node.node_type != strategy:
                continue
            parts = [node.original_text]
            if strategy == "SLIDING_WINDOW":
                words = node.original_text.split()
                parts = [" ".join(words[i : i + 256]) for i in range(0, len(words), 224)]
            for part in parts:
                normalized = " ".join(part.split())
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=str(uuid4()),
                        knowledge_version_id=node.knowledge_version_id,
                        structure_node_ids=(node.structure_node_id,),
                        chunk_type=strategy,
                        original_text=part,
                        normalized_text=normalized,
                        token_count=max(1, len(normalized.split())),
                        language=node.language,
                        sequence=len(chunks),
                        canonical_locator=node.canonical_locator,
                        citation_refs=(node.citation_id,),
                        content_hash=digest(part.encode()),
                        chunking_strategy_version=self.strategy_version,
                    )
                )
        if not chunks:
            raise ValueError("no canonical chunks")
        return chunks


class KnowledgeIngestionService:
    def __init__(
        self,
        repository: KnowledgeRepositoryPort,
        *,
        queue: TaskQueuePort | None = None,
        storage: ObjectStoragePort | None = None,
        downloader: ControlledDownloaderPort | None = None,
        chunker: ChunkingStrategyPort | None = None,
    ):
        self.repository, self.queue, self.storage, self.downloader = (
            repository,
            queue,
            storage,
            downloader,
        )
        self.chunker = chunker or StructureAwareChunkingStrategy()

    def ingest(self, version_id: str, payload: dict) -> dict:
        run = self.repository.schedule_ingestion(version_id, payload)
        if self.queue:
            try:
                self.queue.enqueue(
                    task_id=UUID(run["ingestion_run_id"]), task_type="KNOWLEDGE_INGESTION"
                )
            except Exception:
                pass  # Durable outbox remains pending for retry.
        return run

    def work(self, run_id: str) -> dict:
        data = self.repository.ingestion_input(run_id)
        if data["status"] == "COMPLETED":
            return data["run"]
        try:
            if self.storage is None:
                raise ValueError("OBJECT_STORAGE_NOT_CONFIGURED")
            payload = data["input"]
            audit = {}
            if payload.get("url"):
                if self.downloader is None:
                    raise ValueError("CONTROLLED_DOWNLOADER_NOT_CONFIGURED")
                raw, audit = self.downloader.download(payload["url"])
                content = json.loads(raw)
            else:
                content = {"nodes": payload["nodes"]}
                raw = json.dumps(content, sort_keys=True, ensure_ascii=False).encode()
            if len(raw) > 10_000_000:
                raise ValueError("maximum upload size exceeded")
            content_hash = digest(raw)
            artifact = self.storage.put(
                object_key=f"knowledge/{data['tenant_id']}/{data['version_id']}/{content_hash}.json",
                content=raw,
                content_type="application/json",
            )
            audit.update(content_hash=content_hash, artifact_ref=artifact)
            inputs = content["nodes"]
            if not inputs or len(inputs) > 10000:
                raise ValueError("invalid canonical structure size")
            ids = {n["canonical_locator"]: str(uuid4()) for n in inputs}
            if len(ids) != len(inputs):
                raise ValueError("duplicate canonical locator")
            nodes = []
            for sequence, n in enumerate(inputs):
                parent = n.get("parent_locator")
                if parent and parent not in ids:
                    raise ValueError("missing structure parent")
                nodes.append(
                    KnowledgeStructureNode(
                        structure_node_id=ids[n["canonical_locator"]],
                        knowledge_version_id=data["version_id"],
                        node_type=n["node_type"],
                        parent_node_id=ids.get(parent),
                        sequence=sequence,
                        canonical_locator=n["canonical_locator"],
                        official_number=n.get("official_number"),
                        heading=n.get("heading", ""),
                        original_text=n["original_text"],
                        normalized_text=" ".join(n["original_text"].split()),
                        language=data["language"],
                        effective_date=data["effective_from"],
                        source_trace={
                            "artifact_ref": artifact,
                            "content_hash": content_hash,
                            "locator": n["canonical_locator"],
                        },
                        provenance={
                            "source_id": data["source_id"],
                            "document_id": data["document_id"],
                            "official_source": data["official_source"],
                            "content_hash": content_hash,
                        },
                        citation_id=str(uuid4()),
                    )
                )
            parents = {n.structure_node_id: n.parent_node_id for n in nodes}
            for node in nodes:
                seen = set()
                current = node.structure_node_id
                while current:
                    if current in seen:
                        raise ValueError("cyclic canonical hierarchy")
                    seen.add(current)
                    current = parents[current]
            return self.repository.complete_ingestion(
                run_id,
                nodes,
                self.chunker.chunk(nodes, payload.get("strategy", "STRUCTURE_AWARE")),
                audit,
            )
        except Exception:
            self.repository.fail_ingestion(run_id)
            raise


class PermissionScopeResolver:
    def permits(self, binding, context):
        return (
            context.permission.system
            or set(binding["permission_scopes"]) <= context.permission.scopes
        )


class DimensionScopeResolver:
    dimensions = ()

    def permits(self, binding, formal):
        return all(
            not binding["dimensions"].get(d)
            or bool(set(binding["dimensions"][d]) & set(formal.dimensions.get(d, ())))
            for d in self.dimensions
        )


class ProductScopeResolver(DimensionScopeResolver):
    dimensions = PRODUCT_DIMENSIONS

    def permits(self, binding, formal):
        if formal.product_unresolved and binding["scope_type"] != "GLOBAL":
            return False  # UNRESOLVED_PRODUCT_SCOPE never broadens to all products.
        return super().permits(binding, formal)


class JurisdictionScopeResolver(DimensionScopeResolver):
    dimensions = ("jurisdiction", "jurisdiction_group")


class ScenarioScopeResolver(DimensionScopeResolver):
    dimensions = ("scenario",)


class IndustryScopeResolver(DimensionScopeResolver):
    dimensions = ("industry",)


class DataCategoryScopeResolver(DimensionScopeResolver):
    dimensions = ("data_category",)


class KnowledgeScopeResolver:
    """Generates only hard filters. No retrieval, ranking, model call, or raw-document inference."""

    def __init__(self, repository: KnowledgeRepositoryPort, context: RepositoryContext):
        self.repository, self.context = repository, context

    def resolve(
        self,
        project_id,
        *,
        subject_type="PROJECT",
        subject_id=None,
        snapshot_id=None,
        as_of=None,
        languages=(),
    ):
        subject_id = subject_id or project_id
        saved = (
            self.repository.saved_scope(project_id, subject_type, subject_id, snapshot_id)
            if snapshot_id
            else None
        )
        frozen_filters = None
        if snapshot_id and not saved:
            # Freeze one project-bounded version universe before refining item/flow filters.
            # A subject receives only its own allowed bindings, never the project union.
            frozen_filters = self.repository.snapshot_knowledge_filters(snapshot_id)
            if subject_type != "PROJECT":
                root = self.repository.saved_scope(project_id, "PROJECT", project_id, snapshot_id)
                if root is None:
                    self.resolve(project_id, snapshot_id=snapshot_id, languages=languages)
                frozen_filters = self.repository.snapshot_knowledge_filters(snapshot_id)
        if saved:
            formal = FormalContext.model_validate(saved["formal_context"])
            previous = KnowledgeScope.model_validate(saved["scope"])
            when = previous.effective_as_of
            pinned = previous.filter_spec.version_filter
            languages = previous.filter_spec.language_filter
        else:
            formal = FormalContext.model_validate(
                self.repository.formal_context(project_id, subject_type, subject_id, snapshot_id)
            )
            when = (
                self.repository.snapshot_date(snapshot_id)
                if snapshot_id
                else (as_of or date.today())
            )
            pinned = ()
            if frozen_filters is not None:
                pinned = tuple(frozen_filters["version_filter"])
        candidates = (
            []
            if (saved or frozen_filters is not None) and not pinned
            else self.repository.scope_candidates(when, pinned)
        )
        if frozen_filters is not None:
            candidates = [
                b for b in candidates if b["binding_id"] in frozen_filters["binding_filter"]
            ]
        if saved:
            candidates = [
                b for b in candidates if b["binding_id"] in previous.filter_spec.binding_filter
            ]
        allowed = []
        excluded = []
        resolvers = (
            ("PRODUCT_SCOPE_EXCLUDED", ProductScopeResolver()),
            ("JURISDICTION_SCOPE_EXCLUDED", JurisdictionScopeResolver()),
            ("SCENARIO_SCOPE_EXCLUDED", ScenarioScopeResolver()),
            ("INDUSTRY_SCOPE_EXCLUDED", IndustryScopeResolver()),
            ("DATA_CATEGORY_SCOPE_EXCLUDED", DataCategoryScopeResolver()),
        )
        for binding in candidates:
            reason = None
            if not PermissionScopeResolver().permits(binding, self.context):
                reason = "PERMISSION_DENIED"
            elif not binding["lifecycle_allowed"]:
                reason = "LIFECYCLE_EXCLUDED"
            elif not binding["effective_allowed"]:
                reason = "EFFECTIVE_DATE_EXCLUDED"
            else:
                for code, resolver in resolvers:
                    if not resolver.permits(binding, formal):
                        reason = code
                        break
                if not reason and languages and binding["language"] not in languages:
                    reason = "LANGUAGE_EXCLUDED"
            if reason:
                exclusion = {"reason_code": reason}
                if reason != "PERMISSION_DENIED":
                    exclusion["binding_id"] = binding["binding_id"]
                if exclusion not in excluded:
                    excluded.append(exclusion)
            else:
                allowed.append(binding)
        dimensions = formal.dimensions
        permission = tuple(sorted(self.context.permission.scopes))
        scope_types = tuple(sorted({b["scope_type"] for b in allowed}))
        filters = KnowledgeFilterSpec(
            tenant_filter=str(self.context.tenant_id),
            permission_filter=permission,
            lifecycle_filter=("PINNED_APPROVED",) if snapshot_id else ("ACTIVE",),
            effective_date_filter=when,
            jurisdiction_filter=dimensions.get("jurisdiction", ()),
            product_filter={d: dimensions.get(d, ()) for d in PRODUCT_DIMENSIONS},
            scenario_filter=dimensions.get("scenario", ()),
            industry_filter=dimensions.get("industry", ()),
            data_category_filter=dimensions.get("data_category", ()),
            language_filter=languages,
            scope_type_filter=scope_types,
            version_filter=tuple(sorted({b["knowledge_version_id"] for b in allowed})),
            binding_filter=tuple(sorted({b["binding_id"] for b in allowed})),
        )
        scope = KnowledgeScope(
            tenant_id=str(self.context.tenant_id),
            project_id=project_id,
            analysis_snapshot_id=snapshot_id,
            subject_type=subject_type,
            subject_id=subject_id,
            allowed_jurisdiction_ids=dimensions.get("jurisdiction", ()),
            allowed_product_domain_ids=dimensions.get("product_domain", ()),
            allowed_product_category_ids=dimensions.get("product_category", ()),
            allowed_product_family_ids=dimensions.get("product_family", ()),
            allowed_product_ids=dimensions.get("product", ()),
            allowed_product_tag_ids=dimensions.get("product_tag", ()),
            allowed_scenario_ids=dimensions.get("scenario", ()),
            allowed_industry_refs=dimensions.get("industry", ()),
            allowed_data_category_refs=dimensions.get("data_category", ()),
            allowed_scope_types=scope_types,
            permission_filters=permission,
            lifecycle_filters=filters.lifecycle_filter,
            effective_as_of=when,
            excluded_bindings=tuple(excluded),
            unresolved_scopes=("UNRESOLVED_PRODUCT_SCOPE",) if formal.product_unresolved else (),
            reason_codes=formal.reason_codes,
            review_required=formal.product_unresolved or bool(formal.reason_codes),
            version=formal.context_version,
            filter_spec=filters,
        )
        if not saved:
            payload = {
                "scope": scope.model_dump(mode="json"),
                "formal_context": formal.model_dump(mode="json"),
            }
            result = self.repository.save_scope(payload)
            if snapshot_id and result["scope"] != payload["scope"]:
                # Recheck this actor's permission after another actor wins snapshot creation.
                return self.resolve(
                    project_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    snapshot_id=snapshot_id,
                    languages=languages,
                )
            return KnowledgeScope.model_validate(result["scope"])
        return scope


class EmbeddingFoundationService:
    def __init__(self, repository, embedding: EmbeddingPort):
        self.repository, self.embedding = repository, embedding

    def build(self, version_id, model_config_id):
        dimension = self.repository.embedding_dimension(model_config_id)
        chunks = self.repository.list_component(version_id, "chunks")
        vectors = self.embedding.embed(
            [ch["normalized_text"] for ch in chunks],
            model_config_id=model_config_id,
            dimension=dimension,
        )
        if len(vectors) != len(chunks) or any(
            len(v) != dimension or not all(math.isfinite(x) for x in v) for v in vectors
        ):
            raise ValueError("embedding contract violated")
        return self.repository.build_index(
            version_id, model_config_id, list(zip(chunks, vectors, strict=True))
        )
