from __future__ import annotations

from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError
from alama_common.ids import new_uuid7
from alama_common.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from fastapi import APIRouter, Depends, Header, Query, Request, Response

from knowledge_service.adapters.http.schemas import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    CreateMemoryRequest,
    HealthResponse,
    MemoryListResponse,
    MemoryResponse,
    MessageResponse,
    PatchMemoryRequest,
    PostMessageRequest,
)
from knowledge_service.application.dto import (
    CreateConversationCommand,
    CreateMemoryCommand,
    DeleteMemoryCommand,
    PatchMemoryCommand,
    PostMessageCommand,
)
from knowledge_service.container import KnowledgeContainer
from knowledge_service.domain.models import Conversation, MemoryItem, Message

router = APIRouter()


def get_container(request: Request) -> KnowledgeContainer:
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
        scopes=frozenset({"knowledge:read", "knowledge:write"}),
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


def _memory_response(item: MemoryItem) -> MemoryResponse:
    return MemoryResponse(
        id=item.id,
        tenant_id=item.tenant_id,
        scope=item.scope.value,
        memory_type=item.memory_type.value,
        repository_id=item.repository_id,
        subject_id=item.subject_id,
        task_id=item.task_id,
        title=item.title,
        content_ref=item.content_ref,
        content_hash=item.content_hash,
        provenance=dict(item.provenance),
        confidence=item.confidence,
        acl=dict(item.acl),
        embedding_model=item.embedding_model,
        vector_ref=item.vector_ref,
        expires_at=item.expires_at,
        legal_hold=item.legal_hold,
        status=item.status.value,
        created_at=item.created_at,
        updated_at=item.updated_at,
        version=item.version,
    )


def _conversation_response(item: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=item.id,
        tenant_id=item.tenant_id,
        task_id=item.task_id,
        repository_id=item.repository_id,
        title=item.title,
        created_at=item.created_at,
        updated_at=item.updated_at,
        version=item.version,
    )


def _message_response(message: Message, *, task_accepted: bool = False) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        tenant_id=message.tenant_id,
        conversation_id=message.conversation_id,
        role=message.role.value,
        content_ref=message.content_ref,
        token_estimate=message.token_estimate,
        sequence=message.sequence,
        created_at=message.created_at,
        task_accepted=task_accepted,
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="knowledge-service")


@router.get("/v1/memories", response_model=MemoryListResponse, tags=["memories"])
async def list_memories(
    principal: Principal = Depends(get_principal),
    container: KnowledgeContainer = Depends(get_container),
    scope: str | None = Query(default=None),
    status: str | None = Query(default=None),
    memory_type: str | None = Query(default=None),
    repository_id: UUID | None = Query(default=None),
    subject_id: UUID | None = Query(default=None),
    task_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
) -> MemoryListResponse:
    items, next_cursor = await container.memories.list(
        principal.primary_tenant_id(),
        scope=scope,
        status=status,
        memory_type=memory_type,
        repository_id=repository_id,
        subject_id=subject_id,
        task_id=task_id,
        query=q,
        limit=limit,
        cursor=cursor,
    )
    return MemoryListResponse(
        items=[_memory_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post("/v1/memories", response_model=MemoryResponse, status_code=201, tags=["memories"])
async def create_memory(
    body: CreateMemoryRequest,
    principal: Principal = Depends(get_principal),
    container: KnowledgeContainer = Depends(get_container),
) -> MemoryResponse:
    item = await container.memories.create(
        CreateMemoryCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            scope=body.scope,
            memory_type=body.memory_type,
            title=body.title,
            content=body.content,
            confidence=body.confidence,
            provenance=body.provenance,
            acl=body.acl,
            repository_id=body.repository_id,
            task_id=body.task_id,
            promote=body.promote,
            policy_constraints=body.policy_constraints,
        )
    )
    return _memory_response(item)


@router.patch("/v1/memories/{memory_id}", response_model=MemoryResponse, tags=["memories"])
async def patch_memory(
    memory_id: UUID,
    body: PatchMemoryRequest,
    principal: Principal = Depends(get_principal),
    container: KnowledgeContainer = Depends(get_container),
) -> MemoryResponse:
    item = await container.memories.patch(
        PatchMemoryCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            memory_id=memory_id,
            title=body.title,
            confidence=body.confidence,
            acl=body.acl,
            status=body.status,
        )
    )
    return _memory_response(item)


@router.delete("/v1/memories/{memory_id}", status_code=204, tags=["memories"])
async def delete_memory(
    memory_id: UUID,
    principal: Principal = Depends(get_principal),
    container: KnowledgeContainer = Depends(get_container),
) -> Response:
    await container.memories.delete(
        DeleteMemoryCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            memory_id=memory_id,
        )
    )
    return Response(status_code=204)


@router.get(
    "/v1/conversations",
    response_model=ConversationListResponse,
    tags=["conversations"],
)
async def list_conversations(
    principal: Principal = Depends(get_principal),
    container: KnowledgeContainer = Depends(get_container),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
) -> ConversationListResponse:
    items, next_cursor = await container.conversations.list(
        principal.primary_tenant_id(),
        limit=limit,
        cursor=cursor,
    )
    return ConversationListResponse(
        items=[_conversation_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post(
    "/v1/conversations",
    response_model=ConversationResponse,
    status_code=201,
    tags=["conversations"],
)
async def create_conversation(
    body: CreateConversationRequest,
    principal: Principal = Depends(get_principal),
    container: KnowledgeContainer = Depends(get_container),
) -> ConversationResponse:
    conversation = await container.conversations.create(
        CreateConversationCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            title=body.title or "Untitled conversation",
            task_id=body.task_id,
            repository_id=body.repository_id,
        )
    )
    return _conversation_response(conversation)


@router.post(
    "/v1/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    tags=["conversations"],
)
async def post_message(
    conversation_id: UUID,
    body: PostMessageRequest,
    response: Response,
    principal: Principal = Depends(get_principal),
    container: KnowledgeContainer = Depends(get_container),
) -> MessageResponse:
    result = await container.conversations.post_message(
        PostMessageCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            conversation_id=conversation_id,
            content=body.content,
            role=body.role,
            start_task=body.start_task,
        )
    )
    response.status_code = 202 if result.task_accepted else 201
    return _message_response(result.message, task_accepted=result.task_accepted)
