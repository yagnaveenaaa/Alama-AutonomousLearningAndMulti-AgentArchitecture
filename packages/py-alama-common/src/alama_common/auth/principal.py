from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller identity propagated across services (LLD §2.1)."""

    subject_id: UUID
    tenant_ids: tuple[UUID, ...]
    scopes: frozenset[str]
    session_id: UUID | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def can_access_tenant(self, tenant_id: UUID) -> bool:
        return tenant_id in self.tenant_ids

    def primary_tenant_id(self) -> UUID:
        if not self.tenant_ids:
            msg = "Principal has no tenant memberships"
            raise ValueError(msg)
        return self.tenant_ids[0]
