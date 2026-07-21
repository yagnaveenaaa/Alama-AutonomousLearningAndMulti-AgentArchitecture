from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class PolicySettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="POLICY_", extra="ignore")

    service_name: str = Field(default="policy-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8104)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5436/policy",
    )
    use_in_memory_store: bool = Field(default=True)
    default_bundle_version: str = Field(default="policy.v1")
