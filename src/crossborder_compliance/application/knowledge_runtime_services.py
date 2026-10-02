"""Publication materialization participates in the existing registry outbox consumer."""

from crossborder_compliance.application.knowledge_services import EmbeddingFoundationService
from crossborder_compliance.application.metadata_services import RegistrySyncService


class KnowledgeRuntimeMaterializationService:
    def __init__(self, repository, registry, cache, *, embedding=None):
        self.repository, self.registry, self.cache = repository, registry, cache
        self.embedding = embedding

    def consume(self, event):
        with self.repository.publication_lease(event):
            self.materialize(event)

    def materialize(self, event):
        repo = self.repository
        claim = repo.claim_publication(event)
        if claim["completed"]:
            return
        version = claim["knowledge_version_id"]
        try:
            self.registry.refresh()
            config = claim["embedding_config_id"]
            if config:
                if self.embedding is None:
                    raise ValueError("PUBLICATION_EMBEDDING_PORT_NOT_CONFIGURED")
                index = EmbeddingFoundationService(repo, self.embedding).build(version, config)
            else:
                index = repo.build_index(version)
            graph = repo.materialize_graph(version)
            generation = self.cache.invalidate(
                tenant_id=repo.tenant_id,
                document_id=claim["document_id"],
                version_id=version,
                event_version=claim["event_version"],
            )
            repo.finish_publication(version, index, self.registry.version(), generation, graph)
        except Exception:
            repo.fail_publication(version, "RUNTIME_ASSET_BUILD_FAILED")
            # Existing RegistrySyncService retries the same event; no second event/outbox system.
            raise ValueError("RUNTIME_MATERIALIZATION_RETRY") from None


class KnowledgePublicationConsumer:
    def __init__(self, event_repository, materialization_service):
        self.sync = RegistrySyncService(
            event_repository,
            {},
            event_consumers={"KNOWLEDGE_VERSION_PUBLISHED": materialization_service},
        )

    def run_once(self, limit=100):
        return self.sync.run_once(limit=limit)
