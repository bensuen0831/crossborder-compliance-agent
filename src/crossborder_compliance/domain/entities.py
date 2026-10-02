from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class VersionedEntity:
    tenant_id: UUID
    record_version: int = 1
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.record_version < 1:
            raise ValueError("record_version must be >= 1")


@dataclass(frozen=True, slots=True)
class Tenant(VersionedEntity):
    tenant_id: UUID
    name: str = ""


@dataclass(frozen=True, slots=True)
class Organization(VersionedEntity):
    organization_id: UUID = field(default=None)
    name: str = ""


@dataclass(frozen=True, slots=True)
class Project(VersionedEntity):
    project_id: UUID = field(default=None)
    organization_id: UUID | None = None
    name: str = ""
    active_version_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ProjectVersion(VersionedEntity):
    project_version_id: UUID = field(default=None)
    project_id: UUID = field(default=None)
    version_no: int = 1
    intake_json: dict[str, object] = field(default_factory=dict)
    effective_from: date | None = None
    effective_to: date | None = None

    def __post_init__(self) -> None:
        VersionedEntity.__post_init__(self)
        if self.version_no < 1:
            raise ValueError("version_no must be >= 1")


@dataclass(frozen=True, slots=True)
class LegalEntity(VersionedEntity):
    legal_entity_id: UUID = field(default=None)
    legal_name: str = ""
    registration_jurisdiction_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ProjectParty(VersionedEntity):
    project_party_id: UUID = field(default=None)
    project_id: UUID = field(default=None)
    legal_entity_id: UUID | None = None
    display_name: str = ""


@dataclass(frozen=True, slots=True)
class PartyRoleAssignment(VersionedEntity):
    assignment_id: UUID = field(default=None)
    project_party_id: UUID = field(default=None)
    role_code: str = ""
    jurisdiction_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class Document(VersionedEntity):
    document_id: UUID = field(default=None)
    project_id: UUID = field(default=None)
    name: str = ""
    active_version_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DocumentVersion(VersionedEntity):
    document_version_id: UUID = field(default=None)
    document_id: UUID = field(default=None)
    version_no: int = 1
    storage_ref: str = ""
    content_hash: str = ""


@dataclass(frozen=True, slots=True)
class DataItem(VersionedEntity):
    data_item_id: UUID = field(default=None)
    project_id: UUID = field(default=None)
    name: str = ""
    canonical_type_ref: str | None = None
    description: str | None = None
    source_document_version_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Jurisdiction(VersionedEntity):
    jurisdiction_id: UUID = field(default=None)
    code: str = ""
    name: str = ""


@dataclass(frozen=True, slots=True)
class ClassificationResult(VersionedEntity):
    classification_result_id: UUID = field(default=None)
    subject_type: str = ""
    subject_id: UUID = field(default=None)
    scheme_id: UUID = field(default=None)
    level_id: UUID | None = None
    jurisdiction_id: UUID = field(default=None)
    confidence: float = 0.0
    review_required: bool = False

    def __post_init__(self) -> None:
        VersionedEntity.__post_init__(self)
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EvidenceReference(VersionedEntity):
    evidence_id: UUID = field(default=None)
    evidence_type: str = ""
    source_ref: str = ""
    validation_status: str = "UNVALIDATED"


@dataclass(frozen=True, slots=True)
class LegalBasisItem(VersionedEntity):
    legal_basis_id: UUID = field(default=None)
    jurisdiction_id: UUID = field(default=None)
    regulatory_structure_node_id: UUID | None = None
    legal_basis_summary: str = ""
    applicability_reason: str = ""
    official_source: str = ""
    citation_locator: str = ""


@dataclass(frozen=True, slots=True)
class AnalysisStageResult(VersionedEntity):
    analysis_stage_result_id: UUID = field(default=None)
    workflow_run_id: UUID = field(default=None)
    stage_code: str = ""
    sequence: int = 1
    summary: str | None = None
    review_required: bool = False


@dataclass(frozen=True, slots=True)
class ConversationThread(VersionedEntity):
    conversation_thread_id: UUID = field(default=None)
    session_id: UUID = field(default=None)
    project_id: UUID | None = None
    title: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationMessage(VersionedEntity):
    message_id: UUID = field(default=None)
    conversation_thread_id: UUID = field(default=None)
    role: str = "USER"
    content: str = ""


@dataclass(frozen=True, slots=True)
class ChannelContextValue:
    channel_type: str
    tenant_id: UUID
    request_id: str
    user_id: str | None = None
    client_id: str | None = None
