"""Run tenant-bound durable knowledge ingestion; review/publish remain admin actions."""

import argparse
from uuid import UUID

from crossborder_compliance.application.knowledge_services import KnowledgeIngestionService
from crossborder_compliance.config import get_settings
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.document_storage import S3ObjectStorageAdapter
from crossborder_compliance.infrastructure.knowledge_download import ControlledHTTPSDownloader
from crossborder_compliance.infrastructure.knowledge_worker import (
    KnowledgeIngestionWorker,
    RedisKnowledgeTaskQueue,
)
from crossborder_compliance.infrastructure.persistence.db import build_session_factory
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--consumer-id", default="knowledge-worker")
    parser.add_argument("--approved-download-host", action="append", default=[])
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    repository = PostgresKnowledgeRepository(
        build_session_factory(settings.database_url)[1],
        RepositoryContext.system(args.tenant_id, "knowledge-ingestion-worker"),
    )
    queue = RedisKnowledgeTaskQueue(settings.redis_url, args.tenant_id, args.consumer_id)
    storage = S3ObjectStorageAdapter(
        endpoint_url=settings.object_storage_endpoint,
        bucket=settings.object_storage_bucket,
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
    )
    service = KnowledgeIngestionService(
        repository,
        storage=storage,
        downloader=ControlledHTTPSDownloader(args.approved_download_host),
    )
    worker = KnowledgeIngestionWorker(repository, service, queue)
    while True:
        worker.run_once()
        if args.once:
            return


if __name__ == "__main__":
    main()
