from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from api_gateway.config import GatewaySettings
from api_gateway.container import build_container
from api_gateway.main import create_app
from api_gateway.proxy.upstream import EchoUpstreamClient


@pytest.fixture
def settings() -> GatewaySettings:
    return GatewaySettings(
        use_echo_upstream=True,
        rate_limit_ip_per_minute=1000,
        rate_limit_subject_per_minute=1000,
        rate_limit_tenant_per_minute=1000,
        max_body_bytes=1024,
    )


@pytest.fixture
def container(settings: GatewaySettings):
    return build_container(settings)


@pytest.fixture
async def client(settings: GatewaySettings):
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as http,
        app.router.lifespan_context(app),
    ):
        yield http


@pytest.mark.asyncio
async def test_health_and_ready(client) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "api-gateway"
    ready = await client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["upstream_mode"] == "echo"


@pytest.mark.asyncio
async def test_proxy_requires_auth(client) -> None:
    response = await client.get("/v1/tasks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_proxy_with_bearer_injects_identity_headers(client) -> None:
    subject_id = uuid4()
    tenant_id = uuid4()
    mint = await client.post(
        "/v1/gateway/dev/mint-token",
        json={
            "subject_id": str(subject_id),
            "tenant_ids": [str(tenant_id)],
            "scopes": ["tasks:read"],
        },
    )
    assert mint.status_code == 200
    token = mint.json()["access_token"]

    response = await client.get(
        "/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["echo"] is True
    assert body["subject_id"] == str(subject_id)
    assert body["tenant_id"] == str(tenant_id)
    assert body["url"].endswith("/v1/tasks")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_proxy_session_cookie(client) -> None:
    subject_id = uuid4()
    tenant_id = uuid4()
    mint = await client.post(
        "/v1/gateway/dev/mint-token",
        json={
            "subject_id": str(subject_id),
            "tenant_ids": [str(tenant_id)],
        },
    )
    cookie = mint.json()["session_cookie"]
    response = await client.get(
        "/v1/memories",
        headers={"Cookie": f"alama_session={cookie}"},
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(tenant_id)


@pytest.mark.asyncio
async def test_unknown_route_404(client) -> None:
    subject_id = uuid4()
    tenant_id = uuid4()
    mint = await client.post(
        "/v1/gateway/dev/mint-token",
        json={
            "subject_id": str(subject_id),
            "tenant_ids": [str(tenant_id)],
        },
    )
    token = mint.json()["access_token"]
    response = await client.get(
        "/v1/unknown-thing",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_body_size_limit(client) -> None:
    subject_id = uuid4()
    tenant_id = uuid4()
    mint = await client.post(
        "/v1/gateway/dev/mint-token",
        json={
            "subject_id": str(subject_id),
            "tenant_ids": [str(tenant_id)],
        },
    )
    token = mint.json()["access_token"]
    response = await client.post(
        "/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
        content=b"x" * 2048,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rate_limit_subject(container) -> None:
    assert isinstance(container.upstream, EchoUpstreamClient)
    subject_id = uuid4()
    tenant_id = uuid4()
    token = container.tokens.mint(
        subject_id=subject_id,
        tenant_ids=(tenant_id,),
        scopes=frozenset({"tasks:read"}),
    )
    # Rebuild middleware with tiny subject limit
    from api_gateway.middleware.gateway import GatewayMiddleware
    from api_gateway.ratelimit.memory import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(
        ip_per_minute=1000,
        subject_per_minute=2,
        tenant_per_minute=1000,
    )
    mw = GatewayMiddleware(
        container.tokens,
        container.router,
        limiter,
        container.upstream,
        session_cookie_name="alama_session",
        max_body_bytes=1024,
        proxy_timeout_seconds=5.0,
    )
    headers = {"authorization": f"Bearer {token}"}
    await mw.handle(
        method="GET",
        path="/v1/tasks",
        query_string="",
        headers=headers,
        body=b"",
        client_ip="127.0.0.1",
        cookies={},
    )
    await mw.handle(
        method="GET",
        path="/v1/tasks",
        query_string="",
        headers=headers,
        body=b"",
        client_ip="127.0.0.1",
        cookies={},
    )
    with pytest.raises(Exception) as exc:
        await mw.handle(
            method="GET",
            path="/v1/tasks",
            query_string="",
            headers=headers,
            body=b"",
            client_ip="127.0.0.1",
            cookies={},
        )
    assert "rate limit" in str(exc.value).lower()
