from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from notification_service.domain.models import NotificationChannel


class HealthResponse(BaseModel):
    status: str
    service: str


class DispatchNotificationRequest(BaseModel):
    recipient_id: UUID
    channel: NotificationChannel
    template_key: str = Field(min_length=1, max_length=128)
    subject: str = Field(min_length=1, max_length=512)
    body: str = Field(default="", max_length=32_000)
    idempotency_key: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)
    enforce_preferences: bool = True


class DeliveryAttemptResponse(BaseModel):
    id: UUID
    attempt_number: int
    status: str
    error: str | None
    created_at: datetime


class NotificationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    recipient_id: UUID
    channel: str
    template_key: str
    subject: str
    body: str
    payload: dict[str, Any]
    status: str
    idempotency_key: str
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None
    attempt_count: int
    created: bool = True
    attempts: list[DeliveryAttemptResponse] = Field(default_factory=list)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    next_cursor: str | None = None


class PreferenceResponse(BaseModel):
    channel: str
    enabled: bool
    destination: str | None
    updated_at: datetime


class PreferenceListResponse(BaseModel):
    items: list[PreferenceResponse]


class UpsertPreferenceRequest(BaseModel):
    channel: NotificationChannel
    enabled: bool = True
    destination: str | None = Field(default=None, max_length=512)
