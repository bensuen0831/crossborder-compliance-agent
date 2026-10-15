"""Application management of the existing canonical Metadata/Jurisdiction owners."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from crossborder_compliance.domain.knowledge_management import (
    CreateTaxonomy,
    EditTaxonomy,
    MergeTaxonomy,
    MutateTaxonomy,
    require_management_permission,
)
from crossborder_compliance.domain.security import RepositoryContext


class KnowledgeTaxonomyPort(Protocol):
    def list(self, **query) -> dict: ...
    def tree(self, **query) -> dict: ...
    def detail(self, definition_id: UUID) -> dict: ...
    def impact(self, definition_id: UUID) -> dict: ...
    def aliases(self, definition_id: UUID) -> dict: ...
    def mutate(self, operation: str, identity: UUID | None, request) -> dict: ...
    def audit_history(self, identity: UUID, **query) -> dict: ...
    def create_hold(self, request) -> dict: ...
    def release_hold(self, identity: UUID, request) -> dict: ...
    def list_holds(self, resource_type, identity: UUID) -> list[dict]: ...


OPERATIONS = {
    "CREATE": "taxonomy:write",
    "EDIT_DRAFT": "taxonomy:write",
    "NEW_VERSION": "taxonomy:write",
    "SUBMIT_REVIEW": "taxonomy:submit-review",
    "APPROVE": "taxonomy:approve",
    "REJECT": "taxonomy:approve",
    "PUBLISH": "taxonomy:publish",
    "DELETE_DRAFT": "taxonomy:delete",
    "MERGE_PROPOSAL": "taxonomy:write",
    "DEACTIVATE": "taxonomy:write",
    "REACTIVATE": "taxonomy:write",
    "ARCHIVE": "taxonomy:archive",
}


class KnowledgeTaxonomyService:
    def __init__(self, repository: KnowledgeTaxonomyPort, context: RepositoryContext):
        self.repository, self.context = repository, context

    def list(self, **query):
        require_management_permission(self.context, "taxonomy:read")
        return self.repository.list(**query)

    def tree(self, **query):
        require_management_permission(self.context, "taxonomy:read")
        return self.repository.tree(**query)

    def detail(self, definition_id: UUID):
        require_management_permission(self.context, "taxonomy:read")
        return self.repository.detail(definition_id)

    def impact(self, definition_id: UUID):
        require_management_permission(self.context, "taxonomy:read")
        return self.repository.impact(definition_id)

    def aliases(self, definition_id: UUID):
        require_management_permission(self.context, "taxonomy:read")
        return self.repository.aliases(definition_id)

    def audit_history(self, identity, **query):
        require_management_permission(self.context, "audit:read")
        return self.repository.audit_history(identity, **query)

    def create_hold(self, request):
        require_management_permission(self.context, "hold:create")
        return self.repository.create_hold(request)

    def release_hold(self, identity, request):
        require_management_permission(self.context, "hold:release")
        return self.repository.release_hold(identity, request)

    def list_holds(self, resource_type, identity):
        require_management_permission(self.context, "hold:read")
        return self.repository.list_holds(resource_type, identity)

    def mutate(
        self,
        operation: str,
        identity: UUID | None,
        request: CreateTaxonomy | EditTaxonomy | MergeTaxonomy | MutateTaxonomy,
    ):
        require_management_permission(self.context, OPERATIONS[operation])
        return self.repository.mutate(operation, identity, request)
