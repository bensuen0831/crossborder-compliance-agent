from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from crossborder_compliance.domain.entities import (
    AnalysisStageResult,
    ClassificationResult,
    ConversationMessage,
    ConversationThread,
    DataItem,
    Document,
    EvidenceReference,
    Jurisdiction,
    LegalBasisItem,
    LegalEntity,
    Project,
    ProjectParty,
    ProjectVersion,
)
from crossborder_compliance.domain.security import RepositoryContext, TenantAccessDenied
from crossborder_compliance.infrastructure.persistence.mappers import (
    ClassificationMapper,
    ConversationMapper,
    DataItemMapper,
    EvidenceMapper,
    ProjectMapper,
)
from crossborder_compliance.infrastructure.persistence.models import (
    AnalysisSnapshotEntity,
    AnalysisStageResultEntity,
    ClassificationCategoryEntity,
    ClassificationLevelEntity,
    ClassificationResultCategoryEntity,
    ClassificationResultEntity,
    ClassificationSchemeEntity,
    ConversationMessageEntity,
    ConversationThreadEntity,
    DataItemEntity,
    DocumentEntity,
    EvidenceReferenceEntity,
    JurisdictionEntity,
    LegalBasisEvidenceLinkEntity,
    LegalBasisItemEntity,
    LegalBasisRuleHitLinkEntity,
    LegalEntityEntity,
    RegulatoryStructureNodeEntity,
    RuleHitEntity,
    ProjectEntity,
    ProjectPartyEntity,
    ProjectVersionEntity,
    ReviewTaskEntity,
    InteractionSessionEntity,
    WorkflowRunEntity,
)


class OptimisticConcurrencyError(RuntimeError):
    pass


class _TenantScopedRepository:
    """All queries are scoped from RepositoryContext; callers cannot supply an authorization tenant."""

    def __init__(self, session_factory: sessionmaker, context: RepositoryContext):
        self._sessions = session_factory
        self._context = context

    @property
    def tenant_id(self) -> str:
        return str(self._context.tenant_id)

    def _assert_tenant(self, tenant_id: UUID) -> None:
        self._context.assert_tenant(tenant_id)
        if tenant_id != self._context.tenant_id:
            # Cross-tenant access requires constructing a new explicit system/admin RepositoryContext.
            raise TenantAccessDenied("repository target tenant must equal explicit context tenant")

    def _scoped_get(self, session, model, pk_column, object_id: UUID):
        return session.scalar(
            select(model).where(
                pk_column == str(object_id),
                model.tenant_id == self.tenant_id,
            )
        )


class PostgresProjectRepository(_TenantScopedRepository):
    def add_project(self, project: Project) -> Project:
        self._assert_tenant(project.tenant_id)
        row = ProjectEntity(
            project_id=str(project.project_id),
            tenant_id=self.tenant_id,
            organization_id=str(project.organization_id) if project.organization_id else None,
            name=project.name,
            active_version_id=str(project.active_version_id) if project.active_version_id else None,
            record_version=project.record_version,
            status=project.status,
        )
        with self._sessions() as session, session.begin():
            session.add(row)
        return ProjectMapper.to_domain(row)

    def get_project(self, project_id: UUID) -> Project | None:
        with self._sessions() as session:
            row = self._scoped_get(session, ProjectEntity, ProjectEntity.project_id, project_id)
            return ProjectMapper.to_domain(row) if row else None

    def add_version(self, version: ProjectVersion) -> ProjectVersion:
        self._assert_tenant(version.tenant_id)
        with self._sessions() as session, session.begin():
            project = self._scoped_get(session, ProjectEntity, ProjectEntity.project_id, version.project_id)
            if project is None:
                raise LookupError("project not found in tenant scope")
            row = ProjectVersionEntity(
                project_version_id=str(version.project_version_id),
                tenant_id=self.tenant_id,
                project_id=str(version.project_id),
                version_no=version.version_no,
                intake_json=version.intake_json,
                effective_from=version.effective_from,
                effective_to=version.effective_to,
                record_version=version.record_version,
                status=version.status,
            )
            session.add(row)
        return ProjectMapper.version_to_domain(row)

    def activate_version(self, project_id: UUID, version_id: UUID, *, expected_record_version: int) -> Project:
        with self._sessions() as session, session.begin():
            version = self._scoped_get(
                session, ProjectVersionEntity, ProjectVersionEntity.project_version_id, version_id
            )
            if version is None or version.project_id != str(project_id):
                raise LookupError("version not found in tenant scope")
            result = session.execute(
                update(ProjectEntity)
                .where(
                    ProjectEntity.project_id == str(project_id),
                    ProjectEntity.tenant_id == self.tenant_id,
                    ProjectEntity.record_version == expected_record_version,
                )
                .values(
                    active_version_id=str(version_id),
                    record_version=ProjectEntity.record_version + 1,
                )
            )
            if result.rowcount != 1:
                raise OptimisticConcurrencyError("project version changed")
        project = self.get_project(project_id)
        if project is None:
            raise LookupError("project disappeared")
        return project


