from __future__ import annotations

from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError, AuthorizationError
from alama_common.ids import new_uuid7
from alama_common.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from fastapi import APIRouter, Depends, Header, Query, Request

from identity_service.adapters.http.schemas import (
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    CreateTenantRequest,
    HealthResponse,
    SubjectListResponse,
    SubjectResponse,
    TenantResponse,
)
from identity_service.application.dto import CreateApiKeyCommand, CreateTenantCommand
from identity_service.container import IdentityContainer
from identity_service.domain.models import Tenant

router = APIRouter()


def get_container(request: Request) -> IdentityContainer:
    return request.app.state.container  # type: ignore[no-any-return]


async def get_principal(
    request: Request,
    x_subject_id: str | None = Header(default=None, alias="X-Subject-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> Principal:
    """Gateway-forwarded identity headers (api-gateway will validate JWT later)."""

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
        scopes=frozenset({"identity:read", "identity:write"}),
        session_id=None,
    )
    token = bind_request_context(
        RequestContext(
            request_id=new_uuid7(),
            tenant_id=tenant_id,
            principal=principal,
            trace_id=request.headers.get("traceparent"),
        )
    )
    request.state.context_token = token
    return principal


def _tenant_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        home_region=tenant.home_region,
        home_cell=tenant.home_cell,
        isolation_tier=tenant.isolation_tier,
        plan=tenant.plan,
        status=tenant.status.value,
        data_residency=tenant.data_residency,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        version=tenant.version,
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="identity-service")


@router.post(
    "/v1/tenants",
    response_model=TenantResponse,
    status_code=201,
    tags=["tenants"],
)
async def create_tenant(
    body: CreateTenantRequest,
    container: IdentityContainer = Depends(get_container),
) -> TenantResponse:
    tenant = await container.create_tenant.handle(
        CreateTenantCommand(
            slug=body.slug,
            name=body.name,
            home_region=body.home_region,
            home_cell=body.home_cell,
            isolation_tier=body.isolation_tier,
            plan=body.plan,
            data_residency=body.data_residency,
            owner_external_idp_sub=body.owner_external_idp_sub,
            owner_email=body.owner_email,
            owner_display_name=body.owner_display_name,
        )
    )
    return _tenant_response(tenant)


@router.get("/v1/tenants/me", response_model=TenantResponse, tags=["tenants"])
async def get_tenant_me(
    principal: Principal = Depends(get_principal),
    container: IdentityContainer = Depends(get_container),
) -> TenantResponse:
    tenant_id = principal.primary_tenant_id()
    tenant = await container.tenants.get_by_id(tenant_id)
    if tenant is None:
        from alama_common.errors import NotFoundError

        raise NotFoundError("Tenant not found")
    return _tenant_response(tenant)


@router.get("/v1/subjects/me", response_model=SubjectResponse, tags=["subjects"])
async def get_subject_me(
    principal: Principal = Depends(get_principal),
    container: IdentityContainer = Depends(get_container),
) -> SubjectResponse:
    subject = await container.subjects.get_by_id(principal.subject_id)
    if subject is None:
        from alama_common.errors import NotFoundError

        raise NotFoundError("Subject not found")
    roles = await container.role_bindings.list_roles_for_subject(subject.tenant_id, subject.id)
    return SubjectResponse(
        id=subject.id,
        tenant_id=subject.tenant_id,
        external_idp_sub=subject.external_idp_sub,
        email=subject.email,
        display_name=subject.display_name,
        status=subject.status.value,
        roles=roles,
        created_at=subject.created_at,
        updated_at=subject.updated_at,
    )


@router.get(
    "/v1/tenants/{tenant_id}/subjects",
    response_model=SubjectListResponse,
    tags=["subjects"],
)
async def list_subjects(
    tenant_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    principal: Principal = Depends(get_principal),
    container: IdentityContainer = Depends(get_container),
) -> SubjectListResponse:
    if not principal.can_access_tenant(tenant_id):
        raise AuthorizationError("Tenant access denied")

    subjects, next_cursor = await container.subjects.list_by_tenant(
        tenant_id,
        limit=limit,
        cursor=cursor,
    )
    items: list[SubjectResponse] = []
    for subject in subjects:
        roles = await container.role_bindings.list_roles_for_subject(tenant_id, subject.id)
        items.append(
            SubjectResponse(
                id=subject.id,
                tenant_id=subject.tenant_id,
                external_idp_sub=subject.external_idp_sub,
                email=subject.email,
                display_name=subject.display_name,
                status=subject.status.value,
                roles=roles,
                created_at=subject.created_at,
                updated_at=subject.updated_at,
            )
        )
    return SubjectListResponse(items=items, next_cursor=next_cursor)


@router.post(
    "/v1/tenants/{tenant_id}/api-keys",
    response_model=CreateApiKeyResponse,
    status_code=201,
    tags=["api-keys"],
)
async def create_api_key(
    tenant_id: UUID,
    body: CreateApiKeyRequest,
    principal: Principal = Depends(get_principal),
    container: IdentityContainer = Depends(get_container),
) -> CreateApiKeyResponse:
    if not principal.can_access_tenant(tenant_id):
        raise AuthorizationError("Tenant access denied")
    if not principal.has_scope("identity:write"):
        raise AuthorizationError("Missing identity:write scope")

    subject_id = body.subject_id or principal.subject_id
    result = await container.api_key_service.issue(
        CreateApiKeyCommand(
            tenant_id=tenant_id,
            subject_id=subject_id,
            name=body.name,
            scopes=tuple(body.scopes),
            expires_at=body.expires_at,
        )
    )
    return CreateApiKeyResponse(
        id=result.id,
        key_prefix=result.key_prefix,
        key_once=result.plaintext_key,
        name=result.name,
        scopes=list(result.scopes),
        expires_at=result.expires_at,
    )


@router.delete(
    "/v1/tenants/{tenant_id}/api-keys/{api_key_id}",
    status_code=204,
    tags=["api-keys"],
)
async def revoke_api_key(
    tenant_id: UUID,
    api_key_id: UUID,
    principal: Principal = Depends(get_principal),
    container: IdentityContainer = Depends(get_container),
) -> None:
    if not principal.can_access_tenant(tenant_id):
        raise AuthorizationError("Tenant access denied")
    await container.api_key_service.revoke(
        tenant_id=tenant_id,
        api_key_id=api_key_id,
        actor_subject_id=principal.subject_id,
    )
