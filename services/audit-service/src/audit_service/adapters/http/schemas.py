from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from audit_service.domain.models import ActorType, AuditDecision


class HealthResponse(BaseModel):
    status: str
    service: str


class IngestAuditRequest(BaseModel):
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str = Field(min_length=1, max_length=256)
    action: str = Field(min_length=1, max_length=256)
    resource_type: str = Field(min_length=1, max_length=128)
    resource_id: str = Field(min_length=1, max_length=256)
    decision: AuditDecision = AuditDecision.RECORDED
    policy_version: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditEventResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    decision: str
    policy_version: str | None
    object_ref: str | None
    created_at: datetime
    integrity_hash: str
    prev_hash: str
    legal_hold: bool
    payload: dict[str, Any]


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: str | None = None


class IntegrityResponse(BaseModel):
    tenant_id: UUID
    valid: bool


class ExportRequest(BaseModel):
    region: str = Field(default="local", min_length=1, max_length=64)


class ExportResponse(BaseModel):
    export_id: str
    object_ref: str
    event_count: int


class LegalHoldRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class LegalHoldResponse(BaseModel):
    tenant_id: UUID
    active: bool
    reason: str
    updated_at: datetime