class PostgresPartyRepository(_TenantScopedRepository):
    def add_legal_entity(self, entity: LegalEntity) -> LegalEntity:
        self._assert_tenant(entity.tenant_id)
        row = LegalEntityEntity(
            legal_entity_id=str(entity.legal_entity_id),
            tenant_id=self.tenant_id,
            legal_name=entity.legal_name,
            registration_jurisdiction_id=(
                str(entity.registration_jurisdiction_id) if entity.registration_jurisdiction_id else None
            ),
            record_version=entity.record_version,
            status=entity.status,
        )
        with self._sessions() as session, session.begin():
            session.add(row)
        return entity

    def add_project_party(self, party: ProjectParty) -> ProjectParty:
        self._assert_tenant(party.tenant_id)
        with self._sessions() as session, session.begin():
            project = self._scoped_get(session, ProjectEntity, ProjectEntity.project_id, party.project_id)
            if project is None:
                raise LookupError("project not found in tenant scope")
            if party.legal_entity_id:
                legal_entity = self._scoped_get(
                    session, LegalEntityEntity, LegalEntityEntity.legal_entity_id, party.legal_entity_id
                )
                if legal_entity is None:
                    raise LookupError("legal entity not found in tenant scope")
            row = ProjectPartyEntity(
            project_party_id=str(party.project_party_id),
            tenant_id=self.tenant_id,
            project_id=str(party.project_id),
            legal_entity_id=str(party.legal_entity_id) if party.legal_entity_id else None,
            display_name=party.display_name,
            record_version=party.record_version,
            status=party.status,
            )
            session.add(row)
        return party


class PostgresDocumentRepository(_TenantScopedRepository):
    def add_document(self, document: Document) -> Document:
        self._assert_tenant(document.tenant_id)
        with self._sessions() as session, session.begin():
            project = self._scoped_get(session, ProjectEntity, ProjectEntity.project_id, document.project_id)
            if project is None:
                raise LookupError("project not found in tenant scope")
            row = DocumentEntity(
            document_id=str(document.document_id),
            tenant_id=self.tenant_id,
            project_id=str(document.project_id),
            name=document.name,
            active_version_id=str(document.active_version_id) if document.active_version_id else None,
            record_version=document.record_version,
            status=document.status,
            )
            session.add(row)
        return document

    def get_document(self, document_id: UUID) -> Document | None:
        with self._sessions() as session:
            row = self._scoped_get(session, DocumentEntity, DocumentEntity.document_id, document_id)
            if row is None:
                return None
            return Document(
                tenant_id=UUID(row.tenant_id),
                document_id=UUID(row.document_id),
                project_id=UUID(row.project_id),
                name=row.name,
                active_version_id=UUID(row.active_version_id) if row.active_version_id else None,
                record_version=row.record_version,
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )


