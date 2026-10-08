"""Allowlisted provider/model views; credentials and secret references are absent."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from crossborder_compliance.domain.llm_gateway import ModelOperation
from crossborder_compliance.domain.metadata import GovernanceStatus, ModelCapabilityCode
from crossborder_compliance.domain.model_control import ControlCommand


class AllowlistedModelView(BaseModel):
    model_config = ConfigDict(extra="ignore", json_schema_extra={"additionalProperties": False})


class ProviderVersionView(AllowlistedModelView):
    provider_id: UUID
    provider_version_id: UUID
    provider_version: int
    display_name: str
    vendor_preset: str
    protocol: str
    base_url: str | None
    deployment_class: str
    trust_level: str
    data_boundary: str
    secret_configured: bool
    enabled: bool
    lifecycle_status: GovernanceStatus
    record_version: int
    effective_from: date | None
    effective_to: date | None


class ProviderView(AllowlistedModelView):
    provider_id: UUID
    code: str
    display_name: str
    enabled: bool
    record_version: int
    active_version_id: UUID | None
    versions: tuple[ProviderVersionView, ...]


class ProviderListView(AllowlistedModelView):
    providers: tuple[ProviderView, ...]


class ModelView(AllowlistedModelView):
    model_id: UUID
    provider_id: UUID
    deployment_id: UUID
    provider_version_id: UUID
    display_name: str
    remote_model_name: str
    capabilities: tuple[ModelCapabilityCode, ...]
    operations: tuple[ModelOperation, ...]
    max_output_tokens: int
    embedding_dimension: int | None
    priority: int
    structured_output_format: Literal["json_schema", "json_object"]
    enabled: bool
    lifecycle_status: GovernanceStatus
    record_version: int
    model_record_version: int
    health_status: str


class ModelListView(AllowlistedModelView):
    models: tuple[ModelView, ...]


class ProviderTestResult(AllowlistedModelView):
    status: Literal[
        "HEALTHY",
        "AUTHENTICATION_FAILED",
        "ENDPOINT_UNREACHABLE",
        "TLS_ERROR",
        "MODEL_ENDPOINT_INVALID",
        "CAPABILITY_UNSUPPORTED",
        "SECRET_UNAVAILABLE",
        "TIMEOUT",
    ]
    candidate_models: tuple[str, ...] = ()


class ModelTestRequest(ControlCommand):
    operation: Literal["chat", "structured_output", "embedding"] = "chat"


class EnabledView(AllowlistedModelView):
    enabled: bool
    record_version: int = Field(ge=1)
