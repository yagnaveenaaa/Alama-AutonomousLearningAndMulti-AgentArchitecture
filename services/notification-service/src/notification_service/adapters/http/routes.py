from __future__ import annotations

from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError
from alama_common.ids import new_uuid7
from alama_common.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from fastapi import APIRouter, Depends, Header, Query, Request, Response

from notification_service.adapters.http.schemas import (
    DeliveryAttemptResponse,
    DispatchNotificationRequest,
    HealthResponse,
    NotificationListResponse,
    NotificationResponse,
    PreferenceListResponse,
    PreferenceResponse,
    UpsertPreferenceRequest,
)
from notification_service.application.dto import (
    DispatchNotificationCommand,
    UpsertPreferenceCommand,
)
from notification_service.container import NotificationContainer
from notification_service.domain.models import DeliveryAttempt, Notification

router = APIRouter()


def get_container(request: Request) -> NotificationContainer:
    return request.app.state.container  # type: ignore[no-any-return]


async def get_principal(
    request: Request,
    x_subject_id: str | None = Header(default=None, alias="X-Subject-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> Principal:
    if x_subject_id is None or x_tenant_id is None:
        raise AuthenticationError("Missing identity headers")
    try:
        subject_id = UUID(x_subject_id)
        tenant_id = UUID(x_tenant_id)
    except ValueError as exc:
        raise AuthenticationError("Invalid identity headers") from exc
    principal = Principal(
        subject_id=subject_id,
        tenant_ids=(tenant_id,),
        scopes=frozenset({"notification:read", "notification:write"}),
    )
    bind_request_context(
        RequestContext(
            request_id=new_uuid7(),
            tenant_id=tenant_id,
            principal=principal,
            trace_id=request.headers.get("traceparent"),
        )
    )
    return principal


def _attempt_response(attempt: DeliveryAttempt) -> DeliveryAttemptResponse:
    return DeliveryAttemptResponse(
        id=attempt.id,
        attempt_number=attempt.attempt_number,
        status=attempt.status.value,
        error=attempt.error,
        created_at=attempt.created_at,
    )


def _notification_response(
    notification: Notification,
    *,
    created: bool = True,
    attempts: list[DeliveryAttempt] | None = None,
) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        tenant_id=notification.tenant_id,
        recipient_id=notification.recipient_id,
        channel=notification.channel.value,
        template_key=notification.template_key,
        subject=notification.subject,
        body=notification.body,
        payload=dict(notification.payload),
        status=notification.status.value,
        idempotency_key=notification.idempotency_key,
        created_at=notification.created_at,
        delivered_at=notification.delivered_at,
        read_at=notification.read_at,
        attempt_count=notification.attempt_count,
        created=created,
        attempts=[_attempt_response(a) for a in (attempts or [])],
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="notification-service")


@router.post(
    "/v1/notifications",
    response_model=NotificationResponse,
    tags=["notifications"],
)
async def dispatch_notification(
    body: DispatchNotificationRequest,
    response: Response,
    principal: Principal = Depends(get_principal),
    container: NotificationContainer = Depends(get_container),
) -> NotificationResponse:
    notification, created = await container.dispatcher.dispatch(
        DispatchNotificationCommand(
            tenant_id=principal.primary_tenant_id(),
            recipient_id=body.recipient_id,
            channel=body.channel,
            template_key=body.template_key,
            subject=body.subject,
            body=body.body,
            idempotency_key=body.idempotency_key,
            payload=body.payload,
            enforce_preferences=body.enforce_preferences,
        )
    )
    response.status_code = 202 if created else 200
    attempts = await container.dispatcher.get(
        principal.primary_tenant_id(), notification.id
    )
    return _notification_response(
        notification, created=created, attempts=attempts[1]
    )


@router.get(
    "/v1/notifications",
    response_model=NotificationListResponse,
    tags=["notifications"],
)
async def list_notifications(
    principal: Principal = Depends(get_principal),
    container: NotificationContainer = Depends(get_container),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
) -> NotificationListResponse:
    items, next_cursor = await container.dispatcher.list_for_recipient(
        principal.primary_tenant_id(),
        principal.subject_id,
        limit=limit,
        cursor=cursor,
        unread_only=unread_only,
    )
    return NotificationListResponse(
        items=[_notification_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/v1/notifications/preferences",
    response_model=PreferenceListResponse,
    tags=["preferences"],
)
async def list_preferences(
    principal: Principal = Depends(get_principal),
    container: NotificationContainer = Depends(get_container),
) -> PreferenceListResponse:
    items = await container.preferences.list(
        principal.primary_tenant_id(), principal.subject_id
    )
    return PreferenceListResponse(
        items=[
            PreferenceResponse(
                channel=p.channel.value,
                enabled=p.enabled,
                destination=p.destination,
                updated_at=p.updated_at,
            )
            for p in items
        ]
    )


@router.put(
    "/v1/notifications/preferences",
    response_model=PreferenceResponse,
    tags=["preferences"],
)
async def upsert_preference(
    body: UpsertPreferenceRequest,
    principal: Principal = Depends(get_principal),
    container: NotificationContainer = Depends(get_container),
) -> PreferenceResponse:
    preference = await container.preferences.upsert(
        UpsertPreferenceCommand(
            tenant_id=principal.primary_tenant_id(),
            recipient_id=principal.subject_id,
            channel=body.channel,
            enabled=body.enabled,
            destination=body.destination,
        )
    )
    return PreferenceResponse(
        channel=preference.channel.value,
        enabled=preference.enabled,
        destination=preference.destination,
        updated_at=preference.updated_at,
    )


@router.get(
    "/v1/notifications/{notification_id}",
    response_model=NotificationResponse,
    tags=["notifications"],
)
async def get_notification(
    notification_id: UUID,
    principal: Principal = Depends(get_principal),
    container: NotificationContainer = Depends(get_container),
) -> NotificationResponse:
    notification, attempts = await container.dispatcher.get(
        principal.primary_tenant_id(), notification_id
    )
    return _notification_response(notification, attempts=attempts)


@router.post(
    "/v1/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    tags=["notifications"],
)
async def mark_read(
    notification_id: UUID,
    principal: Principal = Depends(get_principal),
    container: NotificationContainer = Depends(get_container),
) -> NotificationResponse:
    notification = await container.dispatcher.mark_read(
        principal.primary_tenant_id(), notification_id
    )
    return _notification_response(notification)
