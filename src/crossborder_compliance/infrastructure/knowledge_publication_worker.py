"""Automatic publication consumer; the Phase 1C registry outbox is the only event store."""

import logging
import threading
from uuid import UUID

from redis import Redis
from sqlalchemy import select

from crossborder_compliance.application.knowledge_runtime_services import (
    KnowledgePublicationConsumer,
    KnowledgeRuntimeMaterializationService,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence import models as b
from crossborder_compliance.infrastructure.persistence.knowledge_runtime_repository import (
    KnowledgeRuntimeRepository,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresRegistrySyncEventRepository,
)
from crossborder_compliance.infrastructure.registry import ProjectionRegistry


class PublicationEvents:
    def __init__(self, repository):
        self.repository = repository

    def pending(self, limit=100):
        return self.repository.pending(limit, object_kinds=("KNOWLEDGE_VERSION_PUBLISHED",))

    def mark_applied(self, event_id):
        self.repository.mark_applied(event_id)

    def mark_retry(self, event_id, error):
        self.repository.mark_retry(event_id, error)


class RedisRuntimeProjectionCache:
    def __init__(self, redis_url):
        self.client = Redis.from_url(redis_url, decode_responses=True)

    def invalidate(self, *, tenant_id, document_id, version_id, event_version):
        key = f"knowledge-runtime:{UUID(tenant_id)}:{UUID(document_id)}:generation"
        # Monotonic generations make duplicate and out-of-order invalidation safe.
        return self.client.execute_command(
            "EVAL",
            "local old=redis.call('hget',KEYS[1],'epoch'); "
            "if not old or tonumber(ARGV[1])>=tonumber(old) then "
            "redis.call('hset',KEYS[1],'epoch',ARGV[1],'version',ARGV[2]); end; "
            "return redis.call('hget',KEYS[1],'version')",
            1,
            key,
            str(event_version),
            version_id,
        )


class KnowledgePublicationWorker:
    def __init__(self, sessions, redis_url, *, embedding=None, poll_interval=1):
        self.sessions, self.redis_url, self.embedding = sessions, redis_url, embedding
        self.poll_interval = poll_interval
        self.stop_event = threading.Event()
        self.thread = None
        self.last_error_code = None

    def consumer(self, tenant):
        ctx = RepositoryContext.system(UUID(tenant), "knowledge-publication-worker")
        repo = KnowledgeRuntimeRepository(self.sessions, ctx)
        projection = ProjectionRegistry(repo.registry_rows)
        service = KnowledgeRuntimeMaterializationService(
            repo, projection, RedisRuntimeProjectionCache(self.redis_url), embedding=self.embedding
        )
        events = PublicationEvents(PostgresRegistrySyncEventRepository(self.sessions, ctx))
        return KnowledgePublicationConsumer(events, service)

    def run_once(self):
        with self.sessions() as s:
            tenants = tuple(s.scalars(select(b.TenantEntity.tenant_id)))
        results = {t: self.consumer(t).run_once() for t in tenants}
        return results

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()

        def work():
            while not self.stop_event.is_set():
                try:
                    self.run_once()
                    self.last_error_code = None
                except Exception:
                    self.last_error_code = "PUBLICATION_POLL_FAILED"
                    logging.getLogger(__name__).warning("PUBLICATION_POLL_FAILED")
                self.stop_event.wait(self.poll_interval)

        self.thread = threading.Thread(
            target=work, name="knowledge-publication-consumer", daemon=True
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
