"""Provider-neutral foundation contracts. No legal decisions or credential values."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from crossborder_compliance.domain.knowledge import Contract
from crossborder_compliance.domain.metadata import ModelCapabilityCode, ModelProviderType


class ModelOperation(StrEnum):
    CHAT = "chat"
    CHAT_STREAM = "chat_stream"
    STRUCTURED_OUTPUT = "structured_output"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    COUNT_TOKENS = "count_tokens"
    HEALTH_CHECK = "health_check"


class ModelPolicyMode(StrEnum):
    EXTERNAL_MODEL_ALLOWED = "EXTERNAL_MODEL_ALLOWED"
    REDACTION_REQUIRED = "REDACTION_REQUIRED"
    INTERNAL_MODEL_ONLY = "INTERNAL_MODEL_ONLY"


class InputReference(Contract):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: UUID
    version_id: UUID


class LLMRequest(Contract):
    request_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    analysis_snapshot_id: UUID
    operation: ModelOperation
    input_refs: tuple[InputReference, ...] = ()
    prompt_id: UUID | None = None
    required_capabilities: tuple[ModelCapabilityCode, ...] = ()
    output_schema: dict | None = Field(default=None, repr=False)
    max_output_tokens: int = Field(default=512, ge=1, le=65536)

    @model_validator(mode="after")
    def shape(self):
        if self.operation != ModelOperation.HEALTH_CHECK and not self.input_refs:
            raise ValueError("INPUT_REFERENCES_REQUIRED")
        if self.operation == ModelOperation.STRUCTURED_OUTPUT and not self.output_schema:
            raise ValueError("OUTPUT_SCHEMA_REQUIRED")
        if len(set(self.input_refs)) != len(self.input_refs):
            raise ValueError("DUPLICATE_INPUT_REFERENCE")
        return self


class AuthorizedInput(Contract):
    """Produced by a trusted, scoped resource adapter, never accepted from an API caller."""

    ref: InputReference
    tenant_id: UUID
    project_id: UUID
    organization_id: UUID | None = None
    required_scopes: tuple[str, ...] = Field(min_length=1)
    texts: tuple[str, ...] = Field(min_length=1, repr=False, exclude=True)
    security_codes: tuple[str, ...] = ()
    confidentiality_codes: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    permitted_model_boundaries: tuple[str, ...] = ()


class ModelUsagePolicy(Contract):
    policy_id: UUID
    version_id: UUID
    version: int = Field(ge=1)
    tenant_id: UUID
    scope_type: Literal["TENANT", "PROJECT"]
    project_id: UUID | None = None
    default_mode: ModelPolicyMode = ModelPolicyMode.INTERNAL_MODEL_ONLY
    security_rules: dict[str, ModelPolicyMode] = Field(default_factory=dict)
    confidentiality_rules: dict[str, ModelPolicyMode] = Field(default_factory=dict)
    document_rules: dict[str, ModelPolicyMode] = Field(default_factory=dict)
    capability_rules: dict[str, ModelPolicyMode] = Field(default_factory=dict)
    allowed_model_ids: tuple[UUID, ...] = ()
    allowed_provider_ids: tuple[UUID, ...] = ()
    allowed_trust_levels: tuple[str, ...] = ()
    allowed_data_boundaries: tuple[str, ...] = ()
    internal_deployment_classes: tuple[str, ...] = ("ON_PREMISE", "PRIVATE_CLOUD")
    allowed_operations: tuple[ModelOperation, ...] = ()

    @model_validator(mode="after")
    def scope(self):
        if (self.scope_type == "PROJECT") != (self.project_id is not None):
            raise ValueError("POLICY_SCOPE_INVALID")
        if not set(self.internal_deployment_classes) <= {"ON_PREMISE", "PRIVATE_CLOUD"}:
            raise ValueError("INTERNAL_DEPLOYMENT_CLASS_INVALID")
        return self


class ModelCandidate(Contract):
    tenant_id: UUID
    model_id: UUID
    deployment_id: UUID
    provider_id: UUID
    provider_version_id: UUID
    provider_version: int = Field(ge=1)
    provider_type: ModelProviderType
    deployment_class: str
    trust_level: str
    data_boundary: str
    capabilities: tuple[ModelCapabilityCode, ...]
    operations: tuple[ModelOperation, ...]
    health_status: Literal["HEALTHY", "UNHEALTHY", "UNKNOWN"] = "UNKNOWN"
    max_output_tokens: int = Field(ge=1)
    embedding_dimension: int | None = Field(default=None, ge=1, le=16000)
    priority: int = 100


class PolicyDecision(Contract):
    selected_policy: ModelPolicyMode
    external_model_allowed: bool
    redaction_required: bool
    internal_only: bool
    policy_versions: tuple[UUID, ...]
    allowed_model_ids: tuple[UUID, ...]
    allowed_provider_ids: tuple[UUID, ...]
    reason_codes: tuple[str, ...]


class SensitiveSpan(Contract):
    part_index: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    sensitive_type: str = Field(min_length=1, max_length=80)


class DetectionResult(Contract):
    input_hash: str
    complete: bool
    spans: tuple[SensitiveSpan, ...] = ()
    reviewer_required: bool = False


class RedactedRange(SensitiveSpan):
    replacement_token: str


class RedactionResult(Contract):
    run_id: UUID = Field(default_factory=uuid4)
    input_refs: tuple[InputReference, ...]
    input_hash: str
    detected_sensitive_types: tuple[str, ...]
    redacted_ranges: tuple[RedactedRange, ...]
    redacted_texts: tuple[str, ...] = Field(repr=False, exclude=True)
    reversible: Literal[False] = False
    policy_versions: tuple[UUID, ...]
    reviewer_required: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProviderInput(Contract):
    operation: ModelOperation
    texts: tuple[str, ...] = Field(repr=False, exclude=True)
    system_prompt: str | None = Field(default=None, repr=False, exclude=True)
    output_schema: dict | None = Field(default=None, repr=False)
    max_output_tokens: int


class ProviderResult(Contract):
    text: str | None = Field(default=None, repr=False)
    structured: dict | None = Field(default=None, repr=False)
    embeddings: tuple[tuple[float, ...], ...] = Field(default=(), repr=False)
    ranked_indices: tuple[int, ...] = ()
    token_count: int | None = Field(default=None, ge=0)
    healthy: bool | None = None


class LLMResult(Contract):
    request_id: UUID
    model_id: UUID
    deployment_id: UUID
    provider_version_id: UUID
    analysis_snapshot_id: UUID
    policy: PolicyDecision
    redaction_run_id: UUID | None
    result: ProviderResult


class LLMStreamEvent(Contract):
    request_id: UUID
    model_id: UUID
    deployment_id: UUID
    sequence: int = Field(ge=0)
    text_delta: str = Field(repr=False)


class GatewayAuditEvent(Contract):
    """Allowlisted audit shape deliberately excludes text, URLs and credentials."""

    request_id: UUID
    tenant_id: UUID
    project_id: UUID
    analysis_snapshot_id: UUID
    operation: ModelOperation
    model_id: UUID | None = None
    policy_versions: tuple[UUID, ...] = ()
    redaction_run_id: UUID | None = None
    reason_code: Literal["ALLOWED", "COMPLETED", "DENIED", "PROVIDER_FAILED", "STREAM_FAILED"]


class GatewayDenied(PermissionError):
    def __init__(self, code="MODEL_OPERATION_DENIED"):
        self.code = code
        super().__init__(code)


class ProviderFailure(RuntimeError):
    """Sanitized retryable transport failure; raw provider exceptions never escape."""

    def __init__(self):
        super().__init__("MODEL_PROVIDER_UNAVAILABLE")
