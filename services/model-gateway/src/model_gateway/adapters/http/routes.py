from __future__ import annotations

from uuid import UUID

from alama_common.errors import AuthenticationError
from fastapi import APIRouter, Depends, Header, Request

from model_gateway.adapters.http.schemas import (
    CompleteRequest,
    CompleteResponse,
    EmbedRequest,
    EmbedResponse,
    HealthResponse,
    RerankRequest,
    RerankResponse,
)
from model_gateway.container import ModelGatewayContainer
from model_gateway.domain.models import (
    ChatMessage,
    ModelCapability,
    ModelRequest,
    ModelTier,
)

router = APIRouter()


def get_container(request: Request) -> ModelGatewayContainer:
    return request.app.state.container  # type: ignore[no-any-return]


def require_tenant(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> UUID:
    if x_tenant_id is None:
        raise AuthenticationError("Missing X-Tenant-Id")
    try:
        return UUID(x_tenant_id)
    except ValueError as exc:
        raise AuthenticationError("Invalid X-Tenant-Id") from exc


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="model-gateway")


@router.post("/v1/complete", response_model=CompleteResponse, tags=["model"])
async def complete(
    body: CompleteRequest,
    tenant_id: UUID = Depends(require_tenant),
    container: ModelGatewayContainer = Depends(get_container),
) -> CompleteResponse:
    result = await container.gateway.complete(
        ModelRequest(
            tenant_id=tenant_id,
            task_id=body.task_id,
            purpose=body.purpose,
            capability=ModelCapability.COMPLETE,
            preferred_tier=ModelTier(body.preferred_tier),
            residency=body.residency,
            messages=tuple(
                ChatMessage(role=m.role, content=m.content) for m in body.messages
            ),
            template_name=body.template_name,
            template_version=body.template_version,
            template_inputs=dict(body.template_inputs),
            json_schema_name=body.json_schema_name,
            max_tokens=body.max_tokens,
        )
    )
    return CompleteResponse(
        request_id=result.request_id,
        model=result.model,
        provider=result.provider,
        content=result.content,
        parsed_json=result.parsed_json,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        fallback_used=result.fallback_used,
    )


@router.post("/v1/embed", response_model=EmbedResponse, tags=["model"])
async def embed(
    body: EmbedRequest,
    tenant_id: UUID = Depends(require_tenant),
    container: ModelGatewayContainer = Depends(get_container),
) -> EmbedResponse:
    result = await container.gateway.embed(
        ModelRequest(
            tenant_id=tenant_id,
            task_id=body.task_id,
            purpose=body.purpose,
            capability=ModelCapability.EMBED,
            preferred_tier=ModelTier.EMBEDDING,
            residency=body.residency,
            texts=tuple(body.texts),
        )
    )
    return EmbedResponse(
        request_id=result.request_id,
        model=result.model,
        provider=result.provider,
        vectors=[list(v) for v in result.vectors],
        input_tokens=result.input_tokens,
        dimension=result.dimension,
    )


@router.post("/v1/rerank", response_model=RerankResponse, tags=["model"])
async def rerank(
    body: RerankRequest,
    tenant_id: UUID = Depends(require_tenant),
    container: ModelGatewayContainer = Depends(get_container),
) -> RerankResponse:
    result = await container.gateway.rerank(
        ModelRequest(
            tenant_id=tenant_id,
            task_id=body.task_id,
            purpose=body.purpose,
            capability=ModelCapability.RERANK,
            preferred_tier=ModelTier.RERANK,
            residency=body.residency,
            query=body.query,
            documents=tuple(body.documents),
        )
    )
    return RerankResponse(
        request_id=result.request_id,
        model=result.model,
        provider=result.provider,
        ranked_indices=list(result.ranked_indices),
        scores=list(result.scores),
        input_tokens=result.input_tokens,
    )
