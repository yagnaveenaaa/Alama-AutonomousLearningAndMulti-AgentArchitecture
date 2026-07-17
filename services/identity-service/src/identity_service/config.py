from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class IdentitySettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="IDENTITY_", extra="ignore")

    service_name: str = Field(default="identity-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8101)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5432/identity",
    )
    use_in_memory_store: bool = Field(default=True)
    # Development principal bootstrap (gateway will inject real Principal later)
    bootstrap_subject_id: str | None = Field(default=None)
    bootstrap_tenant_id: str | None = Field(default=None)
