from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplicationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=False)


class ProjectDTO(ApplicationDTO):
    project_id: UUID
    tenant_id: UUID
    organization_id: UUID | None = None
    name: str
    active_version_id: UUID | None = None
    record_version: int = Field(ge=1)
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectVersionDTO(ApplicationDTO):
    project_version_id: UUID
    tenant_id: UUID
    project_id: UUID
    version_no: int = Field(ge=1)
    intake_json: dict[str, object]
    effective_from: date | None = None
    effective_to: date | None = None
    record_version: int = Field(ge=1)
    status: str


class ConversationThreadDTO(ApplicationDTO):
    conversation_thread_id: UUID
    tenant_id: UUID
    session_id: UUID
    project_id: UUID | None = None
    title: str | None = None
    record_version: int = Field(ge=1)
    status: str
