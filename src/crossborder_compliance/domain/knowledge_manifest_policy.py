"""Deployment-independent bounded catalogue parsing limits in governed metadata."""

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeManifestLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_bytes: int = Field(default=32 * 1024**2, ge=1, le=128 * 1024**2)
    max_expanded_bytes: int = Field(default=128 * 1024**2, ge=1, le=1024**3)
    max_entries: int = Field(default=10000, ge=1, le=100000)
    max_rows: int = Field(default=20000, ge=1, le=100000)
    max_columns: int = Field(default=256, ge=2, le=4096)
    case_sensitive_paths: bool = True
