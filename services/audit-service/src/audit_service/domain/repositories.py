from __future__ import annotations

from typing import Protocol
from uuid import UUID

from audit_service.domain.models import AuditEvent, LegalHold


class AuditEventRepository(Protocol):
    async def append(self, event: AuditEvent) -> None: ...

    async def get_latest_hash(self, tenant_id: UUID) -> str | None: ...

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        action: str | None,
        actor_id: str | None,
        resource_type: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[AuditEvent], str | None]: ...

    async def list_all_ordered(self, tenant_id: UUID) -> list[AuditEvent]: ...


class AuditObjectStore(Protocol):
    async def put(self, object_ref: str, payload: dict[str, object]) -> str: ...

    async def get(self, object_ref: str) -> dict[str, object] | None: ...


class LegalHoldRepository(Protocol):
    async def get(self, tenant_id: UUID) -> LegalHold | None: ...

    async def save(self, hold: LegalHold) -> None: ...


class OutboxPublisher(Protocol):
    """Kafka-class stand-in for audit fan-out (LLD §2.11)."""

    async def publish(self, topic: str, payload: dict[str, object]) -> None: ...
