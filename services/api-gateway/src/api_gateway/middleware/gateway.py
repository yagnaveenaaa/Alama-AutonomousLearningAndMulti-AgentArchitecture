from __future__ import annotations

from alama_common.auth import Principal
from alama_common.errors import AuthenticationError, ValidationError
from alama_common.ids import new_uuid7

from api_gateway.domain.ports import (
    RateLimiter,
    TenantRouter,
    TokenValidator,
    UpstreamClient,
)


class GatewayMiddleware:
    """Compose auth → route → limit → proxy (LLD §2.1)."""

    def __init__(
        self,
        tokens: TokenValidator,
        router: TenantRouter,
        rate_limiter: RateLimiter,
        upstream: UpstreamClient,
        *,
        session_cookie_name: str,
        max_body_bytes: int,
        proxy_timeout_seconds: float,
    ) -> None:
        self._tokens = tokens
        self._router = router
        self._rate_limiter = rate_limiter
        self._upstream = upstream
        self._session_cookie_name = session_cookie_name
        self._max_body_bytes = max_body_bytes
        self._proxy_timeout = proxy_timeout_seconds

    async def handle(
        self,
        *,
        method: str,
        path: str,
        query_string: str,
        headers: dict[str, str],
        body: bytes,
        client_ip: str,
        cookies: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        if len(body) > self._max_body_bytes:
            raise ValidationError(
                "Request body too large",
                details={"max_body_bytes": self._max_body_bytes},
            )

        principal = await self._authenticate(headers, cookies)
        tenant_id = principal.primary_tenant_id()
        await self._rate_limiter.check(
            ip=client_ip,
            subject_id=principal.subject_id,
            tenant_id=tenant_id,
        )

        full_path = path if not query_string else f"{path}?{query_string}"
        upstream_base, forward_path = self._router.resolve_upstream(path, tenant_id)
        url = f"{upstream_base}{forward_path}"
        if query_string and "?" not in forward_path:
            url = f"{url}?{query_string}"

        request_id = headers.get("x-request-id") or str(new_uuid7())
        out_headers = self._forward_headers(headers, principal, request_id)
        status, resp_headers, resp_body = await self._upstream.forward(
            method=method,
            url=url,
            headers=out_headers,
            content=body,
            timeout=self._proxy_timeout,
        )
        resp_headers = dict(resp_headers)
        resp_headers.setdefault("x-request-id", request_id)
        resp_headers.setdefault("x-alama-cell", self._router.resolve_cell_base(tenant_id))
        _ = full_path
        return status, resp_headers, resp_body

    async def _authenticate(
        self,
        headers: dict[str, str],
        cookies: dict[str, str],
    ) -> Principal:
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            if not token:
                raise AuthenticationError("Empty bearer token")
            return await self._tokens.validate_bearer(token)

        session = cookies.get(self._session_cookie_name)
        if session:
            return await self._tokens.validate_session_cookie(session)

        raise AuthenticationError("Missing Authorization bearer or session cookie")

    def _forward_headers(
        self,
        inbound: dict[str, str],
        principal: Principal,
        request_id: str,
    ) -> dict[str, str]:
        hop_by_hop = {
            "host",
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "content-length",
            "authorization",
            "cookie",
        }
        out: dict[str, str] = {}
        for key, value in inbound.items():
            if key.lower() in hop_by_hop:
                continue
            out[key] = value
        out["X-Subject-Id"] = str(principal.subject_id)
        out["X-Tenant-Id"] = str(principal.primary_tenant_id())
        out["X-Request-Id"] = request_id
        if principal.session_id is not None:
            out["X-Session-Id"] = str(principal.session_id)
        if "traceparent" in {k.lower() for k in inbound}:
            for key, value in inbound.items():
                if key.lower() == "traceparent":
                    out["traceparent"] = value
                    break
        return out
