from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from bff_web.auth_context import AuthContext


@dataclass(frozen=True, slots=True)
class TaskDto:
    id: UUID
    title: str
    objective: str
    state: str
    repository_id: UUID
    repository_name: str
    created_at: datetime
    paused: bool


@dataclass(frozen=True, slots=True)
class TaskEventDto:
    id: UUID
    sequence: int
    event_type: str
    actor_type: str
    summary: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovalDto:
    id: UUID
    gate: str
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RepoDto:
    id: UUID
    full_name: str
    index_state: str
    last_synced_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryDto:
    id: UUID
    title: str
    scope: str
    memory_type: str
    status: str
    confidence: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UsageDto:
    tokens_used: int
    tokens_budget: int
    usd_micros_used: int
    usd_micros_budget: int


@dataclass(frozen=True, slots=True)
class ChatMessageDto:
    id: UUID
    role: str
    content: str
    created_at: datetime
    task_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class StreamHandshakeDto:
    conversation_id: UUID
    stream_url: str
    task_id: UUID | None = None


class TaskClient(Protocol):
    async def list_tasks(self, ctx: AuthContext) -> list[TaskDto]: ...

    async def get_task(self, ctx: AuthContext, task_id: UUID) -> TaskDto | None: ...

    async def list_events(self, ctx: AuthContext, task_id: UUID) -> list[TaskEventDto]: ...

    async def list_approvals(self, ctx: AuthContext, task_id: UUID) -> list[ApprovalDto]: ...

    async def decide_approval(
        self,
        ctx: AuthContext,
        *,
        task_id: UUID,
        approval_id: UUID,
        decision: str,
    ) -> ApprovalDto: ...

    async def create_task(
        self,
        ctx: AuthContext,
        *,
        repository_id: UUID,
        objective: str,
        title: str | None = None,
    ) -> TaskDto: ...


class RepositoryClient(Protocol):
    async def list_repos(self, ctx: AuthContext) -> list[RepoDto]: ...


class KnowledgeClient(Protocol):
    async def list_memories(self, ctx: AuthContext) -> list[MemoryDto]: ...

    async def list_chat(
        self, ctx: AuthContext, conversation_id: UUID | None
    ) -> list[ChatMessageDto]: ...

    async def send_chat(
        self,
        ctx: AuthContext,
        *,
        content: str,
        conversation_id: UUID | None,
        repository_id: UUID | None,
    ) -> tuple[list[ChatMessageDto], StreamHandshakeDto, TaskDto | None]: ...


class UsageClient(Protocol):
    async def get_usage(self, ctx: AuthContext) -> UsageDto: ...


@dataclass
class ServiceClients:
    """Typed clients to task/repo/knowledge (+ usage) (LLD §2.2)."""

    tasks: TaskClient
    repositories: RepositoryClient
    knowledge: KnowledgeClient
    usage: UsageClient
