from __future__ import annotations

from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError
from alama_common.ids import new_uuid7
from alama_common.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from fastapi import APIRouter, Depends, Header, Query, Request

from audit_service.adapters.http.schemas import (
    AuditEventListResponse,
    AuditEventResponse,
    ExportRequest,
    ExportResponse,
    HealthResponse,
    IngestAuditRequest,
    IntegrityResponse,
    LegalHoldRequest,
    LegalHoldResponse,
)
from audit_service.application.dto import (
    ExportAuditCommand,
    IngestAuditCommand,
    LegalHoldCommand,
    QueryAuditCommand,
)
from audit_service.container import AuditContainer
from audit_service.domain.models import AuditEvent, LegalHold

router = APIRouter()


def get_container(request: Request) -> AuditContainer:
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
        scopes=frozenset({"audit:read", "audit:write", "audit:admin"}),
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


def _event_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        tenant_id=event.tenant_id,
        actor_type=event.actor_type.value,
        actor_id=event.actor_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        decision=event.decision.value,
        policy_version=event.policy_version,
        object_ref=event.object_ref,
        created_at=event.created_at,
        integrity_hash=event.integrity_hash,
        prev_hash=event.prev_hash,
        legal_hold=event.legal_hold,
        payload=dict(event.payload),
    )


def _hold_response(hold: LegalHold) -> LegalHoldResponse:
    return LegalHoldResponse(
        tenant_id=hold.tenant_id,
        active=hold.active,
        reason=hold.reason,
        updated_at=hold.updated_at,
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="audit-service")


@router.post(
    "/v1/audit/events",
    response_model=AuditEventResponse,
    status_code=201,
    tags=["audit"],
)
async def ingest_event(
    body: IngestAuditRequest,
    principal: Principal = Depends(get_principal),
    container: AuditContainer = Depends(get_container),
) -> AuditEventResponse:
    event = await container.ingestor.ingest(
        IngestAuditCommand(
            tenant_id=principal.primary_tenant_id(),
            actor_type=body.actor_type,
            actor_id=body.actor_id,
            action=body.action,
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            decision=body.decision,
            policy_version=body.policy_version,
            payload=body.payload,
        )
    )
    return _event_response(event)


@router.get(
    "/v1/audit/events",
    response_model=AuditEventListResponse,
    tags=["audit"],
)
async def list_events(
    principal: Principal = Depends(get_principal),
    container: AuditContainer = Depends(get_container),
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
) -> AuditEventListResponse:
    items, next_cursor = await container.query.list_events(
        QueryAuditCommand(
            tenant_id=principal.primary_tenant_id(),
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            limit=limit,
            cursor=cursor,
        )
    )
    return AuditEventListResponse(
        items=[_event_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/v1/audit/integrity",
    response_model=IntegrityResponse,
    tags=["audit"],
)
async def verify_integrity(
    principal: Principal = Depends(get_principal),
    container: AuditContainer = Depends(get_container),
) -> IntegrityResponse:
    tenant_id = principal.primary_tenant_id()
    valid = await container.query.verify_integrity(tenant_id)
    return IntegrityResponse(tenant_id=tenant_id, valid=valid)


@router.post(
    "/v1/audit/exports",
    response_model=ExportResponse,
    status_code=201,
    tags=["audit"],
)
async def export_events(
    body: ExportRequest,
    principal: Principal = Depends(get_principal),
    container: AuditContainer = Depends(get_container),
) -> ExportResponse:
    result = await container.exporter.export(
        ExportAuditCommand(
            tenant_id=principal.primary_tenant_id(),
            region=body.region,
            requested_by=str(principal.subject_id),
        )
    )
    return ExportResponse(
        export_id=result.export_id,
        object_ref=result.object_ref,
        event_count=result.event_count,
    )


@router.post(
    "/v1/audit/legal-hold",
    response_model=LegalHoldResponse,
    tags=["audit"],
)
async def activate_legal_hold(
    body: LegalHoldRequest,
    principal: Principal = Depends(get_principal),
    container: AuditContainer = Depends(get_container),
) -> LegalHoldResponse:
    hold = await container.legal_hold.activate(
        LegalHoldCommand(
            tenant_id=principal.primary_tenant_id(),
            reason=body.reason,
            actor_id=str(principal.subject_id),
        )
    )
    return _hold_response(hold)


@router.delete(
    "/v1/audit/legal-hold",
    response_model=LegalHoldResponse,
    tags=["audit"],
)
async def release_legal_hold(
    principal: Principal = Depends(get_principal),
    container: AuditContainer = Depends(get_container),
) -> LegalHoldResponse:
    hold = await container.legal_hold.release(
        principal.primary_tenant_id(),
        actor_id=str(principal.subject_id),
    )
    return _hold_response(hold)
