from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class ToolGatewaySettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="TOOL_GATEWAY_", extra="ignore")

    service_name: str = Field(default="tool-gateway")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8108)
    capability_signing_key: str = Field(default="local-dev-capability-key")
    capability_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    max_output_bytes: int = Field(default=65_536, ge=1024, le=10_000_000)
    policy_version: str = Field(default="policy.v1")
