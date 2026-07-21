from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class TaskSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="TASK_", extra="ignore")

    service_name: str = Field(default="task-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8103)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5435/task",
    )
    use_in_memory_store: bool = Field(default=True)
    default_budget_tokens: int = Field(default=1_000_000, ge=1)
    default_budget_usd_micros: int = Field(default=5_000_000, ge=1)
    policy_version: str = Field(default="policy.v1")
