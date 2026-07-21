from __future__ import annotations

from datetime import UTC, datetime

from alama_common.ids import new_uuid7

from audit_service.application.dto import IngestAuditCommand
from audit_service.domain.integrity import IntegrityHasher
from audit_service.domain.models import AuditEvent
from audit_service.domain.repositories import (
    AuditEventRepository,
    AuditObjectStore,
    LegalHoldRepository,
    OutboxPublisher,
)


class AuditIngestor:
    """Validate schema → persist → outbox (Kafka stand-in) (LLD §2.11)."""

    def __init__(
        self,
        events: AuditEventRepository,
        objects: AuditObjectStore,
        outbox: OutboxPublisher,
        hasher: IntegrityHasher,
        holds: LegalHoldRepository,
    ) -> None:
        self._events = events
        self._objects = objects
        self._outbox = outbox
        self._hasher = hasher
        self._holds = holds

    async def ingest(self, command: IngestAuditCommand) -> AuditEvent:
        event_id = new_uuid7()
        created_at = datetime.now(UTC)
        prev = await self._events.get_latest_hash(command.tenant_id)
        prev_hash = prev or IntegrityHasher.GENESIS
        object_ref = f"audit/{command.tenant_id}/{event_id}.json"
        await self._objects.put(
            object_ref,
            {
                "action": command.action,
                "payload": dict(command.payload),
                "resource_type": command.resource_type,
                "resource_id": command.resource_id,
            },
        )
        integrity_hash = self._hasher.hash_event(
            tenant_id=command.tenant_id,
            actor_type=command.actor_type,
            actor_id=command.actor_id,
            action=command.action,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            decision=command.decision,
            policy_version=command.policy_version,
            object_ref=object_ref,
            payload=dict(command.payload),
            prev_hash=prev_hash,
            event_id=event_id,
            created_at_iso=created_at.isoformat(),
        )
        hold = await self._holds.get(command.tenant_id)
        event = AuditEvent(
            id=event_id,
            tenant_id=command.tenant_id,
            actor_type=command.actor_type,
            actor_id=command.actor_id,
            action=command.action.strip(),
            resource_type=command.resource_type.strip(),
            resource_id=command.resource_id,
            decision=command.decision,
            policy_version=command.policy_version,
            object_ref=object_ref,
            created_at=created_at,
            payload=dict(command.payload),
            integrity_hash=integrity_hash,
            prev_hash=prev_hash,
            legal_hold=bool(hold and hold.active),
        )
        await self._events.append(event)
        await self._outbox.publish(
            "audit.events.v1",
            {
                "id": str(event.id),
                "tenant_id": str(event.tenant_id),
                "action": event.action,
                "integrity_hash": event.integrity_hash,
            },
        )
        return event
