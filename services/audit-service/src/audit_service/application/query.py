from __future__ import annotations

from uuid import UUID

from audit_service.application.dto import QueryAuditCommand
from audit_service.domain.integrity import IntegrityHasher
from audit_service.domain.models import AuditEvent
from audit_service.domain.repositories import AuditEventRepository


class AuditQueryService:
    """Tenant-scoped search (LLD §2.11 / §5.6)."""

    def __init__(self, events: AuditEventRepository, hasher: IntegrityHasher) -> None:
        self._events = events
        self._hasher = hasher

    async def list_events(
        self, command: QueryAuditCommand
    ) -> tuple[list[AuditEvent], str | None]:
        return await self._events.list_for_tenant(
            command.tenant_id,
            action=command.action,
            actor_id=command.actor_id,
            resource_type=command.resource_type,
            limit=command.limit,
            cursor=command.cursor,
        )

    async def verify_integrity(self, tenant_id: UUID) -> bool:
        ordered = await self._events.list_all_ordered(tenant_id)
        return self._hasher.verify_chain(ordered)
