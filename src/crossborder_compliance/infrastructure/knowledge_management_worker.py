"""Deployment adapter for the existing durable upload/import/ingestion owners.

The host supplies fresh scoped RepositoryContexts through its existing identity
boundary. This worker never constructs system contexts, reviewers or publishers.
It is technical import work, not a second compliance WorkflowRuntime.
"""

import logging
import threading
from pathlib import Path

from crossborder_compliance.application.knowledge_services import KnowledgeIngestionService
from crossborder_compliance.application.knowledge_uploads import KnowledgeUploadService
from crossborder_compliance.infrastructure.knowledge_batch_ingestion_worker import (
    KnowledgeBatchIngestionWorker,
)
from crossborder_compliance.infrastructure.knowledge_binary_extraction import (
    NativeKnowledgeBinarySourceExtractor,
)
from crossborder_compliance.infrastructure.knowledge_import_worker import KnowledgeImportWorker
from crossborder_compliance.infrastructure.knowledge_upload_worker import KnowledgeUploadWorker
from crossborder_compliance.infrastructure.persistence.knowledge_batches import (
    PostgresKnowledgeImportBatches,
)
from crossborder_compliance.infrastructure.persistence.knowledge_repositories import (
    PostgresKnowledgeRepository,
)
from crossborder_compliance.infrastructure.persistence.knowledge_uploads import (
    PostgresKnowledgeUploads,
)


class KnowledgeManagementWorker:
    def __init__(
        self,
        sessions,
        storage,
        scanner,
        scanner_sandbox,
        extractor,
        parser,
        contexts,
        working_root: Path,
        *,
        poll_interval=2,
    ):
        self.sessions, self.storage, self.scanner = sessions, storage, scanner
        self.scanner_sandbox, self.extractor, self.parser = scanner_sandbox, extractor, parser
        self.contexts, self.root = contexts, working_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.poll_interval = poll_interval
        self.stop_event = threading.Event()
        self.thread = None
        self.last_error_code = None

    def run_once(self):
        contexts = tuple(self.contexts())
        if len(contexts) > 1000 or len({context.tenant_id for context in contexts}) != len(
            contexts
        ):
            raise ValueError("KNOWLEDGE_WORKER_CONTEXT_SCOPE_INVALID")
        work = 0
        for context in contexts:
            if context.permission.system:
                raise PermissionError("KNOWLEDGE_WORKER_REQUIRES_SCOPED_IDENTITY")
            if self.stop_event.is_set():
                break
            uploads = PostgresKnowledgeUploads(self.sessions, context)
            service = KnowledgeUploadService(uploads, self.storage)
            batches = PostgresKnowledgeImportBatches(self.sessions, context)
            if service.cleanup_once():
                work += 1
            if KnowledgeUploadWorker(
                uploads,
                self.storage,
                self.scanner,
                self.scanner_sandbox,
                self.scanner_sandbox.working_root,
            ).run_once():
                work += 1
            if KnowledgeImportWorker(
                batches, service, self.storage, self.extractor, self.extractor.sandbox.working_root
            ).run_once():
                work += 1
            ingestion = KnowledgeIngestionService(
                PostgresKnowledgeRepository(self.sessions, context),
                binary_extractor=NativeKnowledgeBinarySourceExtractor(
                    self.storage, self.parser, self.parser.sandbox.working_root
                ),
            )
            if KnowledgeBatchIngestionWorker(batches, ingestion).run_once():
                work += 1
        return work

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()

        def poll():
            while not self.stop_event.is_set():
                try:
                    self.run_once()
                    self.last_error_code = None
                except PermissionError:
                    self.last_error_code = "KNOWLEDGE_WORKER_CURRENT_SCOPE_DENIED"
                except Exception:
                    self.last_error_code = "KNOWLEDGE_MANAGEMENT_POLL_FAILED"
                    logging.getLogger(__name__).warning("KNOWLEDGE_MANAGEMENT_POLL_FAILED")
                self.stop_event.wait(self.poll_interval)

        self.thread = threading.Thread(target=poll, name="knowledge-management-import", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
