from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse
from uuid import UUID


def utcnow() -> datetime:
    return datetime.now(UTC)


class GovernanceStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


class ModelProviderType(StrEnum):
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
    GENERIC_REST = "GENERIC_REST"
    INTERNAL_API = "INTERNAL_API"
    COMMERCIAL_API = "COMMERCIAL_API"


class ModelCapabilityCode(StrEnum):
    TEXT = "TEXT"
    VISION = "VISION"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
    LONG_CONTEXT = "LONG_CONTEXT"
    EMBEDDING = "EMBEDDING"
    RERANK = "RERANK"


class KnowledgeScopeCode(StrEnum):
    GLOBAL = "GLOBAL"
    JURISDICTION = "JURISDICTION"
    INDUSTRY = "INDUSTRY"
    SCENARIO = "SCENARIO"
    PRODUCT_DOMAIN = "PRODUCT_DOMAIN"
    PRODUCT = "PRODUCT"
    DATA_CATEGORY = "DATA_CATEGORY"


class TemplateTypeCode(StrEnum):
    REGULATORY_TEMPLATE = "REGULATORY_TEMPLATE"
    ENTERPRISE_TEMPLATE = "ENTERPRISE_TEMPLATE"


class KnowledgeSourceType(StrEnum):
    DOCUMENT = "DOCUMENT"
    WEB = "WEB"
    API = "API"
    DATABASE = "DATABASE"
    MANUAL = "MANUAL"


_ALLOWED_ENDPOINT_SCHEMES = {"https", "http", "internal"}


