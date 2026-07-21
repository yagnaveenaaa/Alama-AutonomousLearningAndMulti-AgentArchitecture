from __future__ import annotations

from dataclasses import dataclass

from api_gateway.authn.local_jwt import LocalJwtTokenValidator
from api_gateway.config import GatewaySettings
from api_gateway.middleware.gateway import GatewayMiddleware
from api_gateway.proxy.upstream import EchoUpstreamClient, HttpxUpstreamClient
from api_gateway.ratelimit.memory import InMemoryRateLimiter
from api_gateway.routing.tenant_router import StaticTenantRouter


@dataclass
class GatewayContainer:
    settings: GatewaySettings
    tokens: LocalJwtTokenValidator
    router: StaticTenantRouter
    rate_limiter: InMemoryRateLimiter
    upstream: EchoUpstreamClient | HttpxUpstreamClient
    middleware: GatewayMiddleware


def build_container(settings: GatewaySettings | None = None) -> GatewayContainer:
    settings = settings or GatewaySettings()
    tokens = LocalJwtTokenValidator(
        secret=settings.jwt_hmac_secret,
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    router = StaticTenantRouter.from_settings(
        tenant_cell_map_json=settings.tenant_cell_map_json,
        default_cell_base_url=settings.default_cell_base_url,
        identity_upstream=settings.identity_upstream,
        repository_upstream=settings.repository_upstream,
        task_upstream=settings.task_upstream,
        policy_upstream=settings.policy_upstream,
        retrieval_upstream=settings.retrieval_upstream,
        knowledge_upstream=settings.knowledge_upstream,
    )
    rate_limiter = InMemoryRateLimiter(
        ip_per_minute=settings.rate_limit_ip_per_minute,
        subject_per_minute=settings.rate_limit_subject_per_minute,
        tenant_per_minute=settings.rate_limit_tenant_per_minute,
    )
    upstream: EchoUpstreamClient | HttpxUpstreamClient = (
        EchoUpstreamClient() if settings.use_echo_upstream else HttpxUpstreamClient()
    )
    middleware = GatewayMiddleware(
        tokens,
        router,
        rate_limiter,
        upstream,
        session_cookie_name=settings.session_cookie_name,
        max_body_bytes=settings.max_body_bytes,
        proxy_timeout_seconds=settings.proxy_timeout_seconds,
    )
    return GatewayContainer(
        settings=settings,
        tokens=tokens,
        router=router,
        rate_limiter=rate_limiter,
        upstream=upstream,
        middleware=middleware,
    )
