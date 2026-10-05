"""Profile projection consumer of the existing registry outbox, not another publisher."""

from uuid import UUID

from crossborder_compliance.application.metadata_services import RegistrySyncService
from crossborder_compliance.domain.compliance_profiles import PHASE1I_CONFIG_KINDS
from crossborder_compliance.domain.decision_policies import PHASE1J_POLICY_KINDS
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.knowledge_publication_worker import (
    KnowledgePublicationWorker,
)
from crossborder_compliance.infrastructure.persistence.metadata_repositories import (
    PostgresRegistrySourceRepository,
    PostgresRegistrySyncEventRepository,
)
from crossborder_compliance.infrastructure.registry import GenericMetadataRegistry


class ProfileProjectionEvents:
    def __init__(self, repository):
        self.repository = repository

    def pending(self, limit=100):
        return self.repository.pending(limit, object_kinds=tuple(sorted(PHASE1I_CONFIG_KINDS | PHASE1J_POLICY_KINDS)))

    def mark_applied(self, ident):
        self.repository.mark_applied(ident)

    def mark_retry(self, ident, error):
        self.repository.mark_retry(ident, error)


class ComplianceProfilePublicationWorker(KnowledgePublicationWorker):
    def __init__(self, sessions, poll_interval=1):
        super().__init__(sessions, None, poll_interval=poll_interval)
        self.projections = {}

    def consumer(self, tenant):
        context = RepositoryContext.system(UUID(tenant), "compliance-profile-projection-worker")
        source = PostgresRegistrySourceRepository(self.sessions, context)
        registries = {
            kind: self.projections.setdefault((tenant, kind), GenericMetadataRegistry(source, kind))
            for kind in PHASE1I_CONFIG_KINDS | PHASE1J_POLICY_KINDS
        }
        return RegistrySyncService(
            ProfileProjectionEvents(PostgresRegistrySyncEventRepository(self.sessions, context)),
            registries,
        )
