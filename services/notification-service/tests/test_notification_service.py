from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from notification_service.application.dto import (
    DispatchNotificationCommand,
    UpsertPreferenceCommand,
)
from notification_service.config import NotificationSettings
from notification_service.container import build_container
from notification_service.domain.models import NotificationChannel, NotificationStatus
from notification_service.main import create_app


@pytest.fixture
def container():
    return build_container(
        NotificationSettings(
            use_in_memory_store=True,
            retry_max_attempts=3,
            retry_initial_backoff_ms=0,
            retry_max_backoff_ms=0,
            retry_jitter=False,
        )
    )


@pytest.fixture
async def client():
    app = create_app(
        NotificationSettings(
            use_in_memory_store=True,
            retry_max_attempts=3,
            retry_initial_backoff_ms=0,
            retry_max_backoff_ms=0,
            retry_jitter=False,
        )
    )
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as http,
        app.router.lifespan_context(app),
    ):
        yield http


def _headers(tenant_id=None, subject_id=None) -> dict[str, str]:
    return {
        "X-Tenant-Id": str(tenant_id or uuid4()),
        "X-Subject-Id": str(subject_id or uuid4()),
    }


@pytest.mark.asyncio
async def test_idempotent_dispatch_and_delivery(container) -> None:
    tenant_id = uuid4()
    recipient_id = uuid4()
    cmd = DispatchNotificationCommand(
        tenant_id=tenant_id,
        recipient_id=recipient_id,
        channel=NotificationChannel.IN_APP,
        template_key="task.approval_required",
        subject="Approval needed",
        body="Task requires approval",
        idempotency_key="n-1",
    )
    first, created1 = await container.dispatcher.dispatch(cmd)
    second, created2 = await container.dispatcher.dispatch(cmd)
    assert created1 is True
    assert created2 is False
    assert first.id == second.id
    assert first.status == NotificationStatus.DELIVERED
    assert len(container.store.sent) == 1


@pytest.mark.asyncio
async def test_preference_skip_and_retry(container) -> None:
    tenant_id = uuid4()
    recipient_id = uuid4()
    await container.preferences.upsert(
        UpsertPreferenceCommand(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            channel=NotificationChannel.EMAIL,
            enabled=False,
        )
    )
    skipped, _ = await container.dispatcher.dispatch(
        DispatchNotificationCommand(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            channel=NotificationChannel.EMAIL,
            template_key="digest.daily",
            subject="Daily digest",
            body="...",
            idempotency_key="skip-1",
        )
    )
    assert skipped.status == NotificationStatus.SKIPPED

    container.notifier.fail_times = 2
    delivered, _ = await container.dispatcher.dispatch(
        DispatchNotificationCommand(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            channel=NotificationChannel.SLACK,
            template_key="task.completed",
            subject="Done",
            body="Task finished",
            idempotency_key="retry-1",
            enforce_preferences=False,
        )
    )
    assert delivered.status == NotificationStatus.DELIVERED
    assert delivered.attempt_count == 3
    attempts = await container.dispatcher.get(tenant_id, delivered.id)
    assert len(attempts[1]) == 3


@pytest.mark.asyncio
async def test_http_dispatch_list_and_read(client) -> None:
    subject_id = uuid4()
    tenant_id = uuid4()
    headers = _headers(tenant_id=tenant_id, subject_id=subject_id)

    health = await client.get("/health")
    assert health.status_code == 200

    created = await client.post(
        "/v1/notifications",
        headers=headers,
        json={
            "recipient_id": str(subject_id),
            "channel": "in_app",
            "template_key": "approval.gate",
            "subject": "Approve change",
            "body": "Please approve",
            "idempotency_key": "http-1",
        },
    )
    assert created.status_code == 202
    notification_id = created.json()["id"]
    assert created.json()["status"] == "delivered"

    replay = await client.post(
        "/v1/notifications",
        headers=headers,
        json={
            "recipient_id": str(subject_id),
            "channel": "in_app",
            "template_key": "approval.gate",
            "subject": "Approve change",
            "body": "Please approve",
            "idempotency_key": "http-1",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["created"] is False

    inbox = await client.get("/v1/notifications", headers=headers)
    assert inbox.status_code == 200
    assert len(inbox.json()["items"]) == 1

    marked = await client.post(
        f"/v1/notifications/{notification_id}/read", headers=headers
    )
    assert marked.status_code == 200
    assert marked.json()["status"] == "read"

    prefs = await client.put(
        "/v1/notifications/preferences",
        headers=headers,
        json={"channel": "email", "enabled": False},
    )
    assert prefs.status_code == 200
    assert prefs.json()["enabled"] is False
