from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ValidationError
from alama_common.ids import new_uuid7


class NotificationChannel(StrEnum):
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"
    SKIPPED = "skipped"


class AttemptStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class Notification:
    """notification.notifications row (LLD §4.8)."""

    id: UUID
    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    template_key: str
    subject: str
    body: str
    payload: dict[str, Any]
    status: NotificationStatus
    idempotency_key: str
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None
    attempt_count: int

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        recipient_id: UUID,
        channel: NotificationChannel,
        template_key: str,
        subject: str,
        body: str,
        idempotency_key: str,
        payload: dict[str, Any] | None = None,
    ) -> Notification:
        if not idempotency_key.strip():
            raise ValidationError("idempotency_key is required")
        if not template_key.strip():
            raise ValidationError("template_key is required")
        if not subject.strip():
            raise ValidationError("subject is required")
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            channel=channel,
            template_key=template_key.strip(),
            subject=subject.strip(),
            body=body,
            payload=dict(payload or {}),
            status=NotificationStatus.PENDING,
            idempotency_key=idempotency_key.strip(),
            created_at=datetime.now(UTC),
            delivered_at=None,
            read_at=None,
            attempt_count=0,
        )


@dataclass(frozen=True, slots=True)
class DeliveryAttempt:
    """Per-delivery attempt (LLD §2.13 / §3.3)."""

    id: UUID
    notification_id: UUID
    attempt_number: int
    status: AttemptStatus
    error: str | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        notification_id: UUID,
        attempt_number: int,
        status: AttemptStatus,
        error: str | None = None,
    ) -> DeliveryAttempt:
        return cls(
            id=new_uuid7(),
            notification_id=notification_id,
            attempt_number=attempt_number,
            status=status,
            error=error,
            created_at=datetime.now(UTC),
        )


@dataclass
class ChannelPreference:
    """Per-recipient channel enablement."""

    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    enabled: bool
    destination: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
