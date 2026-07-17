from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Validated environment configuration shared by all deployables (LLD §3.1)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = Field(..., min_length=1)
    environment: str = Field(default="development", pattern=r"^(development|staging|production)$")
    cell_id: str = Field(default="local", min_length=1)
    region: str = Field(default="local", min_length=1)
    log_level: str = Field(default="INFO")
    otel_enabled: bool = Field(default=True)
    otel_exporter_endpoint: str | None = Field(default=None)
    otel_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
