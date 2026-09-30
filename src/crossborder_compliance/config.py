from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    app_env: Literal["LOCAL_DEV", "LOCAL_SERVER", "CLOUD_PRODUCTION", "RESTRICTED_NETWORK"] = "LOCAL_DEV"
    app_name: str = "crossborder-compliance-agent"
    database_url: str = "sqlite+pysqlite:///./phase1a.db"
    langgraph_database_uri: str = "postgresql://compliance:compliance@localhost:5432/compliance?sslmode=disable"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "compliance"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = Field(default="change-me", repr=False)
    langgraph_strict_msgpack: bool = True
    otel_service_name: str = "crossborder-compliance-agent"

    @property
    def is_production_like(self) -> bool:
        return self.app_env in {"LOCAL_SERVER", "CLOUD_PRODUCTION", "RESTRICTED_NETWORK"}

    def validate_runtime_safety(self) -> None:
        if self.is_production_like and not self.langgraph_strict_msgpack:
            raise ValueError("LANGGRAPH_STRICT_MSGPACK must be enabled in production-like profiles")
        if self.is_production_like and self.database_url.startswith("sqlite"):
            raise ValueError("PostgreSQL is required in production-like profiles")

@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate_runtime_safety()
    return s
