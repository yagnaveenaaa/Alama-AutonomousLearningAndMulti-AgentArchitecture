from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from alama_common.auth import Principal


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Forward principal + tenant to cell clients (LLD §2.2)."""

    principal: Principal
    tenant_id: UUID
    request_id: UUID
    authorization: str | None = None

    @property
    def subject_id(self) -> UUID:
        return self.principal.subject_id

    def identity_headers(self) -> dict[str, str]:
        headers = {
            "X-Subject-Id": str(self.subject_id),
            "X-Tenant-Id": str(self.tenant_id),
            "X-Request-Id": str(self.request_id),
        }
        if self.authorization:
            headers["Authorization"] = self.authorization
        return headers


class AuthContextFactory(Protocol):
    def from_headers(
        self,
        *,
        subject_id: str | None,
        tenant_id: str | None,
        authorization: str | None,
    ) -> AuthContext: ...
