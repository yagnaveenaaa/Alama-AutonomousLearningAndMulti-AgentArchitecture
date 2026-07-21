from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class GatewaySettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="GATEWAY_", extra="ignore")

    service_name: str = Field(default="api-gateway")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    jwt_hmac_secret: str = Field(default="alama-local-dev-hmac-secret-change-me")
    jwt_audience: str = Field(default="alama-api")
    jwt_issuer: str = Field(default="alama-local")
    session_cookie_name: str = Field(default="alama_session")
    max_body_bytes: int = Field(default=1_048_576, ge=1024)  # 1 MiB default
    proxy_timeout_seconds: float = Field(default=30.0, ge=1.0)
    rate_limit_ip_per_minute: int = Field(default=600, ge=1)
    rate_limit_subject_per_minute: int = Field(default=300, ge=1)
    rate_limit_tenant_per_minute: int = Field(default=3000, ge=1)
    # JSON map: tenant_id → cell base URL (e.g. http://cell-a:8080)
    # Empty = use default_cell_base_url for all tenants.
    tenant_cell_map_json: str = Field(default="{}")
    default_cell_base_url: str = Field(default="http://127.0.0.1:8101")
    # Service path prefixes → upstream host:port within the cell
    identity_upstream: str = Field(default="http://127.0.0.1:8101")
    repository_upstream: str = Field(default="http://127.0.0.1:8102")
    task_upstream: str = Field(default="http://127.0.0.1:8103")
    policy_upstream: str = Field(default="http://127.0.0.1:8104")
    retrieval_upstream: str = Field(default="http://127.0.0.1:8105")
    knowledge_upstream: str = Field(default="http://127.0.0.1:8106")
    use_echo_upstream: bool = Field(
        default=True,
        description="Local/tests: echo proxy without real backends",
    )
