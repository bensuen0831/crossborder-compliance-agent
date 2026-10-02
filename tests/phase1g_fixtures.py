"""Simulate the automatically running publication worker using explicit test adapters."""

from uuid import UUID

from test_phase1f_postgres import FakeEmbedding
from test_phase1f_postgres import publish as publish_domain

from crossborder_compliance.application.knowledge_runtime_services import (
    KnowledgePublicationConsumer,
    KnowledgeRuntimeMaterializationService,
)
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_publication_worker import (
    PublicationEvents,
    RedisRuntimeProjectionCache,
)
from crossborder_compliance.infrastructure.persistence.knowledge_runtime_repository import (
    KnowledgeRuntimeRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresRegistrySyncEventRepository,
)
from crossborder_compliance.infrastructure.registry import ProjectionRegistry


def consume_publications(f, *, embedding=None, cache=None):
    ctx = RepositoryContext.system(UUID(f["tenant"]), "test-publication-worker")
    repo = KnowledgeRuntimeRepository(f["sf"], ctx)
    svc = KnowledgeRuntimeMaterializationService(
        repo,
        ProjectionRegistry(repo.registry_rows),
        cache or RedisRuntimeProjectionCache(get_settings().redis_url),
        embedding=embedding or FakeEmbedding(),
    )
    consumer = KnowledgePublicationConsumer(
        PublicationEvents(PostgresRegistrySyncEventRepository(f["sf"], ctx)), svc
    )
    return consumer.run_once()


def publish(f, *args, **kwargs):
    version = publish_domain(f, *args, **kwargs)
    consume_publications(f)
    return version
