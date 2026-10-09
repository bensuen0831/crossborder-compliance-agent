"""Provider-neutral typed control-plane commands. Credentials are write-only."""

from datetime import date
from typing import Literal
from urllib.parse import unquote, urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from crossborder_compliance.domain.llm_gateway import ModelOperation
from crossborder_compliance.domain.metadata import GovernanceStatus, ModelCapabilityCode


class ControlCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderDraft(ControlCommand):
    provider_id: UUID | None = None
    expected_record_version: int | None = Field(default=None, ge=1)
    code: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    display_name: str = Field(min_length=1, max_length=200)
    vendor_preset: str = Field(default="OTHER_OPENAI_COMPATIBLE", max_length=80)
    protocol: Literal["OPENAI_COMPATIBLE", "GENERIC_REST"] = "OPENAI_COMPATIBLE"
    operation_paths: dict[ModelOperation, str] = Field(default_factory=dict)
    base_url: str = Field(min_length=1, max_length=400)
    deployment_class: Literal["EXTERNAL", "PRIVATE_CLOUD", "ON_PREMISE"] = "EXTERNAL"
    trust_level: str = Field(min_length=1, max_length=80)
    data_boundary: str = Field(min_length=1, max_length=160)
    credential: SecretStr | None = Field(default=None, repr=False, exclude=True)
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    health_ttl_seconds: int = Field(default=300, ge=1, le=86400)
    effective_from: date
    effective_to: date | None = None

    @field_validator("operation_paths")
    @classmethod
    def relative_paths(cls, values):
        for path in values.values():
            decoded = unquote(path)
            parsed = urlparse(decoded)
            if (
                not path.startswith("/")
                or path.startswith("//")
                or parsed.netloc
                or parsed.scheme
                or parsed.query
                or parsed.fragment
                or ".." in decoded
                or "\\" in decoded
                or any(ord(c) < 32 for c in decoded)
            ):
                raise ValueError("MODEL_OPERATION_PATH_INVALID")
        return values


class ModelDraft(ControlCommand):
    model_id: UUID | None = None
    expected_record_version: int | None = Field(default=None, ge=1)
    provider_version_id: UUID
    remote_model_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    capabilities: tuple[ModelCapabilityCode, ...] = Field(min_length=1)
    operations: tuple[ModelOperation, ...] = Field(min_length=1)
    max_output_tokens: int = Field(ge=1, le=65536)
    embedding_dimension: int | None = Field(default=None, ge=1, le=16000)
    priority: int = Field(default=100, ge=0, le=10000)
    structured_output_format: Literal["json_schema", "json_object"] = "json_schema"
    effective_from: date
    effective_to: date | None = None


class ControlTransition(ControlCommand):
    target_status: GovernanceStatus
    expected_record_version: int = Field(ge=1)


class ControlEnabled(ControlCommand):
    enabled: bool
    expected_record_version: int = Field(ge=1)
