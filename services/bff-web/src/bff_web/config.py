from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class BffSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="BFF_", extra="ignore")

    service_name: str = Field(default="bff-web")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8081)
    use_in_memory_clients: bool = Field(default=True)
    task_service_url: str = Field(default="http://127.0.0.1:8103")
    repository_service_url: str = Field(default="http://127.0.0.1:8102")
    knowledge_service_url: str = Field(default="http://127.0.0.1:8106")
    usage_service_url: str = Field(default="http://127.0.0.1:8110")
    api_gateway_url: str = Field(default="http://127.0.0.1:8080")
    stream_base_url: str = Field(default="http://127.0.0.1:8080")
