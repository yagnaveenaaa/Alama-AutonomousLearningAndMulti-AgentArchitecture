from __future__ import annotations

from uuid import UUID

from alama_common.errors import AuthenticationError
from fastapi import APIRouter, Depends, Header, Request

from tool_gateway.adapters.http.schemas import (
    HealthResponse,
    InvokeRequest,
    InvokeResponse,
    MintCapabilityRequest,
    MintCapabilityResponse,
    ToolReceiptResponse,
)
from tool_gateway.container import ToolGatewayContainer
from tool_gateway.domain.models import ToolCallRequest

router = APIRouter()


def get_container(request: Request) -> ToolGatewayContainer:
    return request.app.state.container  # type: ignore[no-any-return]


def require_identity(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_subject_id: str | None = Header(default=None, alias="X-Subject-Id"),
) -> tuple[UUID, UUID]:
    if x_tenant_id is None or x_subject_id is None:
        raise AuthenticationError("Missing identity headers")
    try:
        return UUID(x_tenant_id), UUID(x_subject_id)
    except ValueError as exc:
        raise AuthenticationError("Invalid identity headers") from exc


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="tool-gateway")


@router.post(
    "/v1/capabilities/mint",
    response_model=MintCapabilityResponse,
    tags=["capabilities"],
)
async def mint_capability(
    body: MintCapabilityRequest,
    identity: tuple[UUID, UUID] = Depends(require_identity),
    container: ToolGatewayContainer = Depends(get_container),
) -> MintCapabilityResponse:
    tenant_id, subject_id = identity
    token = await container.gateway.mint_capability(
        tenant_id=tenant_id,
        task_id=body.task_id,
        subject_id=subject_id,
        tool=body.tool,
        paths=body.paths,
    )
    return MintCapabilityResponse(
        token=token.raw,
        token_id=token.token_id,
        tool=token.tool,
        paths=list(token.paths),
        expires_at=token.expires_at.isoformat(),
        policy_version=token.policy_version,
    )


@router.post("/v1/invoke", response_model=InvokeResponse, tags=["tools"])
async def invoke(
    body: InvokeRequest,
    identity: tuple[UUID, UUID] = Depends(require_identity),
    container: ToolGatewayContainer = Depends(get_container),
) -> InvokeResponse:
    tenant_id, _subject_id = identity
    result = await container.gateway.invoke(
        ToolCallRequest(
            tenant_id=tenant_id,
            task_id=body.task_id,
            tool=body.tool,
            args=dict(body.args),
            capability_raw=body.capability,
        )
    )
    receipt = result.receipt
    return InvokeResponse(
        ok=result.ok,
        output=result.output,
        receipt=ToolReceiptResponse(
            receipt_id=receipt.receipt_id,
            tool=receipt.tool,
            inputs_hash=receipt.inputs_hash,
            output_ref=receipt.output_ref,
            output_inline=receipt.output_inline,
            duration_ms=receipt.duration_ms,
            policy_version=receipt.policy_version,
            capability_id=receipt.capability_id,
            ok=receipt.ok,
        ),
    )
