from __future__ import annotations

import json
from typing import Any

import httpx


class HttpxUpstreamClient:
    """Reverse proxy transport with timeout/deadline propagation (LLD §2.1)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(follow_redirects=False)
        return self._client

    async def forward(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        content: bytes,
        timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        client = await self._ensure()
        response = await client.request(
            method,
            url,
            headers=headers,
            content=content,
            timeout=timeout,
        )
        out_headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in {"transfer-encoding", "content-encoding", "connection"}
        }
        return response.status_code, out_headers, response.content


class EchoUpstreamClient:
    """Local stand-in that echoes the proxied request (no real backends)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def aclose(self) -> None:
        return None

    async def forward(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        content: bytes,
        timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        record = {
            "method": method,
            "url": url,
            "headers": dict(headers),
            "content": content,
            "timeout": timeout,
        }
        self.calls.append(record)
        lower = {k.lower(): v for k, v in headers.items()}
        body = json.dumps(
            {
                "echo": True,
                "method": method,
                "url": url,
                "subject_id": lower.get("x-subject-id"),
                "tenant_id": lower.get("x-tenant-id"),
                "request_id": lower.get("x-request-id"),
            }
        ).encode("utf-8")
        return 200, {"content-type": "application/json"}, body
