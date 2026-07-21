from __future__ import annotations

from datetime import datetime
from uuid import UUID

import strawberry


@strawberry.type(name="Task")
class TaskType:
    id: UUID
    title: str
    objective: str
    state: str
    repository_id: UUID
    repository_name: str
    created_at: datetime
    paused: bool


@strawberry.type(name="TaskEvent")
class TaskEventType:
    id: UUID
    sequence: int
    event_type: str
    actor_type: str
    summary: str
    created_at: datetime


@strawberry.type(name="Approval")
class ApprovalType:
    id: UUID
    gate: str
    status: str
    reason: str | None


@strawberry.type(name="Repository")
class RepositoryType:
    id: UUID
    full_name: str
    index_state: str
    last_synced_at: datetime


@strawberry.type(name="Memory")
class MemoryType:
    id: UUID
    title: str
    scope: str
    memory_type: str
    status: str
    confidence: float
    created_at: datetime


@strawberry.type(name="Usage")
class UsageType:
    tokens_used: int
    tokens_budget: int
    usd_micros_used: int
    usd_micros_budget: int


@strawberry.type(name="ChatMessage")
class ChatMessageType:
    id: UUID
    role: str
    content: str
    created_at: datetime
    task_id: UUID | None


@strawberry.type(name="StreamHandshake")
class StreamHandshakeType:
    conversation_id: UUID
    stream_url: str
    task_id: UUID | None


@strawberry.type(name="SendChatPayload")
class SendChatPayload:
    messages: list[ChatMessageType]
    handshake: StreamHandshakeType
    task: TaskType | None
