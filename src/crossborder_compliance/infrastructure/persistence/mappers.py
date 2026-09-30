from __future__ import annotations

from uuid import UUID

from crossborder_compliance.application.dtos import (
    ConversationThreadDTO,
    ProjectDTO,
    ProjectVersionDTO,
)
from crossborder_compliance.domain.contracts import (
    ClassificationResultDTO,
    DataItemDTO,
    EvidenceReferenceDTO,
    ProvenanceDTO,
)
from crossborder_compliance.domain.entities import (
    ClassificationResult,
    ConversationThread,
    DataItem,
    EvidenceReference,
    Project,
    ProjectVersion,
)
from crossborder_compliance.domain.foundation import AnalysisSnapshot, ReviewTask, WorkflowRun
from crossborder_compliance.infrastructure.persistence.models import (
    ClassificationResultEntity,
    ConversationThreadEntity,
    DataItemEntity,
    EvidenceReferenceEntity,
    ProjectEntity,
    ProjectVersionEntity,
    AnalysisSnapshotEntity,
    ReviewTaskEntity,
    WorkflowRunEntity,
)


def _provenance(source_ref: str) -> ProvenanceDTO:
    return ProvenanceDTO(
        source_type="postgresql",
        source_ref=source_ref,
        generated_by="PersistenceMapper",
    )


