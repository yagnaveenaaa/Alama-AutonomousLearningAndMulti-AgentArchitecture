from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class RetrievalSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="RETRIEVAL_", extra="ignore")

    service_name: str = Field(default="retrieval-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8105)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5434/alama_index_meta"
    )
    use_in_memory_store: bool = Field(default=True)
