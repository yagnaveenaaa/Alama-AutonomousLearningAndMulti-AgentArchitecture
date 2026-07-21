from __future__ import annotations

from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError
from alama_common.ids import new_uuid7
from fastapi import APIRouter, Depends, Header, Request

from policy_service.adapters.http.schemas import (
    EvaluatePolicyRequest,
    HealthResponse,
    PolicyBundleListResponse,
    PolicyBundleResponse,
    PolicyDecisionResponse,
    UpsertDraftBundleRequest,
)
from policy_service.application.dto import (
    ActivateBundleCommand,
    EvaluatePolicyCommand,
    UpsertDraftBundleCommand,
)
from policy_service.container import PolicyContainer
from policy_service.domain.models import PolicyBundle, PolicyDecision

router = APIRouter()


def get_container(request: Request) -> PolicyContainer:
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
        scopes=frozenset({"policy:read", "policy:write", "policy:admin"}),
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


def _decision_response(decision: PolicyDecision) -> PolicyDecisionResponse:
    return PolicyDecisionResponse(
        effect=decision.effect.value,
        required_approvals=list(decision.required_approvals),
        constraints=dict(decision.constraints),
        policy_version=decision.policy_version,
        reasons=list(decision.reasons),
    )


def _bundle_response(bundle: PolicyBundle) -> PolicyBundleResponse:
    return PolicyBundleResponse(
        id=bundle.id,
        tenant_id=bundle.tenant_id,
        version=bundle.version,
        bundle_ref=bundle.bundle_ref,
        status=bundle.status.value,
        checksum=bundle.checksum,
        activated_at=bundle.activated_at.isoformat() if bundle.activated_at else None,
        created_at=bundle.created_at.isoformat(),
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="policy-service")


@router.post(
    "/v1/policy/evaluate",
    response_model=PolicyDecisionResponse,
    tags=["policy"],
)
async def evaluate_policy(
    body: EvaluatePolicyRequest,
    principal: Principal = Depends(get_principal),
    container: PolicyContainer = Depends(get_container),
) -> PolicyDecisionResponse:
    decision = await container.evaluate.handle(
        EvaluatePolicyCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            action=body.action,
            attributes=body.attributes,
            policy_version=body.policy_version,
            dry_run=body.dry_run,
        )
    )
    return _decision_response(decision)


@router.get(
    "/v1/policy/bundles",
    response_model=PolicyBundleListResponse,
    tags=["policy"],
)
async def list_bundles(
    principal: Principal = Depends(get_principal),
    container: PolicyContainer = Depends(get_container),
) -> PolicyBundleListResponse:
    items = await container.list_bundles.handle(principal.primary_tenant_id())
    return PolicyBundleListResponse(items=[_bundle_response(item) for item in items])


@router.post(
    "/v1/policy/bundles",
    response_model=PolicyBundleResponse,
    status_code=201,
    tags=["policy"],
)
async def upsert_draft_bundle(
    body: UpsertDraftBundleRequest,
    principal: Principal = Depends(get_principal),
    container: PolicyContainer = Depends(get_container),
) -> PolicyBundleResponse:
    bundle = await container.upsert_draft.handle(
        UpsertDraftBundleCommand(
            tenant_id=principal.primary_tenant_id(),
            version=body.version,
            rules_payload={"schema_version": 1, "rules": body.rules},
            subject_id=principal.subject_id,
        )
    )
    return _bundle_response(bundle)


@router.post(
    "/v1/policy/bundles/{version}/activate",
    response_model=PolicyBundleResponse,
    tags=["policy"],
)
async def activate_bundle(
    version: str,
    principal: Principal = Depends(get_principal),
    container: PolicyContainer = Depends(get_container),
) -> PolicyBundleResponse:
    bundle = await container.activate.handle(
        ActivateBundleCommand(
            tenant_id=principal.primary_tenant_id(),
            version=version,
            subject_id=principal.subject_id,
        )
    )
    return _bundle_response(bundle)
