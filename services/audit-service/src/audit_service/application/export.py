from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from alama_common.errors import ConflictError
from alama_common.ids import new_uuid7

from audit_service.application.dto import (
    ExportAuditCommand,
    IngestAuditCommand,
    LegalHoldCommand,
)
from audit_service.application.ingest import AuditIngestor
from audit_service.domain.models import ActorType, AuditDecision, LegalHold
from audit_service.domain.repositories import (
    AuditEventRepository,
    AuditObjectStore,
    LegalHoldRepository,
)


@dataclass(frozen=True, slots=True)
class ExportResult:
    export_id: str
    object_ref: str
    event_count: int


class AuditExporter:
    """Region-aware export packages (LLD §2.11)."""

    def __init__(
        self,
        events: AuditEventRepository,
        objects: AuditObjectStore,
        *,
        export_prefix: str,
    ) -> None:
        self._events = events
        self._objects = objects
        self._prefix = export_prefix

    async def export(self, command: ExportAuditCommand) -> ExportResult:
        items = await self._events.list_all_ordered(command.tenant_id)
        export_id = new_uuid7()
        object_ref = (
            f"{self._prefix}/{command.region}/{command.tenant_id}/{export_id}.json"
        )
        package: dict[str, object] = {
            "export_id": str(export_id),
            "tenant_id": str(command.tenant_id),
            "region": command.region,
            "requested_by": command.requested_by,
            "generated_at": datetime.now(UTC).isoformat(),
            "event_count": len(items),
            "events": [
                {
                    "id": str(e.id),
                    "action": e.action,
                    "actor_type": e.actor_type.value,
                    "actor_id": e.actor_id,
                    "resource_type": e.resource_type,
                    "resource_id": e.resource_id,
                    "decision": e.decision.value,
                    "policy_version": e.policy_version,
                    "integrity_hash": e.integrity_hash,
                    "prev_hash": e.prev_hash,
                    "created_at": e.created_at.isoformat(),
                    "legal_hold": e.legal_hold,
                }
                for e in items
            ],
        }
        await self._objects.put(object_ref, package)
        return ExportResult(
            export_id=str(export_id),
            object_ref=object_ref,
            event_count=len(items),
        )


class LegalHoldService:
    def __init__(
        self,
        holds: LegalHoldRepository,
        ingestor: AuditIngestor,
    ) -> None:
        self._holds = holds
        self._ingestor = ingestor

    async def activate(self, command: LegalHoldCommand) -> LegalHold:
        hold = await self._holds.get(command.tenant_id)
        if hold is None:
            hold = LegalHold(
                tenant_id=command.tenant_id,
                active=False,
                reason="",
                updated_at=datetime.now(UTC),
            )
        hold.activate(command.reason)
        await self._holds.save(hold)
        await self._ingestor.ingest(
            IngestAuditCommand(
                tenant_id=command.tenant_id,
                actor_type=ActorType.USER,
                actor_id=command.actor_id,
                action="audit.legal_hold.activate",
                resource_type="legal_hold",
                resource_id=str(command.tenant_id),
                decision=AuditDecision.RECORDED,
                payload={"reason": command.reason},
            )
        )
        return hold

    async def release(self, tenant_id: UUID, *, actor_id: str) -> LegalHold:
        hold = await self._holds.get(tenant_id)
        if hold is None or not hold.active:
            raise ConflictError("Legal hold is not active")
        hold.release()
        await self._holds.save(hold)
        await self._ingestor.ingest(
            IngestAuditCommand(
                tenant_id=tenant_id,
                actor_type=ActorType.USER,
                actor_id=actor_id,
                action="audit.legal_hold.release",
                resource_type="legal_hold",
                resource_id=str(tenant_id),
                decision=AuditDecision.RECORDED,
            )
        )
        return hold
