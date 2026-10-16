"""Catalogue preparation/read use cases; confirmation remains with the existing batch owner."""

from typing import Protocol

from crossborder_compliance.domain.knowledge_management import require_management_permission


class KnowledgeManifestImportPort(Protocol):
    def prepare(self, batch_id, request) -> dict: ...
    def detail(self, batch_id, manifest_id, **query) -> dict: ...
    def list(self, batch_id, **query) -> dict: ...
    def missing_files(self, batch_id, manifest_id, **query) -> dict: ...


class KnowledgeManifestImportService:
    def __init__(self, repository: KnowledgeManifestImportPort, context):
        self.repository, self.context = repository, context

    def prepare(self, batch_id, request):
        require_management_permission(self.context, "batch:manifest-import")
        return self.repository.prepare(batch_id, request)

    def detail(self, batch_id, manifest_id, **query):
        require_management_permission(self.context, "batch:manifest-read")
        return self.repository.detail(batch_id, manifest_id, **query)

    def list(self, batch_id, **query):
        require_management_permission(self.context, "batch:manifest-read")
        return self.repository.list(batch_id, **query)

    def missing_files(self, batch_id, manifest_id, **query):
        require_management_permission(self.context, "batch:manifest-export")
        return self.repository.missing_files(batch_id, manifest_id, **query)
