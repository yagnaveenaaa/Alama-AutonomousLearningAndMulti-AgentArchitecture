from __future__ import annotations

from bff_web.clients.ports import (
    ApprovalDto,
    ChatMessageDto,
    MemoryDto,
    RepoDto,
    StreamHandshakeDto,
    TaskDto,
    TaskEventDto,
    UsageDto,
)
from bff_web.schema.types import (
    ApprovalType,
    ChatMessageType,
    MemoryType,
    RepositoryType,
    StreamHandshakeType,
    TaskEventType,
    TaskType,
    UsageType,
)


def map_task(dto: TaskDto) -> TaskType:
    return TaskType(
        id=dto.id,
        title=dto.title,
        objective=dto.objective,
        state=dto.state,
        repository_id=dto.repository_id,
        repository_name=dto.repository_name,
        created_at=dto.created_at,
        paused=dto.paused,
    )


def map_event(dto: TaskEventDto) -> TaskEventType:
    return TaskEventType(
        id=dto.id,
        sequence=dto.sequence,
        event_type=dto.event_type,
        actor_type=dto.actor_type,
        summary=dto.summary,
        created_at=dto.created_at,
    )


def map_approval(dto: ApprovalDto) -> ApprovalType:
    return ApprovalType(
        id=dto.id,
        gate=dto.gate,
        status=dto.status,
        reason=dto.reason,
    )


def map_repo(dto: RepoDto) -> RepositoryType:
    return RepositoryType(
        id=dto.id,
        full_name=dto.full_name,
        index_state=dto.index_state,
        last_synced_at=dto.last_synced_at,
    )


def map_memory(dto: MemoryDto) -> MemoryType:
    return MemoryType(
        id=dto.id,
        title=dto.title,
        scope=dto.scope,
        memory_type=dto.memory_type,
        status=dto.status,
        confidence=dto.confidence,
        created_at=dto.created_at,
    )


def map_usage(dto: UsageDto) -> UsageType:
    return UsageType(
        tokens_used=dto.tokens_used,
        tokens_budget=dto.tokens_budget,
        usd_micros_used=dto.usd_micros_used,
        usd_micros_budget=dto.usd_micros_budget,
    )


def map_chat_message(dto: ChatMessageDto) -> ChatMessageType:
    return ChatMessageType(
        id=dto.id,
        role=dto.role,
        content=dto.content,
        created_at=dto.created_at,
        task_id=dto.task_id,
    )


def map_handshake(dto: StreamHandshakeDto) -> StreamHandshakeType:
    return StreamHandshakeType(
        conversation_id=dto.conversation_id,
        stream_url=dto.stream_url,
        task_id=dto.task_id,
    )