class PostgresDataInventoryRepository(_TenantScopedRepository):
    def add_data_item(self, item: DataItem) -> DataItem:
        self._assert_tenant(item.tenant_id)
        with self._sessions() as session, session.begin():
            project = self._scoped_get(session, ProjectEntity, ProjectEntity.project_id, item.project_id)
            if project is None:
                raise LookupError("project not found in tenant scope")
            row = DataItemEntity(
            data_item_id=str(item.data_item_id),
            tenant_id=self.tenant_id,
            project_id=str(item.project_id),
            name=item.name,
            canonical_type_ref=item.canonical_type_ref,
            description=item.description,
            source_document_version_id=(
                str(item.source_document_version_id) if item.source_document_version_id else None
            ),
            record_version=item.record_version,
            status=item.status,
            )
            session.add(row)
        return DataItemMapper.to_domain(row)

    def get_data_item(self, data_item_id: UUID) -> DataItem | None:
        with self._sessions() as session:
            row = self._scoped_get(session, DataItemEntity, DataItemEntity.data_item_id, data_item_id)
            return DataItemMapper.to_domain(row) if row else None


class PostgresJurisdictionRepository(_TenantScopedRepository):
    def add_jurisdiction(self, jurisdiction: Jurisdiction) -> Jurisdiction:
        self._assert_tenant(jurisdiction.tenant_id)
        row = JurisdictionEntity(
            jurisdiction_id=str(jurisdiction.jurisdiction_id),
            tenant_id=self.tenant_id,
            code=jurisdiction.code,
            name=jurisdiction.name,
            record_version=jurisdiction.record_version,
            status=jurisdiction.status,
        )
        with self._sessions() as session, session.begin():
            session.add(row)
        return jurisdiction

    def get_jurisdiction(self, jurisdiction_id: UUID) -> Jurisdiction | None:
        with self._sessions() as session:
            row = self._scoped_get(
                session, JurisdictionEntity, JurisdictionEntity.jurisdiction_id, jurisdiction_id
            )
            if row is None:
                return None
            return Jurisdiction(
                tenant_id=UUID(row.tenant_id),
                jurisdiction_id=UUID(row.jurisdiction_id),
                code=row.code,
                name=row.name,
                record_version=row.record_version,
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )


class PostgresClassificationRepository(_TenantScopedRepository):
    def add_result(
        self, result: ClassificationResult, category_ids: list[UUID] | None = None
    ) -> ClassificationResult:
        self._assert_tenant(result.tenant_id)
        with self._sessions() as session, session.begin():
            scheme = self._scoped_get(session, ClassificationSchemeEntity, ClassificationSchemeEntity.scheme_id, result.scheme_id)
            jurisdiction = self._scoped_get(session, JurisdictionEntity, JurisdictionEntity.jurisdiction_id, result.jurisdiction_id)
            if scheme is None or jurisdiction is None:
                raise LookupError("classification scheme or jurisdiction not found in tenant scope")
            if result.level_id:
                level = self._scoped_get(session, ClassificationLevelEntity, ClassificationLevelEntity.level_id, result.level_id)
                if level is None or level.scheme_id != str(result.scheme_id):
                    raise LookupError("classification level not found in tenant scope")
            checked_categories: list[UUID] = []
            for category_id in category_ids or []:
                category = self._scoped_get(session, ClassificationCategoryEntity, ClassificationCategoryEntity.category_id, category_id)
                if category is None or category.scheme_id != str(result.scheme_id):
                    raise LookupError("classification category not found in tenant scope")
                checked_categories.append(category_id)
            row = ClassificationResultEntity(
            classification_result_id=str(result.classification_result_id),
            tenant_id=self.tenant_id,
            subject_type=result.subject_type,
            subject_id=str(result.subject_id),
            scheme_id=str(result.scheme_id),
            scheme_version_id=str(result.scheme_id),
            level_id=str(result.level_id) if result.level_id else None,
            jurisdiction_id=str(result.jurisdiction_id),
            confidence=result.confidence,
            review_required=result.review_required,
            record_version=result.record_version,
            status=result.status,
            )
            session.add(row)
            for category_id in checked_categories:
                session.add(
                    ClassificationResultCategoryEntity(
                        classification_result_category_id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        classification_result_id=str(result.classification_result_id),
                        category_id=str(category_id),
                    )
                )
        return ClassificationMapper.to_domain(row)

    def get_result(self, classification_result_id: UUID) -> ClassificationResult | None:
        with self._sessions() as session:
            row = self._scoped_get(
                session,
                ClassificationResultEntity,
                ClassificationResultEntity.classification_result_id,
                classification_result_id,
            )
            return ClassificationMapper.to_domain(row) if row else None


