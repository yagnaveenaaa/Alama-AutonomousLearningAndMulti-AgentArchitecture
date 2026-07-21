from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from notification_service.domain.models import NotificationChannel


@dataclass(frozen=True, slots=True)
class DispatchNotificationCommand:
    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    template_key: str
    subject: str
    body: str
    idempotency_key: str
    payload: dict[str, Any] | None = None
    enforce_preferences: bool = True


@dataclass(frozen=True, slots=True)
class UpsertPreferenceCommand:
    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    enabled: bool
    destination: str | None = None
