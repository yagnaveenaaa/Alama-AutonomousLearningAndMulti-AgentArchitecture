from __future__ import annotations

from uuid import UUID

from alama_common.errors import DependencyTransientError
from alama_common.pagination import decode_cursor, encode_cursor

from notification_service.domain.models import (
    ChannelPreference,
    DeliveryAttempt,
    Notification,
    NotificationChannel,
    NotificationStatus,
)


class InMemoryNotificationStore:
    def __init__(self) -> None:
        self.notifications: dict[UUID, Notification] = {}
        self.attempts: list[DeliveryAttempt] = []
        self.preferences: dict[tuple[UUID, UUID, str], ChannelPreference] = {}
        self.sent: list[Notification] = []


class InMemoryNotificationRepository:
    def __init__(self, store: InMemoryNotificationStore) -> None:
        self._store = store

    async def get_by_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> Notification | None:
        for item in self._store.notifications.values():
            if item.tenant_id == tenant_id and item.idempotency_key == idempotency_key:
                return item
        return None

    async def get(self, tenant_id: UUID, notification_id: UUID) -> Notification | None:
        item = self._store.notifications.get(notification_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    async def save(self, notification: Notification) -> None:
        self._store.notifications[notification.id] = notification

    async def list_for_recipient(
        self,
        tenant_id: UUID,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        unread_only: bool,
    ) -> tuple[list[Notification], str | None]:
        items = [
            n
            for n in self._store.notifications.values()
            if n.tenant_id == tenant_id and n.recipient_id == recipient_id
        ]
        items.sort(key=lambda n: n.created_at, reverse=True)
        if unread_only:
            items = [
                n
                for n in items
                if n.status
                in {NotificationStatus.DELIVERED, NotificationStatus.PENDING}
            ]
        offset = 0
        if cursor:
            offset = int(decode_cursor(cursor).get("offset", 0))
        page = items[offset : offset + limit]
        next_cursor = (
            encode_cursor({"offset": offset + limit})
            if offset + limit < len(items)
            else None
        )
        return page, next_cursor


class InMemoryDeliveryAttemptRepository:
    def __init__(self, store: InMemoryNotificationStore) -> None:
        self._store = store

    async def append(self, attempt: DeliveryAttempt) -> None:
        self._store.attempts.append(attempt)

    async def list_for_notification(
        self, notification_id: UUID
    ) -> list[DeliveryAttempt]:
        items = [a for a in self._store.attempts if a.notification_id == notification_id]
        items.sort(key=lambda a: a.attempt_number)
        return items


class InMemoryPreferenceRepository:
    def __init__(self, store: InMemoryNotificationStore) -> None:
        self._store = store

    async def get(
        self,
        tenant_id: UUID,
        recipient_id: UUID,
        channel: NotificationChannel,
    ) -> ChannelPreference | None:
        return self._store.preferences.get((tenant_id, recipient_id, channel.value))

    async def list_for_recipient(
        self, tenant_id: UUID, recipient_id: UUID
    ) -> list[ChannelPreference]:
        return [
            p
            for (tid, rid, _), p in self._store.preferences.items()
            if tid == tenant_id and rid == recipient_id
        ]

    async def save(self, preference: ChannelPreference) -> None:
        key = (
            preference.tenant_id,
            preference.recipient_id,
            preference.channel.value,
        )
        self._store.preferences[key] = preference


class InMemoryNotifier:
    """Records sends; optional failure injection for tests."""

    def __init__(self, store: InMemoryNotificationStore) -> None:
        self._store = store
        self.fail_times: int = 0

    async def send(self, notification: Notification) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise DependencyTransientError("simulated channel failure")
        self._store.sent.append(notification)
