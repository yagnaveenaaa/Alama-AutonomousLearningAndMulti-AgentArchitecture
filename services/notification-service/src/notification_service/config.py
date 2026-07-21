from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class NotificationSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIFICATION_", extra="ignore")

    service_name: str = Field(default="notification-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8111)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5440/notification",
    )
    use_in_memory_store: bool = Field(default=True)
    # Retry knobs (LLD §3.3 — default matches RetryPolicy.notification)
    retry_max_attempts: int = Field(default=8, ge=1)
    retry_initial_backoff_ms: int = Field(default=500, ge=0)
    retry_max_backoff_ms: int = Field(default=3_600_000, ge=0)
    retry_jitter: bool = Field(default=True)
