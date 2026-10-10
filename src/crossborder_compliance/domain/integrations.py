"""Northbound identity/transport governance; no compliance decision authority."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class IntegrationScope(StrEnum):
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    INTAKE_WRITE = "intake:write"
    DOCUMENT_UPLOAD = "document:upload"
    COMPLIANCE_ANALYZE = "compliance:analyze"
    COMPLIANCE_READ = "compliance:read"
    MODEL_SELECT = "model:select"
    WEBHOOK_MANAGE = "webhook:manage"


# This is channel authorization adaptation to existing owner scopes, never a
# second permission model. Per-project grants are added only after binding checks.
CANONICAL_SCOPE_MAP = {
    IntegrationScope.PROJECT_CREATE: {"project:create", "project:read"},
    IntegrationScope.PROJECT_READ: {"project:read"},
    IntegrationScope.INTAKE_WRITE: {"project:read", "project:update", "project:confirm"},
    IntegrationScope.DOCUMENT_UPLOAD: {
        "project:read",
        "project:update",
        "document:read",
        "document:upload",
        "document:parse",
        "document:unlink",
    },
    IntegrationScope.COMPLIANCE_ANALYZE: {
        "project:read",
        "workflow:read",
        "workflow:execute",
        "decision:read",
        "decision:execute",
        "classification:read",
        "classification:execute",
        "applicability:read",
        "applicability:execute",
        "knowledge:read",
        "knowledge:retrieve",
        "read:internal",
    },
    IntegrationScope.COMPLIANCE_READ: {
        "project:read",
        "workflow:read",
        "decision:read",
        "classification:read",
        "applicability:read",
        "knowledge:read",
        "knowledge:retrieve",
        "read:internal",
    },
    IntegrationScope.MODEL_SELECT: {"project:read", "llm:invoke"},
    IntegrationScope.WEBHOOK_MANAGE: set(),
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntegrationPolicy(Contract):
    token_ttl_seconds: int = Field(default=900, ge=30, le=86400)
    service_account_ttl_seconds: int = Field(default=2592000, ge=60, le=31536000)
    request_limit_bytes: int = Field(default=1048576, ge=1024)
    request_timeout_seconds: int = Field(default=60, ge=1)
    stream_duration_seconds: int = Field(default=60, ge=1)
    event_poll_seconds: float = Field(default=0.5, gt=0)
    rate_window_seconds: int = Field(default=60, ge=1)
    tenant_rate_limit: int = Field(default=1000, ge=1)
    client_rate_limits: dict[str, int] = Field(
        default_factory=lambda: {
            "read": 120,
            "write": 60,
            "upload": 20,
            "start": 10,
            "auth": 30,
        }
    )
    quota_window_seconds: int = Field(default=86400, ge=1)
    client_quotas: dict[str, int] = Field(
        default_factory=lambda: {
            "requests": 10000,
            "upload": 100,
            "start": 100,
        }
    )
    webhook_timeout_seconds: float = Field(default=10, gt=0, le=60)
    webhook_max_attempts: int = Field(default=5, ge=1, le=20)
    webhook_backoff_seconds: float = Field(default=2, gt=0)
    webhook_max_backoff_seconds: float = Field(default=300, gt=0)
    worker_poll_seconds: float = Field(default=1, gt=0)
    delivery_lease_seconds: int = Field(default=300, ge=30)
    analysis_deadline_seconds: int = Field(default=1800, ge=60)
    event_batch_size: int = Field(default=100, ge=1, le=1000)
    workflow_delivery_max_attempts: int = Field(default=5, ge=1, le=20)


class EmptyCommand(Contract):
    pass


class DeliveryAccepted(Contract):
    delivery_id: UUID
    status: str


class ProjectBindingView(Contract):
    project_id: UUID
    binding_type: str
    status: str


class IntegrationOptions(Contract):
    scopes: tuple[IntegrationScope, ...]
    webhook_events: tuple[str, ...]
    credential_types: tuple[str, ...] = ("OAUTH2", "SERVICE_ACCOUNT")
    deployment_classes: tuple[str, ...] = ("EXTERNAL", "INTERNAL")


class ClientCreate(Contract):
    display_name: str = Field(min_length=1, max_length=200)
    allowed_scopes: tuple[IntegrationScope, ...] = Field(min_length=1, max_length=8)
    credential_type: str = Field(default="OAUTH2", pattern="^(OAUTH2|SERVICE_ACCOUNT)$")


class ClientUpdate(Contract):
    expected_version: int = Field(ge=1)
    status: str = Field(pattern="^(ACTIVE|DISABLED|REVOKED)$")
    allowed_scopes: tuple[IntegrationScope, ...] | None = None


class VersionCommand(Contract):
    expected_version: int = Field(ge=1)


class ProjectBindingCommand(VersionCommand):
    project_id: UUID
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|REVOKED)$")


class ClientView(Contract):
    client_id: UUID
    display_name: str
    status: str
    allowed_scopes: tuple[IntegrationScope, ...]
    credential_type: str
    record_version: int
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None
    credential_configured: bool


class ClientCredentialView(Contract):
    client: ClientView
    credential_id: UUID
    # Only mutation response, never a GET/persisted metadata payload.
    credential: str | None = Field(default=None, json_schema_extra={"writeOnly": True})


class TokenRequest(Contract):
    grant_type: str = Field(pattern="^client_credentials$")
    client_id: UUID
    client_secret: SecretStr
    scope: str | None = Field(default=None, max_length=500)


class TokenView(Contract):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


class IntegrationPrincipal(Contract):
    client_id: UUID
    tenant_id: UUID
    credential_id: UUID
    scopes: tuple[IntegrationScope, ...]


class GatewayError(Contract):
    error_code: str
    message: str
    details: dict = Field(default_factory=dict)
    trace_id: str
    retryable: bool = False


class ExternalWorkflowAccepted(Contract):
    schema_version: str = "1.0"
    project_id: UUID
    analysis_snapshot_id: UUID
    workflow_run_id: UUID
    status: str
    status_url: str
    result_url: str
    events_url: str


class ExternalWorkflowEvent(Contract):
    event_id: UUID
    schema_version: str = "1.0"
    event_code: str
    timestamp: datetime
    project_id: UUID
    workflow_run_id: UUID
    analysis_snapshot_id: UUID
    status: str | None = None
    step: str | None = None
    result_ref: str | None = None
    review_ref: UUID | None = None
    reason_codes: tuple[str, ...] = ()
    correlation_id: str | None = None


WEBHOOK_EVENTS = frozenset(
    {
        "WORKFLOW_STARTED",
        "WORKFLOW_PROGRESS",
        "REVIEW_REQUIRED",
        "WORKFLOW_COMPLETED",
        "WORKFLOW_FAILED",
    }
)
PROGRESS_SOURCE_EVENTS = frozenset({"NODE_STARTED", "NODE_PROGRESS", "NODE_COMPLETED"})


def external_event_code(code):
    return "WORKFLOW_PROGRESS" if code in PROGRESS_SOURCE_EVENTS else code


class WebhookCreate(Contract):
    callback_url: str = Field(min_length=1, max_length=2048)
    event_codes: tuple[str, ...] = Field(min_length=1, max_length=5)
    deployment_class: str = Field(default="EXTERNAL", pattern="^(EXTERNAL|INTERNAL)$")


class WebhookUpdate(VersionCommand):
    enabled: bool
    callback_url: str | None = Field(default=None, min_length=1, max_length=2048)
    event_codes: tuple[str, ...] | None = Field(default=None, min_length=1, max_length=5)


class WebhookView(Contract):
    subscription_id: UUID
    client_id: UUID
    callback_url: str
    event_codes: tuple[str, ...]
    enabled: bool
    record_version: int
    secret_configured: bool
    deployment_class: str = "EXTERNAL"


class WebhookSecretView(Contract):
    subscription: WebhookView
    secret: str | None = Field(default=None, json_schema_extra={"writeOnly": True})


class DeliveryView(Contract):
    delivery_id: UUID
    subscription_id: UUID
    event_id: UUID
    status: str
    attempts: int
    last_status_code: int | None
    error_code: str | None
    next_attempt_at: datetime
