# Phase 1B Repository Contracts

Application-layer Protocols: ProjectRepository, PartyRepository, DocumentRepository, DataInventoryRepository, JurisdictionRepository, ClassificationRepository, EvidenceRepository, LegalBasisRepository, AnalysisSnapshotRepository, WorkflowRunRepository, ReviewRepository, AnalysisStageRepository, ConversationRepository.

Infrastructure provides tenant-scoped PostgreSQL adapters. Query scope derives from RepositoryContext; callers do not pass authorization tenant_id.

Project/Document active version changes require expected_record_version; stale writes raise OptimisticConcurrencyError. Immutable version rows are preserved.
