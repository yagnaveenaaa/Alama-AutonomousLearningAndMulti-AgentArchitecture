from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class KnowledgeSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="KNOWLEDGE_", extra="ignore")

    service_name: str = Field(default="knowledge-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8106)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5437/knowledge",
    )
    use_in_memory_store: bool = Field(default=True)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    default_conversation_retention_days: int = Field(default=90, ge=1)
