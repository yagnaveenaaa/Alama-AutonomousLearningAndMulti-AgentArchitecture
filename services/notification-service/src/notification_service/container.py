from __future__ import annotations

from dataclasses import dataclass

from alama_common.retry import RetryPolicy

from notification_service.adapters.memory import (
    InMemoryDeliveryAttemptRepository,
    InMemoryNotificationRepository,
    InMemoryNotificationStore,
    InMemoryNotifier,
    InMemoryPreferenceRepository,
)
from notification_service.application.dispatcher import NotificationDispatcher
from notification_service.application.preferences import PreferenceService
from notification_service.config import NotificationSettings


@dataclass
class NotificationContainer:
    store: InMemoryNotificationStore
    notifier: InMemoryNotifier
    dispatcher: NotificationDispatcher
    preferences: PreferenceService


def build_container(
    settings: NotificationSettings | None = None,
) -> NotificationContainer:
    settings = settings or NotificationSettings()
    store = InMemoryNotificationStore()
    notifications = InMemoryNotificationRepository(store)
    attempts = InMemoryDeliveryAttemptRepository(store)
    prefs = InMemoryPreferenceRepository(store)
    notifier = InMemoryNotifier(store)
    retry_policy = RetryPolicy(
        name="notification",
        max_attempts=settings.retry_max_attempts,
        initial_backoff_ms=settings.retry_initial_backoff_ms,
        max_backoff_ms=settings.retry_max_backoff_ms,
        jitter=settings.retry_jitter,
    )
    dispatcher = NotificationDispatcher(
        notifications,
        attempts,
        prefs,
        notifier,
        retry_policy=retry_policy,
    )
    return NotificationContainer(
        store=store,
        notifier=notifier,
        dispatcher=dispatcher,
        preferences=PreferenceService(prefs),
    )
