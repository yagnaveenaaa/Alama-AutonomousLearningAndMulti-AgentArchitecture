from __future__ import annotations

from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError, AuthorizationError, NotFoundError
from alama_common.ids import new_uuid7
from alama_common.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from fastapi import APIRouter, Depends, Header, Query, Request, Response

from repository_service.adapters.http.schemas import (
    ConnectRepositoryRequest,
    HealthResponse,
    IndexStatusResponse,
    InstallationResponse,
    RegisterInstallationRequest,
    ReindexRequest,
    ReindexResponse,
    RepositoryListResponse,
    RepositoryResponse,
    SnapshotListResponse,
    SnapshotResponse,
)
from repository_service.application.dto import (
    ConnectRepositoryCommand,
    IngestWebhookCommand,
    RegisterInstallationCommand,
    ReindexCommand,
)
from repository_service.container import RepositoryContainer
from repository_service.domain.models import RepositoryConnection, ScmProviderName

router = APIRouter()


def get_container(request: Request) -> RepositoryContainer:
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
        scopes=frozenset({"repos:read", "repos:write"}),
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


def _repo_response(repo: RepositoryConnection) -> RepositoryResponse:
    return RepositoryResponse(
        id=repo.id,
        tenant_id=repo.tenant_id,
        installation_id=repo.installation_id,
        provider=repo.provider,
        external_repo_id=repo.external_repo_id,
        full_name=repo.full_name,
        default_branch=repo.default_branch,
        visibility=repo.visibility.value,
        size_tier=repo.size_tier.value,
        last_synced_at=repo.last_synced_at,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="repository-service")


@router.post(
    "/v1/installations",
    response_model=InstallationResponse,
    status_code=201,
    tags=["installations"],
)
async def register_installation(
    body: RegisterInstallationRequest,
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> InstallationResponse:
    tenant_id = principal.primary_tenant_id()
    installation = await container.connect.register_installation(
        RegisterInstallationCommand(
            tenant_id=tenant_id,
            provider=body.provider,
            external_installation_id=body.external_installation_id,
            account_login=body.account_login,
            secret_ref_path=body.secret_ref_path,
        )
    )
    return InstallationResponse(
        id=installation.id,
        tenant_id=installation.tenant_id,
        provider=installation.provider,
        external_installation_id=installation.external_installation_id,
        account_login=installation.account_login,
        status=installation.status.value,
    )


@router.get("/v1/repositories", response_model=RepositoryListResponse, tags=["repositories"])
async def list_repositories(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> RepositoryListResponse:
    tenant_id = principal.primary_tenant_id()
    items, next_cursor = await container.repositories.list_by_tenant(
        tenant_id,
        limit=limit,
        cursor=cursor,
    )
    return RepositoryListResponse(
        items=[_repo_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/v1/repositories/{repository_id}",
    response_model=RepositoryResponse,
    tags=["repositories"],
)
async def get_repository(
    repository_id: UUID,
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> RepositoryResponse:
    repo = await container.repositories.get_by_id(repository_id)
    if (
        repo is None
        or repo.deleted_at is not None
        or not principal.can_access_tenant(repo.tenant_id)
    ):
        raise NotFoundError("Repository not found")
    return _repo_response(repo)


@router.post(
    "/v1/repositories/connect",
    response_model=RepositoryResponse,
    status_code=201,
    tags=["repositories"],
)
async def connect_repository(
    body: ConnectRepositoryRequest,
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> RepositoryResponse:
    if not principal.has_scope("repos:write"):
        raise AuthorizationError("Missing repos:write scope")
    repo = await container.connect.connect(
        ConnectRepositoryCommand(
            tenant_id=principal.primary_tenant_id(),
            provider=body.provider,
            installation_id=body.installation_id,
            external_repo_id=body.external_repo_id,
        )
    )
    return _repo_response(repo)


@router.delete("/v1/repositories/{repository_id}", status_code=204, tags=["repositories"])
async def disconnect_repository(
    repository_id: UUID,
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> Response:
    await container.connect.disconnect(
        tenant_id=principal.primary_tenant_id(),
        repository_id=repository_id,
    )
    return Response(status_code=204)


@router.post(
    "/v1/repositories/{repository_id}/reindex",
    response_model=ReindexResponse,
    status_code=202,
    tags=["repositories"],
)
async def reindex_repository(
    repository_id: UUID,
    body: ReindexRequest,
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> ReindexResponse:
    snapshot = await container.snapshots_service.request_reindex(
        ReindexCommand(
            tenant_id=principal.primary_tenant_id(),
            repository_id=repository_id,
            ref=body.ref,
        )
    )
    return ReindexResponse(snapshot_id=snapshot.id)


@router.get(
    "/v1/repositories/{repository_id}/snapshots",
    response_model=SnapshotListResponse,
    tags=["repositories"],
)
async def list_snapshots(
    repository_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> SnapshotListResponse:
    repo = await container.repositories.get_by_id(repository_id)
    if repo is None or not principal.can_access_tenant(repo.tenant_id):
        raise NotFoundError("Repository not found")
    items, next_cursor = await container.snapshots.list_by_repository(
        repository_id,
        limit=limit,
        cursor=cursor,
    )
    return SnapshotListResponse(
        items=[
            SnapshotResponse(
                id=item.id,
                repository_id=item.repository_id,
                commit_sha=item.commit_sha,
                parent_commit_sha=item.parent_commit_sha,
                state=item.state,
                index_generation_id=item.index_generation_id,
                created_at=item.created_at,
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/v1/repositories/{repository_id}/index/status",
    response_model=IndexStatusResponse,
    tags=["repositories"],
)
async def index_status(
    repository_id: UUID,
    principal: Principal = Depends(get_principal),
    container: RepositoryContainer = Depends(get_container),
) -> IndexStatusResponse:
    repo = await container.repositories.get_by_id(repository_id)
    if repo is None or not principal.can_access_tenant(repo.tenant_id):
        raise NotFoundError("Repository not found")
    latest = await container.snapshots.latest_for_repository(repository_id)
    if latest is None:
        return IndexStatusResponse(
            repository_id=repository_id,
            latest_snapshot_id=None,
            latest_commit_sha=None,
            state=None,
            index_generation_id=None,
        )
    return IndexStatusResponse(
        repository_id=repository_id,
        latest_snapshot_id=latest.id,
        latest_commit_sha=latest.commit_sha,
        state=latest.state.value,
        index_generation_id=latest.index_generation_id,
    )


@router.post("/webhooks/{provider}", status_code=202, tags=["webhooks"])
async def ingest_webhook(
    provider: ScmProviderName,
    request: Request,
    x_tenant_id: str = Header(alias="X-Tenant-Id"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_gitlab_token: str | None = Header(default=None, alias="X-Gitlab-Token"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_alama_secret_ref: str = Header(alias="X-Alama-Secret-Ref"),
    container: RepositoryContainer = Depends(get_container),
) -> dict[str, str]:
    """Accept webhooks with signature verification; always 202 after accept (LLD §5.3)."""

    body = await request.body()
    delivery_id = x_github_delivery or request.headers.get("X-Request-Id") or str(new_uuid7())
    event_type = x_github_event or request.headers.get("X-Gitlab-Event") or "unknown"
    signature = x_hub_signature_256 or x_gitlab_token
    await container.webhook_ingestor.ingest(
        IngestWebhookCommand(
            tenant_id=UUID(x_tenant_id),
            provider=provider,
            delivery_id=delivery_id,
            event_type=event_type,
            body=body,
            signature_header=signature,
            secret_ref_path=x_alama_secret_ref,
        )
    )
    return {"status": "accepted"}
