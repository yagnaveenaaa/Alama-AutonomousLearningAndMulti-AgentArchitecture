from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class ModelGatewaySettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="MODEL_GATEWAY_", extra="ignore")

    service_name: str = Field(default="model-gateway")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8107)
    default_completion_model: str = Field(default="alama-strong-v1")
    default_embedding_model: str = Field(default="alama-embed-v1")
    default_rerank_model: str = Field(default="alama-rerank-v1")
    embedding_dim: int = Field(default=64, ge=8, le=4096)
    tenant_token_quota: int = Field(default=1_000_000, ge=1)
    allow_provider_training: bool = Field(default=False)
