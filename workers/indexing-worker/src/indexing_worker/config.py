from __future__ import annotations

from alama_common.config.base import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class IndexingWorkerSettings(BaseServiceSettings):
    """Typed settings for indexing-worker (LLD §3.1)."""

    model_config = SettingsConfigDict(env_prefix="INDEXING_WORKER_", extra="ignore")

    service_name: str = Field(default="indexing-worker")
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5434/alama_index_meta"
    )
    use_in_memory_store: bool = Field(default=True)
    embedding_model: str = Field(default="alama-embed-v1")
    embedding_dim: int = Field(default=64, ge=8, le=4096)
    max_chunk_tokens: int = Field(default=1000, ge=100, le=4000)
    supported_languages: str = Field(default="python")
    poll_interval_seconds: float = Field(default=1.0, ge=0.1)
