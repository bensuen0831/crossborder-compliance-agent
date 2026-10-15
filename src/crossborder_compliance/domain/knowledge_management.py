"""Governed management contracts; taxonomy labels are persisted data, never legal rules."""

from datetime import date
from typing import Literal
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crossborder_compliance.domain.localized_metadata import (
    LocalizedDisplayMetadata,
    StableMetadataCode,
)
from crossborder_compliance.domain.security import RepositoryContext

TaxonomyKind = Literal[
    "JURISDICTION_CONFIG",
    "REGULATION_CATEGORY",
    "RESEARCH_TOPIC",
    "LANGUAGE",
    "ISSUING_AUTHORITY",
    "KNOWLEDGE_SOURCE_TYPE",
    "LEGAL_EFFECT",
]
TAXONOMY_KINDS = frozenset(TaxonomyKind.__args__)


class ManagementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TaxonomyPayload(ManagementRequest):
    management_schema: Literal["KB01_TAXONOMY_V1"] = "KB01_TAXONOMY_V1"
    localized_display: LocalizedDisplayMetadata = Field(default_factory=LocalizedDisplayMetadata)
    description: str = Field(default="", max_length=4096)
    local_name: str | None = Field(default=None, max_length=250)
    aliases: tuple[str, ...] = Field(default=(), max_length=128)
    parent_definition_id: UUID | None = None
    display_order: int = Field(default=0, ge=0, le=1_000_000)
    jurisdiction_type: (
        Literal["COUNTRY", "TERRITORY", "SUPRANATIONAL", "SUBJURISDICTION", "SPECIAL_REGIME"] | None
    ) = None
    enabled: bool = True
    merge_source_definition_ids: tuple[UUID, ...] = Field(default=(), max_length=128)
    merge_source_record_versions: dict[UUID, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_aliases(self):
        if any(not x.strip() or len(x) > 250 for x in self.aliases):
            raise ValueError("INVALID_TAXONOMY_ALIAS")
        if len(set(self.aliases)) != len(self.aliases):
            raise ValueError("DUPLICATE_TAXONOMY_ALIAS")
        if len(set(self.merge_source_definition_ids)) != len(self.merge_source_definition_ids):
            raise ValueError("DUPLICATE_TAXONOMY_MERGE_SOURCE")
        if len(self.merge_source_record_versions) > 128 or any(
            version < 1 for version in self.merge_source_record_versions.values()
        ):
            raise ValueError("INVALID_TAXONOMY_MERGE_VERSION")
        return self


class CreateTaxonomy(ManagementRequest):
    kind: TaxonomyKind
    code: StableMetadataCode
    display_name: str = Field(min_length=1, max_length=250)
    payload: TaxonomyPayload = Field(default_factory=TaxonomyPayload)
    idempotency_key: str = Field(min_length=1, max_length=128)


class MutateTaxonomy(ManagementRequest):
    expected_record_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2048)


class EditTaxonomy(MutateTaxonomy):
    payload: TaxonomyPayload


class MergeTaxonomy(MutateTaxonomy):
    target_definition_id: UUID
    expected_target_record_version: int = Field(ge=1)


class CreateKnowledgeHold(ManagementRequest):
    resource_type: Literal["TAXONOMY", "KNOWLEDGE_DOCUMENT"]
    resource_id: UUID
    expected_record_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2048)
    idempotency_key: str = Field(min_length=1, max_length=128)


class KnowledgeDocumentLabel(ManagementRequest):
    kind: TaxonomyKind
    definition_id: UUID
    version_id: UUID


class KnowledgeDocumentMetadata(ManagementRequest):
    title: str = Field(min_length=1, max_length=250)
    local_title: str | None = Field(default=None, max_length=250)
    description: str = Field(default="", max_length=4096)
    official_source_url: str | None = Field(default=None, max_length=2048)
    labels: tuple[KnowledgeDocumentLabel, ...] = Field(default=(), max_length=128)

    @model_validator(mode="after")
    def unique_labels(self):
        identities = [(label.kind, label.definition_id) for label in self.labels]
        if len(set(identities)) != len(identities):
            raise ValueError("DUPLICATE_DOCUMENT_LABEL")
        if self.official_source_url:
            source = urlsplit(self.official_source_url)
            if (
                source.scheme != "https"
                or not source.hostname
                or source.username
                or source.password
                or source.fragment
                or any(
                    key.lower() in {"token", "api_key", "secret", "password"}
                    for key, _ in parse_qsl(source.query)
                )
            ):
                raise ValueError("OFFICIAL_SOURCE_URL_MUST_BE_CREDENTIAL_FREE_HTTPS")
        return self


class CreateManagedKnowledgeDocument(ManagementRequest):
    source_id: UUID
    collection_version_id: UUID
    language: str = Field(min_length=1, max_length=80)
    effective_from: date | None = None
    effective_to: date | None = None
    metadata: KnowledgeDocumentMetadata
    idempotency_key: str = Field(min_length=1, max_length=128)


class CreateManagedKnowledgeVersion(MutateTaxonomy):
    collection_version_id: UUID
    language: str = Field(min_length=1, max_length=80)
    effective_from: date | None = None
    effective_to: date | None = None
    metadata: KnowledgeDocumentMetadata


class EditManagedKnowledgeVersion(MutateTaxonomy):
    metadata: KnowledgeDocumentMetadata


class KnowledgeManagementPolicy(ManagementRequest):
    """Technical management policy on existing governed MetadataVersion."""

    draft_delete_allowed: bool = False
    draft_retention_seconds: int = Field(default=86400, ge=0, le=315360000)
    max_single_bytes: int = Field(default=1024**3, ge=500_000_000)
    max_archive_bytes: int = Field(default=10 * 1024**3, gt=1_000_000_000)
    max_expanded_bytes: int = Field(default=50 * 1024**3, gt=0)
    max_archive_entries: int = Field(default=20000, ge=1)
    multipart_chunk_bytes: int = Field(default=32 * 1024**2, ge=5 * 1024**2, le=5 * 1024**3)
    upload_expiry_seconds: int = Field(default=86400, ge=60, le=604800)
    scan_required: bool = True
    extraction_timeout_seconds: int = Field(default=3600, ge=1, le=14400)
    nested_archives_allowed: bool = False
    tenant_storage_quota_bytes: int = Field(default=100 * 1024**3, gt=0, le=2**63 - 1)
    max_active_upload_sessions: int = Field(default=64, ge=1, le=10000)
    signed_part_expiry_seconds: int = Field(default=900, ge=60, le=3600)
    scanner_timeout_seconds: int = Field(default=3600, ge=1, le=14400)


class KnowledgeManagementPermissionError(PermissionError):
    pass


def require_management_permission(context: RepositoryContext, operation: str) -> None:
    # A legacy coarse grant does not imply the new operation grants. Current
    # server context is authoritative; no operation accepts actor/tenant fields.
    if f"knowledge:{operation}" not in context.permission.scopes:
        raise KnowledgeManagementPermissionError("KNOWLEDGE_OPERATION_NOT_AUTHORIZED")
