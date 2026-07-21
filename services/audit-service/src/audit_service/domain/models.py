from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ConflictError, ValidationError
from alama_common.ids import new_uuid7


class ActorType(StrEnum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    SERVICE = "service"


class AuditDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"
    RECORDED = "recorded"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Append-only normalized audit event (LLD §4.8 audit_index)."""

    id: UUID
    tenant_id: UUID
    actor_type: ActorType
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    decision: AuditDecision
    policy_version: str | None
    object_ref: str | None
    created_at: datetime
    payload: dict[str, Any]
    integrity_hash: str
    prev_hash: str
    legal_hold: bool = False

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        actor_type: ActorType,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        decision: AuditDecision,
        integrity_hash: str,
        prev_hash: str,
        policy_version: str | None = None,
        object_ref: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        if not action.strip():
            raise ValidationError("action is required")
        if not resource_type.strip():
            raise ValidationError("resource_type is required")
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action.strip(),
            resource_type=resource_type.strip(),
            resource_id=resource_id,
            decision=decision,
            policy_version=policy_version,
            object_ref=object_ref,
            created_at=datetime.now(UTC),
            payload=dict(payload or {}),
            integrity_hash=integrity_hash,
            prev_hash=prev_hash,
            legal_hold=False,
        )


@dataclass
class LegalHold:
    tenant_id: UUID
    active: bool
    reason: str
    updated_at: datetime

    def activate(self, reason: str) -> None:
        if self.active:
            raise ConflictError("Legal hold already active")
        self.active = True
        self.reason = reason
        self.updated_at = datetime.now(UTC)

    def release(self) -> None:
        if not self.active:
            raise ConflictError("Legal hold is not active")
        self.active = False
        self.updated_at = datetime.now(UTC)
