from __future__ import annotations

from uuid import UUID

from alama_common.pagination import decode_cursor, encode_cursor

from audit_service.domain.models import AuditEvent, LegalHold


class InMemoryObjectStore:
    def __init__(self) -> None:
        self._objects: dict[str, dict[str, object]] = {}

    async def put(self, object_ref: str, payload: dict[str, object]) -> str:
        self._objects[object_ref] = dict(payload)
        return object_ref

    async def get(self, object_ref: str) -> dict[str, object] | None:
        payload = self._objects.get(object_ref)
        return dict(payload) if payload is not None else None


class InMemoryOutbox:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def publish(self, topic: str, payload: dict[str, object]) -> None:
        self.messages.append({"topic": topic, "payload": dict(payload)})


class InMemoryAuditStore:
    def __init__(self) -> None:
        self.events: dict[UUID, list[AuditEvent]] = {}
        self.holds: dict[UUID, LegalHold] = {}
        self.objects = InMemoryObjectStore()
        self.outbox = InMemoryOutbox()


class InMemoryAuditEventRepository:
    def __init__(self, store: InMemoryAuditStore) -> None:
        self._store = store

    async def append(self, event: AuditEvent) -> None:
        self._store.events.setdefault(event.tenant_id, []).append(event)

    async def get_latest_hash(self, tenant_id: UUID) -> str | None:
        items = self._store.events.get(tenant_id, [])
        if not items:
            return None
        return items[-1].integrity_hash

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        action: str | None,
        actor_id: str | None,
        resource_type: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[AuditEvent], str | None]:
        items = list(self._store.events.get(tenant_id, []))
        items.sort(key=lambda e: e.created_at, reverse=True)
        if action:
            items = [e for e in items if e.action == action]
        if actor_id:
            items = [e for e in items if e.actor_id == actor_id]
        if resource_type:
            items = [e for e in items if e.resource_type == resource_type]
        offset = 0
        if cursor:
            offset = int(decode_cursor(cursor).get("offset", 0))
        page = items[offset : offset + limit]
        next_cursor = (
            encode_cursor({"offset": offset + limit}) if offset + limit < len(items) else None
        )
        return page, next_cursor

    async def list_all_ordered(self, tenant_id: UUID) -> list[AuditEvent]:
        items = list(self._store.events.get(tenant_id, []))
        items.sort(key=lambda e: e.created_at)
        return items


class InMemoryLegalHoldRepository:
    def __init__(self, store: InMemoryAuditStore) -> None:
        self._store = store

    async def get(self, tenant_id: UUID) -> LegalHold | None:
        return self._store.holds.get(tenant_id)

    async def save(self, hold: LegalHold) -> None:
        self._store.holds[hold.tenant_id] = hold
