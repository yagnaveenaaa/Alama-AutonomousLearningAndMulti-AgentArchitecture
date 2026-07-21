from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class AuditSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="AUDIT_", extra="ignore")

    service_name: str = Field(default="audit-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8109)
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5438/audit",
    )
    use_in_memory_store: bool = Field(default=True)
    export_object_prefix: str = Field(default="audit-exports")