class PostgresEvidenceRepository(_TenantScopedRepository):
    def add_evidence(self, evidence: EvidenceReference) -> EvidenceReference:
        self._assert_tenant(evidence.tenant_id)
        row = EvidenceReferenceEntity(
            evidence_id=str(evidence.evidence_id),
            tenant_id=self.tenant_id,
            evidence_type=evidence.evidence_type,
            source_ref=evidence.source_ref,
            validation_status=evidence.validation_status,
            record_version=evidence.record_version,
            status=evidence.status,
        )
        with self._sessions() as session, session.begin():
            session.add(row)
        return EvidenceMapper.to_domain(row)


class PostgresLegalBasisRepository(_TenantScopedRepository):
    def add_legal_basis(self, item: LegalBasisItem) -> LegalBasisItem:
        self._assert_tenant(item.tenant_id)
        with self._sessions() as session, session.begin():
            jurisdiction = self._scoped_get(session, JurisdictionEntity, JurisdictionEntity.jurisdiction_id, item.jurisdiction_id)
            if jurisdiction is None:
                raise LookupError("jurisdiction not found in tenant scope")
            if item.regulatory_structure_node_id:
                node = self._scoped_get(
                    session,
                    RegulatoryStructureNodeEntity,
                    RegulatoryStructureNodeEntity.regulatory_structure_node_id,
                    item.regulatory_structure_node_id,
                )
                if node is None:
                    raise LookupError("regulatory structure node not found in tenant scope")
            row = LegalBasisItemEntity(
            legal_basis_id=str(item.legal_basis_id),
            tenant_id=self.tenant_id,
            jurisdiction_id=str(item.jurisdiction_id),
            regulatory_structure_node_id=(
                str(item.regulatory_structure_node_id)
                if item.regulatory_structure_node_id
                else None
            ),
            legal_basis_summary=item.legal_basis_summary,
            applicability_reason=item.applicability_reason,
            official_source=item.official_source,
            citation_locator=item.citation_locator,
            record_version=item.record_version,
            status=item.status,
            )
            session.add(row)
        return item

    def link_rule_hit(self, legal_basis_id: UUID, rule_hit_id: UUID) -> None:
        with self._sessions() as session, session.begin():
            legal_basis = self._scoped_get(
                session, LegalBasisItemEntity, LegalBasisItemEntity.legal_basis_id, legal_basis_id
            )
            if legal_basis is None:
                raise LookupError("legal basis not found in tenant scope")
            rule_hit = self._scoped_get(session, RuleHitEntity, RuleHitEntity.rule_hit_id, rule_hit_id)
            if rule_hit is None:
                raise LookupError("rule hit not found in tenant scope")
            session.add(
                LegalBasisRuleHitLinkEntity(
                    legal_basis_rule_hit_link_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    legal_basis_id=str(legal_basis_id),
                    rule_hit_id=str(rule_hit_id),
                )
            )

    def link_evidence(self, legal_basis_id: UUID, evidence_id: UUID) -> None:
        with self._sessions() as session, session.begin():
            legal_basis = self._scoped_get(
                session, LegalBasisItemEntity, LegalBasisItemEntity.legal_basis_id, legal_basis_id
            )
            if legal_basis is None:
                raise LookupError("legal basis not found in tenant scope")
            evidence = self._scoped_get(
                session, EvidenceReferenceEntity, EvidenceReferenceEntity.evidence_id, evidence_id
            )
            if evidence is None:
                raise LookupError("evidence not found in tenant scope")
            session.add(
                LegalBasisEvidenceLinkEntity(
                    legal_basis_evidence_link_id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    legal_basis_id=str(legal_basis_id),
                    evidence_id=str(evidence_id),
                )
            )


