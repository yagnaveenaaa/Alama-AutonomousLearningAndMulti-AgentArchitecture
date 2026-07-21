from __future__ import annotations

from typing import Protocol
from uuid import UUID

from notification_service.domain.models import (
    ChannelPreference,
    DeliveryAttempt,
    Notification,
    NotificationChannel,
)


class NotificationRepository(Protocol):
    async def get_by_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> Notification | None: ...

    async def get(self, tenant_id: UUID, notification_id: UUID) -> Notification | None: ...

    async def save(self, notification: Notification) -> None: ...

    async def list_for_recipient(
        self,
        tenant_id: UUID,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        unread_only: bool,
    ) -> tuple[list[Notification], str | None]: ...


class DeliveryAttemptRepository(Protocol):
    async def append(self, attempt: DeliveryAttempt) -> None: ...

    async def list_for_notification(
        self, notification_id: UUID
    ) -> list[DeliveryAttempt]: ...


class PreferenceRepository(Protocol):
    async def get(
        self,
        tenant_id: UUID,
        recipient_id: UUID,
        channel: NotificationChannel,
    ) -> ChannelPreference | None: ...

    async def list_for_recipient(
        self, tenant_id: UUID, recipient_id: UUID
    ) -> list[ChannelPreference]: ...

    async def save(self, preference: ChannelPreference) -> None: ...


class Notifier(Protocol):
    """Channel send adapter (LLD §2.13)."""

    async def send(self, notification: Notification) -> None: ...
