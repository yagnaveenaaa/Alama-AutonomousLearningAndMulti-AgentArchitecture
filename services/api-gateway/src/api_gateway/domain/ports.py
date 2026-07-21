from __future__ import annotations

from typing import Protocol
from uuid import UUID

from alama_common.auth import Principal


class TokenValidator(Protocol):
    """Validate bearer/cookie → Principal (LLD §2.1)."""

    async def validate_bearer(self, token: str) -> Principal: ...

    async def validate_session_cookie(self, cookie_value: str) -> Principal: ...


class TenantRouter(Protocol):
    """Map tenant → cell endpoint (LLD §2.1)."""

    def resolve_cell_base(self, tenant_id: UUID) -> str: ...

    def resolve_upstream(self, path: str, tenant_id: UUID) -> tuple[str, str]:
        """Return (upstream_base_url, path_to_forward)."""
        ...


class RateLimiter(Protocol):
    """Hierarchical limits: IP, subject, tenant (LLD §2.1)."""

    async def check(
        self,
        *,
        ip: str,
        subject_id: UUID,
        tenant_id: UUID,
    ) -> None: ...


class UpstreamClient(Protocol):
    async def forward(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        content: bytes,
        timeout: float,
    ) -> tuple[int, dict[str, str], bytes]: ...
