"""Operation grants and commands for the single canonical KnowledgeDocument owner."""

from typing import Protocol
from uuid import UUID

from crossborder_compliance.domain.knowledge_management import require_management_permission
from crossborder_compliance.domain.security import RepositoryContext

DOCUMENT_OPERATIONS = {
    "CREATE": "document:create",
    "NEW_VERSION": "document:write",
    "EDIT_DRAFT": "document:write",
    "DELETE_DRAFT": "document:delete",
    "VALIDATE": "document:validate",
    "SUBMIT_REVIEW": "document:submit-review",
    "APPROVE": "document:approve",
    "PUBLISH": "document:publish",
    "EXPIRE": "document:archive",
    "SUPERSEDE": "document:archive",
    "ARCHIVE": "document:archive",
}


class KnowledgeDocumentManagementPort(Protocol):
    def list(self, **query) -> dict: ...
    def detail(self, identity: UUID) -> dict: ...
    def impact(self, identity: UUID) -> dict: ...
    def mutate(self, operation: str, identity: UUID | None, request) -> dict: ...
    def scope_options(self, **query) -> dict: ...
    def scope_bindings(self, identity: UUID) -> dict: ...
    def bind(self, identity: UUID, request) -> dict: ...


class KnowledgeDocumentManagementService:
    def __init__(self, repository: KnowledgeDocumentManagementPort, context: RepositoryContext):
        self.repository, self.context = repository, context

    def list(self, **query):
        require_management_permission(self.context, "document:read")
        return self.repository.list(**query)

    def detail(self, identity):
        require_management_permission(self.context, "document:read")
        return self.repository.detail(identity)

    def impact(self, identity):
        require_management_permission(self.context, "document:read")
        return self.repository.impact(identity)

    def scope_options(self, **query):
        require_management_permission(self.context, "document:bind")
        return self.repository.scope_options(**query)

    def scope_bindings(self, identity):
        require_management_permission(self.context, "document:read")
        return self.repository.scope_bindings(identity)

    def bind(self, identity, request):
        require_management_permission(self.context, "document:bind")
        return self.repository.bind(identity, request)

    def mutate(self, operation, identity, request):
        require_management_permission(self.context, DOCUMENT_OPERATIONS[operation])
        return self.repository.mutate(operation, identity, request)
