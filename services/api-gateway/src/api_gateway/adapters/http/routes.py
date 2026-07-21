from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from api_gateway.container import GatewayContainer

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    upstream_mode: str


class MintTokenRequest(BaseModel):
    """Local/dev helper — production uses IdP/BFF only."""

    subject_id: UUID
    tenant_ids: list[UUID] = Field(min_length=1)
    scopes: list[str] = Field(default_factory=lambda: ["tasks:read", "tasks:write"])


class MintTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    session_cookie: str | None = None


def get_container(request: Request) -> GatewayContainer:
    return request.app.state.container  # type: ignore[no-any-return]


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="api-gateway")


@router.get("/ready", response_model=ReadyResponse, tags=["ops"])
async def ready(request: Request) -> ReadyResponse:
    container = get_container(request)
    mode = "echo" if container.settings.use_echo_upstream else "httpx"
    return ReadyResponse(status="ready", service="api-gateway", upstream_mode=mode)


@router.post("/v1/gateway/dev/mint-token", response_model=MintTokenResponse, tags=["dev"])
async def mint_token(body: MintTokenRequest, request: Request) -> MintTokenResponse:
    """Dev-only token mint for local integration; disabled conceptually in prod IdP flow."""
    container = get_container(request)
    token = container.tokens.mint(
        subject_id=body.subject_id,
        tenant_ids=tuple(body.tenant_ids),
        scopes=frozenset(body.scopes),
    )
    session = container.tokens.mint_session(
        subject_id=body.subject_id,
        tenant_ids=tuple(body.tenant_ids),
        scopes=frozenset(body.scopes),
    )
    return MintTokenResponse(access_token=token, session_cookie=session)


async def proxy_catch_all(request: Request) -> Response:
    """Catch-all reverse proxy for cell service routes."""
    container = get_container(request)
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    cookies = dict(request.cookies)
    client_ip = request.client.host if request.client else "0.0.0.0"
    status, resp_headers, resp_body = await container.middleware.handle(
        method=request.method,
        path=request.url.path,
        query_string=request.url.query,
        headers=headers,
        body=body,
        client_ip=client_ip,
        cookies=cookies,
    )
    # Starlette Response wants media-friendly headers
    excluded = {"content-length", "content-encoding"}
    clean: dict[str, str] = {
        k: v for k, v in resp_headers.items() if k.lower() not in excluded
    }
    return Response(content=resp_body, status_code=status, headers=clean)


def register_proxy_routes(app: Any) -> None:
    """Register method-agnostic catch-all after explicit routes."""
    app.add_api_route(
        "/v1/{path:path}",
        proxy_catch_all,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=True,
        tags=["proxy"],
        name="proxy_v1",
    )
