from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class RepositorySettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="REPOSITORY_", extra="ignore")

    service_name: str = Field(default="repository-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8102)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5433/repository",
    )
    use_in_memory_store: bool = Field(default=True)
