from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from alama_common.errors import ConflictError, NotFoundError
from alama_common.retry import RetryPolicy, retry_with_policy_async

from notification_service.application.dto import DispatchNotificationCommand
from notification_service.domain.models import (
    AttemptStatus,
    DeliveryAttempt,
    Notification,
    NotificationStatus,
)
from notification_service.domain.repositories import (
    DeliveryAttemptRepository,
    NotificationRepository,
    Notifier,
    PreferenceRepository,
)


class NotificationDispatcher:
    """Route by preference and deliver with retries (LLD §2.13 / §3.3)."""

    def __init__(
        self,
        notifications: NotificationRepository,
        attempts: DeliveryAttemptRepository,
        preferences: PreferenceRepository,
        notifier: Notifier,
        *,
        retry_policy: RetryPolicy,
    ) -> None:
        self._notifications = notifications
        self._attempts = attempts
        self._preferences = preferences
        self._notifier = notifier
        self._retry_policy = retry_policy

    async def dispatch(
        self, command: DispatchNotificationCommand
    ) -> tuple[Notification, bool]:
        existing = await self._notifications.get_by_idempotency_key(
            command.tenant_id, command.idempotency_key
        )
        if existing is not None:
            return existing, False

        notification = Notification.create(
            tenant_id=command.tenant_id,
            recipient_id=command.recipient_id,
            channel=command.channel,
            template_key=command.template_key,
            subject=command.subject,
            body=command.body,
            idempotency_key=command.idempotency_key,
            payload=command.payload,
        )
        await self._notifications.save(notification)

        if command.enforce_preferences:
            pref = await self._preferences.get(
                command.tenant_id, command.recipient_id, command.channel
            )
            if pref is not None and not pref.enabled:
                skipped = self._with_status(
                    notification,
                    NotificationStatus.SKIPPED,
                    attempt_count=1,
                )
                await self._notifications.save(skipped)
                await self._attempts.append(
                    DeliveryAttempt.create(
                        notification_id=skipped.id,
                        attempt_number=1,
                        status=AttemptStatus.SKIPPED,
                        error="channel disabled by preference",
                    )
                )
                return skipped, True

        return await self._deliver(notification), True

    async def _deliver(self, notification: Notification) -> Notification:
        attempt_number = 0

        async def _send() -> None:
            nonlocal attempt_number
            attempt_number += 1
            try:
                await self._notifier.send(notification)
            except Exception as exc:
                await self._attempts.append(
                    DeliveryAttempt.create(
                        notification_id=notification.id,
                        attempt_number=attempt_number,
                        status=AttemptStatus.FAILED,
                        error=str(exc),
                    )
                )
                raise
            await self._attempts.append(
                DeliveryAttempt.create(
                    notification_id=notification.id,
                    attempt_number=attempt_number,
                    status=AttemptStatus.SUCCESS,
                )
            )

        try:
            await retry_with_policy_async(self._retry_policy, _send)
        except Exception:
            failed = self._with_status(
                notification,
                NotificationStatus.FAILED,
                attempt_count=attempt_number,
            )
            await self._notifications.save(failed)
            return failed

        delivered = self._with_status(
            notification,
            NotificationStatus.DELIVERED,
            attempt_count=attempt_number,
            delivered_at=datetime.now(UTC),
        )
        await self._notifications.save(delivered)
        return delivered

    async def mark_read(self, tenant_id: UUID, notification_id: UUID) -> Notification:
        current = await self._notifications.get(tenant_id, notification_id)
        if current is None:
            raise NotFoundError(
                "Notification not found",
                details={"notification_id": str(notification_id)},
            )
        if current.status == NotificationStatus.READ:
            return current
        if current.status not in {
            NotificationStatus.DELIVERED,
            NotificationStatus.PENDING,
        }:
            raise ConflictError(
                "Notification cannot be marked read",
                details={"status": current.status.value},
            )
        updated = self._with_status(
            current,
            NotificationStatus.READ,
            attempt_count=current.attempt_count,
            delivered_at=current.delivered_at,
            read_at=datetime.now(UTC),
        )
        await self._notifications.save(updated)
        return updated

    async def get(
        self, tenant_id: UUID, notification_id: UUID
    ) -> tuple[Notification, list[DeliveryAttempt]]:
        current = await self._notifications.get(tenant_id, notification_id)
        if current is None:
            raise NotFoundError(
                "Notification not found",
                details={"notification_id": str(notification_id)},
            )
        attempts = await self._attempts.list_for_notification(notification_id)
        return current, attempts

    async def list_for_recipient(
        self,
        tenant_id: UUID,
        recipient_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        unread_only: bool,
    ) -> tuple[list[Notification], str | None]:
        return await self._notifications.list_for_recipient(
            tenant_id,
            recipient_id,
            limit=limit,
            cursor=cursor,
            unread_only=unread_only,
        )

    @staticmethod
    def _with_status(
        notification: Notification,
        status: NotificationStatus,
        *,
        attempt_count: int,
        delivered_at: datetime | None = None,
        read_at: datetime | None = None,
    ) -> Notification:
        return Notification(
            id=notification.id,
            tenant_id=notification.tenant_id,
            recipient_id=notification.recipient_id,
            channel=notification.channel,
            template_key=notification.template_key,
            subject=notification.subject,
            body=notification.body,
            payload=dict(notification.payload),
            status=status,
            idempotency_key=notification.idempotency_key,
            created_at=notification.created_at,
            delivered_at=delivered_at if delivered_at is not None else notification.delivered_at,
            read_at=read_at if read_at is not None else notification.read_at,
            attempt_count=attempt_count,
        )
