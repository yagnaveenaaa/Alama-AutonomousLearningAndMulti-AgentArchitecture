from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from audit_service.domain.models import ActorType, AuditDecision


@dataclass(frozen=True, slots=True)
class IngestAuditCommand:
    tenant_id: UUID
    actor_type: ActorType
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    decision: AuditDecision = AuditDecision.RECORDED
    policy_version: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QueryAuditCommand:
    tenant_id: UUID
    action: str | None = None
    actor_id: str | None = None
    resource_type: str | None = None
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class ExportAuditCommand:
    tenant_id: UUID
    region: str
    requested_by: str


@dataclass(frozen=True, slots=True)
class LegalHoldCommand:
    tenant_id: UUID
    reason: str
    actor_id: str