class ProjectMapper:
    @staticmethod
    def to_domain(row: ProjectEntity) -> Project:
        return Project(
            tenant_id=UUID(row.tenant_id),
            project_id=UUID(row.project_id),
            organization_id=UUID(row.organization_id) if row.organization_id else None,
            name=row.name,
            active_version_id=UUID(row.active_version_id) if row.active_version_id else None,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def to_application(row: ProjectEntity) -> ProjectDTO:
        return ProjectDTO(
            project_id=UUID(row.project_id),
            tenant_id=UUID(row.tenant_id),
            organization_id=UUID(row.organization_id) if row.organization_id else None,
            name=row.name,
            active_version_id=UUID(row.active_version_id) if row.active_version_id else None,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def version_to_domain(row: ProjectVersionEntity) -> ProjectVersion:
        return ProjectVersion(
            tenant_id=UUID(row.tenant_id),
            project_version_id=UUID(row.project_version_id),
            project_id=UUID(row.project_id),
            version_no=row.version_no,
            intake_json=row.intake_json,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def version_to_application(row: ProjectVersionEntity) -> ProjectVersionDTO:
        return ProjectVersionDTO(
            project_version_id=UUID(row.project_version_id),
            tenant_id=UUID(row.tenant_id),
            project_id=UUID(row.project_id),
            version_no=row.version_no,
            intake_json=row.intake_json,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            record_version=row.record_version,
            status=row.status,
        )


class DataItemMapper:
    @staticmethod
    def to_domain(row: DataItemEntity) -> DataItem:
        return DataItem(
            tenant_id=UUID(row.tenant_id),
            data_item_id=UUID(row.data_item_id),
            project_id=UUID(row.project_id),
            name=row.name,
            canonical_type_ref=row.canonical_type_ref,
            description=row.description,
            source_document_version_id=UUID(row.source_document_version_id) if row.source_document_version_id else None,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def to_contract(row: DataItemEntity) -> DataItemDTO:
        return DataItemDTO(
            data_item_id=UUID(row.data_item_id),
            project_id=UUID(row.project_id),
            name=row.name,
            canonical_type_ref=row.canonical_type_ref,
            description=row.description,
            source_document_version_id=UUID(row.source_document_version_id) if row.source_document_version_id else None,
            provenance=_provenance(row.data_item_id),
        )


class ClassificationMapper:
    @staticmethod
    def to_domain(row: ClassificationResultEntity) -> ClassificationResult:
        return ClassificationResult(
            tenant_id=UUID(row.tenant_id),
            classification_result_id=UUID(row.classification_result_id),
            subject_type=row.subject_type,
            subject_id=UUID(row.subject_id),
            scheme_id=UUID(row.scheme_id),
            level_id=UUID(row.level_id) if row.level_id else None,
            jurisdiction_id=UUID(row.jurisdiction_id),
            confidence=row.confidence,
            review_required=row.review_required,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def to_contract(row: ClassificationResultEntity, category_ids: list[UUID]) -> ClassificationResultDTO:
        return ClassificationResultDTO(
            classification_result_id=UUID(row.classification_result_id),
            subject_type=row.subject_type,
            subject_id=UUID(row.subject_id),
            scheme_id=UUID(row.scheme_id),
            scheme_version_id=UUID(row.scheme_version_id),
            level_id=UUID(row.level_id) if row.level_id else None,
            category_ids=category_ids,
            jurisdiction_id=UUID(row.jurisdiction_id),
            confidence=row.confidence,
            evidence_ids=[],
            review_required=row.review_required,
            provenance=_provenance(row.classification_result_id),
        )


class EvidenceMapper:
    @staticmethod
    def to_domain(row: EvidenceReferenceEntity) -> EvidenceReference:
        return EvidenceReference(
            tenant_id=UUID(row.tenant_id),
            evidence_id=UUID(row.evidence_id),
            evidence_type=row.evidence_type,
            source_ref=row.source_ref,
            validation_status=row.validation_status,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def to_contract(row: EvidenceReferenceEntity) -> EvidenceReferenceDTO:
        return EvidenceReferenceDTO(
            evidence_id=UUID(row.evidence_id),
            evidence_type=row.evidence_type,
            source_ref=row.source_ref,
            excerpt_hash=row.excerpt_hash,
            validation_status=row.validation_status,
            provenance=_provenance(row.evidence_id),
        )


class ConversationMapper:
    @staticmethod
    def to_domain(row: ConversationThreadEntity) -> ConversationThread:
        return ConversationThread(
            tenant_id=UUID(row.tenant_id),
            conversation_thread_id=UUID(row.conversation_thread_id),
            session_id=UUID(row.session_id),
            project_id=UUID(row.project_id) if row.project_id else None,
            title=row.title,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def to_application(row: ConversationThreadEntity) -> ConversationThreadDTO:
        return ConversationThreadDTO(
            conversation_thread_id=UUID(row.conversation_thread_id),
            tenant_id=UUID(row.tenant_id),
            session_id=UUID(row.session_id),
            project_id=UUID(row.project_id) if row.project_id else None,
            title=row.title,
            record_version=row.record_version,
            status=row.status,
        )


class RuntimeDomainMapper:
    @staticmethod
    def snapshot_to_domain(row: AnalysisSnapshotEntity) -> AnalysisSnapshot:
        return AnalysisSnapshot(
            tenant_id=UUID(row.tenant_id),
            analysis_snapshot_id=UUID(row.analysis_snapshot_id),
            project_version_id=UUID(row.project_version_id),
            snapshot_version=row.snapshot_version,
            analysis_as_of_date=row.analysis_as_of_date,
            provenance=dict(row.provenance_json or {}),
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def workflow_run_to_domain(row: WorkflowRunEntity) -> WorkflowRun:
        return WorkflowRun(
            tenant_id=UUID(row.tenant_id),
            workflow_run_id=UUID(row.workflow_run_id),
            thread_id=UUID(row.thread_id),
            analysis_snapshot_id=UUID(row.analysis_snapshot_id),
            graph_definition_version=row.graph_definition_version,
            langgraph_runtime_version=row.langgraph_runtime_version,
            checkpointer_version=row.checkpointer_version,
            state_schema_version=row.state_schema_version,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def review_to_domain(row: ReviewTaskEntity) -> ReviewTask:
        return ReviewTask(
            tenant_id=UUID(row.tenant_id),
            review_id=UUID(row.review_id),
            workflow_run_id=UUID(row.workflow_run_id),
            review_type=row.review_type,
            object_type=row.object_type,
            object_id=UUID(row.object_id),
            reason=row.reason,
            idempotency_key=row.idempotency_key,
            record_version=row.record_version,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
