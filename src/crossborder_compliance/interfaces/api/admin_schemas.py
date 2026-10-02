from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AdminDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=250)
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_definition_id: str | None = None


class AdminDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_record_version: int = Field(ge=1)


class AdminTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_record_version: int = Field(ge=1)