def validate_endpoint_config(config: dict[str, Any]) -> None:
    def check_keys(value):
        if isinstance(value, dict):
            if any(
                str(key).lower().replace("-", "_")
                in {
                    "api_key",
                    "apikey",
                    "credential",
                    "credentials",
                    "password",
                    "token",
                    "access_token",
                    "authorization",
                    "secret",
                    "secret_value",
                }
                or str(key).lower().replace("-", "_").endswith("_api_key")
                for key in value
            ):
                raise ValueError("provider credentials require a secret reference")
            for child in value.values():
                check_keys(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                check_keys(child)

    check_keys(config)
    url = config.get("url")
    if not url:
        return
    parsed = urlparse(str(url))
    if parsed.scheme not in _ALLOWED_ENDPOINT_SCHEMES:
        raise ValueError("endpoint scheme is not allowed")
    if parsed.username or parsed.password:
        raise ValueError("endpoint credentials must not be embedded in URL")
    if parsed.query or parsed.fragment:
        raise ValueError("endpoint query and fragment are not allowed")
    if parsed.scheme == "internal":
        if not parsed.netloc and not parsed.path:
            raise ValueError("internal endpoint reference is empty")
        return
    if not parsed.hostname:
        raise ValueError("endpoint hostname is required")
    if parsed.scheme == "http":
        host = parsed.hostname.lower()
        private = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(
            (".internal", ".local")
        )
        if not private:
            try:
                ip = ipaddress.ip_address(host)
                private = ip.is_private or ip.is_loopback
            except ValueError:
                private = False
        if not private:
            raise ValueError("plain HTTP endpoint is allowed only for private/loopback hosts")


@dataclass(frozen=True, slots=True)
class GovernedDefinition:
    tenant_id: UUID
    definition_id: UUID
    kind: str
    code: str
    display_name: str
    parent_definition_id: UUID | None = None
    active_version_id: UUID | None = None
    record_version: int = 1
    status: str = "ACTIVE"


@dataclass(frozen=True, slots=True)
class GovernedVersion:
    tenant_id: UUID
    version_id: UUID
    definition_id: UUID
    version_no: int
    lifecycle_status: GovernanceStatus = GovernanceStatus.DRAFT
    payload: dict[str, Any] = field(default_factory=dict)
    effective_from: date | None = None
    effective_to: date | None = None
    record_version: int = 1

    def __post_init__(self) -> None:
        if self.version_no < 1:
            raise ValueError("version_no must be >= 1")
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")


@dataclass(frozen=True, slots=True)
class MetadataBinding:
    tenant_id: UUID
    binding_id: UUID
    binding_type: str
    source_definition_id: UUID
    target_definition_id: UUID
    scope: dict[str, Any] = field(default_factory=dict)
    effective_from: date | None = None
    effective_to: date | None = None


# Named metadata domain contracts. Persistence may use the common versioned metadata store.
@dataclass(frozen=True, slots=True)
class Region(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class JurisdictionGroup(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class RegulatorMetadata(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class LanguageMetadata(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class CurrencyMetadata(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class LocaleMetadata(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ScenarioDefinition(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ScenarioCategory(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ScenarioTag(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ScenarioBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class ProductDomain(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ProductCategory(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ProductFamily(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class Product(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ProductTag(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ProductBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class ProductAlias(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ProductCapabilityBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class ProductKnowledgeBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class DataTypeDefinition(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class DataCategoryDefinition(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class DataFlowTypeDefinition(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ProcessingActivityType(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class StorageType(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class TransferType(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class PartyRoleDefinition(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class ClassificationSchemeVersion:
    tenant_id: UUID
    scheme_version_id: UUID
    scheme_id: UUID
    version_no: int
    lifecycle_status: GovernanceStatus
    applicability: dict[str, Any] = field(default_factory=dict)
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class ClassificationBinding:
    tenant_id: UUID
    classification_binding_id: UUID
    scheme_version_id: UUID
    jurisdiction_id: UUID | None = None
    industry_ref: str | None = None
    scenario_definition_id: UUID | None = None
    priority: int = 100
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class ClassificationApplicabilityMetadata:
    jurisdiction_id: UUID | None = None
    industry_ref: str | None = None
    scenario_definition_id: UUID | None = None
    effective_on: date | None = None


@dataclass(frozen=True, slots=True)
class ModelProvider:
    tenant_id: UUID
    provider_id: UUID
    provider_type: ModelProviderType
    code: str
    display_name: str
    active_version_id: UUID | None = None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ModelProviderVersion:
    tenant_id: UUID
    provider_version_id: UUID
    provider_id: UUID
    version_no: int
    lifecycle_status: GovernanceStatus
    base_url_ref: str | None = None
    endpoint_config: dict[str, Any] = field(default_factory=dict)
    auth_type: str = "NONE"
    secret_ref: str | None = None
    deployment_type: str = "API"
    trust_level: str = "UNSPECIFIED"
    data_boundary: str = "UNSPECIFIED"
    timeout_policy: dict[str, Any] = field(default_factory=dict)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    cost_metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    effective_from: date | None = None
    effective_to: date | None = None

    def __post_init__(self) -> None:
        validate_endpoint_config(self.endpoint_config)


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    tenant_id: UUID
    model_definition_id: UUID
    provider_id: UUID
    model_id: str
    display_name: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    enabled: bool = True
    active_deployment_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ModelDeployment:
    tenant_id: UUID
    model_deployment_id: UUID
    model_definition_id: UUID
    provider_version_id: UUID
    deployment_ref: str
    lifecycle_status: GovernanceStatus
    enabled: bool = True
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class ModelCapability:
    tenant_id: UUID
    model_capability_id: UUID
    model_definition_id: UUID
    capability: ModelCapabilityCode
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelRoutingProfile:
    tenant_id: UUID
    routing_profile_id: UUID
    code: str
    required_capabilities: tuple[ModelCapabilityCode, ...] = ()
    policy: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ModelHealthMetadata:
    tenant_id: UUID
    model_health_metadata_id: UUID
    model_deployment_id: UUID
    health_status: str
    observed_at: datetime = field(default_factory=utcnow)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PromptDefinition(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class PromptVersion(GovernedVersion):
    template_text: str = ""
    variable_schema: dict[str, Any] = field(default_factory=dict)
    capability_requirement: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class PromptVariableSchema:
    schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PromptReview:
    review_id: UUID
    prompt_version_id: UUID
    reviewer_id: str
    decision: str
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class PromptPublishRecord:
    publish_record_id: UUID
    prompt_version_id: UUID
    published_by: str
    published_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class RuleDefinition(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class RuleVersion(GovernedVersion):
    safe_dsl: dict[str, Any] = field(default_factory=dict)
    jurisdiction_scope: tuple[UUID, ...] = ()
    scenario_scope: tuple[UUID, ...] = ()
    industry_scope: tuple[str, ...] = ()
    data_category_scope: tuple[UUID, ...] = ()
    priority: int = 100


@dataclass(frozen=True, slots=True)
class RuleBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class RuleTestCase:
    rule_test_case_id: UUID
    rule_version_id: UUID
    fact_context: dict[str, Any]
    expected_result: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RulePublishRecord:
    publish_record_id: UUID
    rule_version_id: UUID
    published_by: str
    published_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class TemplateDefinition(GovernedDefinition):
    template_type: TemplateTypeCode = TemplateTypeCode.ENTERPRISE_TEMPLATE


@dataclass(frozen=True, slots=True)
class TemplateVersion(GovernedVersion):
    field_schema: dict[str, Any] = field(default_factory=dict)
    content_ref: str | None = None


@dataclass(frozen=True, slots=True)
class TemplateBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class TemplateFieldSchema:
    schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TemplateReview:
    review_id: UUID
    template_version_id: UUID
    reviewer_id: str
    decision: str


@dataclass(frozen=True, slots=True)
class TemplatePublishRecord:
    publish_record_id: UUID
    template_version_id: UUID
    published_by: str
    published_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class KnowledgeCollection(GovernedDefinition):
    pass


@dataclass(frozen=True, slots=True)
class KnowledgeCollectionVersion(GovernedVersion):
    pass


@dataclass(frozen=True, slots=True)
class KnowledgeBinding(MetadataBinding):
    pass


@dataclass(frozen=True, slots=True)
class KnowledgeScopeMetadata:
    scope_type: KnowledgeScopeCode
    scope_ref: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeSourceDefinition(GovernedDefinition):
    source_type: str = ""


@dataclass(frozen=True, slots=True)
class AdminChangeSet:
    tenant_id: UUID
    change_set_id: UUID
    actor_id: str
    status: GovernanceStatus = GovernanceStatus.DRAFT


@dataclass(frozen=True, slots=True)
class AdminReviewTask:
    tenant_id: UUID
    review_task_id: UUID
    change_set_id: UUID
    reviewer_id: str | None = None
    status: str = "PENDING"


@dataclass(frozen=True, slots=True)
class AdminPublishRecord:
    tenant_id: UUID
    publish_record_id: UUID
    object_kind: str
    version_id: UUID
    published_by: str
    published_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class RegistrySyncEvent:
    tenant_id: UUID
    registry_sync_event_id: UUID
    object_kind: str
    object_id: UUID
    version_id: UUID
    event_version: int
    status: str = "PENDING"
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class AnalysisSnapshotRegistryPin:
    tenant_id: UUID
    pin_id: UUID
    analysis_snapshot_id: UUID
    pin_type: str
    logical_key: str
    object_id: UUID
    version_id: UUID
    version_no: int