class PostgresAnalysisSnapshotRepository(_TenantScopedRepository):
    def get_snapshot(self, analysis_snapshot_id: UUID) -> AnalysisSnapshotEntity | None:
        with self._sessions() as session:
            return self._scoped_get(
                session, AnalysisSnapshotEntity, AnalysisSnapshotEntity.analysis_snapshot_id, analysis_snapshot_id
            )


class PostgresWorkflowRunRepository(_TenantScopedRepository):
    def get_workflow_run(self, workflow_run_id: UUID) -> WorkflowRunEntity | None:
        with self._sessions() as session:
            return self._scoped_get(
                session, WorkflowRunEntity, WorkflowRunEntity.workflow_run_id, workflow_run_id
            )


class PostgresReviewRepository(_TenantScopedRepository):
    def get_review(self, review_id: UUID) -> ReviewTaskEntity | None:
        with self._sessions() as session:
            return self._scoped_get(session, ReviewTaskEntity, ReviewTaskEntity.review_id, review_id)


class PostgresAnalysisStageRepository(_TenantScopedRepository):
    def add_stage_result(self, result: AnalysisStageResult) -> AnalysisStageResult:
        self._assert_tenant(result.tenant_id)
        row = AnalysisStageResultEntity(
            analysis_stage_result_id=str(result.analysis_stage_result_id),
            tenant_id=self.tenant_id,
            workflow_run_id=str(result.workflow_run_id),
            stage_code=result.stage_code,
            stage_name=result.stage_code,
            sequence=result.sequence,
            summary=result.summary,
            review_required=result.review_required,
            status=result.status,
            record_version=result.record_version,
        )
        with self._sessions() as session, session.begin():
            session.add(row)
        return result


class PostgresConversationRepository(_TenantScopedRepository):
    def add_thread(self, thread: ConversationThread) -> ConversationThread:
        self._assert_tenant(thread.tenant_id)
        with self._sessions() as session, session.begin():
            parent_session = self._scoped_get(session, InteractionSessionEntity, InteractionSessionEntity.session_id, thread.session_id)
            if parent_session is None:
                raise LookupError("interaction session not found in tenant scope")
            if thread.project_id:
                project = self._scoped_get(session, ProjectEntity, ProjectEntity.project_id, thread.project_id)
                if project is None:
                    raise LookupError("project not found in tenant scope")
            row = ConversationThreadEntity(
            conversation_thread_id=str(thread.conversation_thread_id),
            tenant_id=self.tenant_id,
            session_id=str(thread.session_id),
            project_id=str(thread.project_id) if thread.project_id else None,
            title=thread.title,
            status=thread.status,
            record_version=thread.record_version,
            )
            session.add(row)
        return ConversationMapper.to_domain(row)

    def get_thread(self, conversation_thread_id: UUID) -> ConversationThread | None:
        with self._sessions() as session:
            row = self._scoped_get(
                session,
                ConversationThreadEntity,
                ConversationThreadEntity.conversation_thread_id,
                conversation_thread_id,
            )
            return ConversationMapper.to_domain(row) if row else None

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        self._assert_tenant(message.tenant_id)
        with self._sessions() as session, session.begin():
            thread = self._scoped_get(
                session,
                ConversationThreadEntity,
                ConversationThreadEntity.conversation_thread_id,
                message.conversation_thread_id,
            )
            if thread is None:
                raise LookupError("conversation thread not found in tenant scope")
            session.add(
                ConversationMessageEntity(
                    message_id=str(message.message_id),
                    tenant_id=self.tenant_id,
                    conversation_thread_id=str(message.conversation_thread_id),
                    role=message.role,
                    content=message.content,
                    status=message.status,
                    record_version=message.record_version,
                )
            )
        return message
