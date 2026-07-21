from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class UsageSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="USAGE_", extra="ignore")

    service_name: str = Field(default="usage-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8110)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5439/usage",
    )
    use_in_memory_store: bool = Field(default=True)
    default_limit_tokens: int = Field(default=1_000_000, ge=0)
    default_limit_usd_micros: int = Field(default=5_000_000, ge=0)
    default_soft_pct: float = Field(default=0.8, ge=0.0, le=1.0)
    anomaly_spike_ratio: float = Field(default=3.0, ge=1.0)
    anomaly_min_baseline_events: int = Field(default=3, ge=1)
