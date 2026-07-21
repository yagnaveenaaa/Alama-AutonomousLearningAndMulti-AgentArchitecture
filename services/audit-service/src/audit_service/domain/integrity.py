from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from audit_service.domain.models import ActorType, AuditDecision, AuditEvent


class IntegrityHasher:
    """Hash chain / Merkle-batch style integrity (LLD §2.11)."""

    GENESIS = "0" * 64

    def hash_event(
        self,
        *,
        tenant_id: UUID,
        actor_type: ActorType,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        decision: AuditDecision,
        policy_version: str | None,
        object_ref: str | None,
        payload: dict[str, Any],
        prev_hash: str,
        event_id: UUID,
        created_at_iso: str,
    ) -> str:
        canonical = {
            "id": str(event_id),
            "tenant_id": str(tenant_id),
            "actor_type": actor_type.value,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "decision": decision.value,
            "policy_version": policy_version,
            "object_ref": object_ref,
            "payload": payload,
            "prev_hash": prev_hash,
            "created_at": created_at_iso,
        }
        raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def verify_chain(self, events: list[AuditEvent]) -> bool:
        """Verify chronological chain for a tenant (oldest → newest)."""
        expected_prev = self.GENESIS
        for event in events:
            if event.prev_hash != expected_prev:
                return False
            recomputed = self.hash_event(
                tenant_id=event.tenant_id,
                actor_type=event.actor_type,
                actor_id=event.actor_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                decision=event.decision,
                policy_version=event.policy_version,
                object_ref=event.object_ref,
                payload=event.payload,
                prev_hash=event.prev_hash,
                event_id=event.id,
                created_at_iso=event.created_at.isoformat(),
            )
            if recomputed != event.integrity_hash:
                return False
            expected_prev = event.integrity_hash
        return True
