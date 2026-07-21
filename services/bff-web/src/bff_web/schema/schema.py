from __future__ import annotations

from typing import Any
from uuid import UUID

import strawberry
from strawberry.types import Info

from bff_web.mappers import (
    map_approval,
    map_chat_message,
    map_event,
    map_handshake,
    map_memory,
    map_repo,
    map_task,
    map_usage,
)
from bff_web.schema.types import (
    ApprovalType,
    ChatMessageType,
    MemoryType,
    RepositoryType,
    SendChatPayload,
    TaskEventType,
    TaskType,
    UsageType,
)


def _ctx(info: Info) -> dict[str, Any]:
    return info.context  # type: ignore[no-any-return]


@strawberry.type
class Query:
    """Root query — Task / Repo / Chat / Memory / Usage (LLD §2.2)."""

    @strawberry.field
    async def tasks(self, info: Info) -> list[TaskType]:
        ctx = _ctx(info)
        items = await ctx["clients"].tasks.list_tasks(ctx["auth"])
        return [map_task(item) for item in items]

    @strawberry.field
    async def task(self, info: Info, id: UUID) -> TaskType | None:
        ctx = _ctx(info)
        item = await ctx["loaders"].task(id)
        return map_task(item) if item else None

    @strawberry.field
    async def task_events(self, info: Info, task_id: UUID) -> list[TaskEventType]:
        ctx = _ctx(info)
        items = await ctx["loaders"].events(task_id)
        return [map_event(item) for item in items]

    @strawberry.field
    async def task_approvals(self, info: Info, task_id: UUID) -> list[ApprovalType]:
        ctx = _ctx(info)
        items = await ctx["loaders"].approvals(task_id)
        return [map_approval(item) for item in items]

    @strawberry.field
    async def repositories(self, info: Info) -> list[RepositoryType]:
        ctx = _ctx(info)
        items = await ctx["loaders"].repos()
        return [map_repo(item) for item in items]

    @strawberry.field
    async def chat_messages(
        self, info: Info, conversation_id: UUID | None = None
    ) -> list[ChatMessageType]:
        ctx = _ctx(info)
        items = await ctx["clients"].knowledge.list_chat(ctx["auth"], conversation_id)
        return [map_chat_message(item) for item in items]

    @strawberry.field
    async def memories(self, info: Info) -> list[MemoryType]:
        ctx = _ctx(info)
        items = await ctx["clients"].knowledge.list_memories(ctx["auth"])
        return [map_memory(item) for item in items]

    @strawberry.field
    async def usage(self, info: Info) -> UsageType:
        ctx = _ctx(info)
        item = await ctx["clients"].usage.get_usage(ctx["auth"])
        return map_usage(item)


@strawberry.type
class Mutation:
    """Root mutation — approvals + chat stream handshake."""

    @strawberry.mutation
    async def decide_approval(
        self,
        info: Info,
        task_id: UUID,
        approval_id: UUID,
        decision: str,
    ) -> ApprovalType:
        ctx = _ctx(info)
        item = await ctx["clients"].tasks.decide_approval(
            ctx["auth"],
            task_id=task_id,
            approval_id=approval_id,
            decision=decision,
        )
        return map_approval(item)

    @strawberry.mutation
    async def send_chat(
        self,
        info: Info,
        content: str,
        conversation_id: UUID | None = None,
        repository_id: UUID | None = None,
    ) -> SendChatPayload:
        ctx = _ctx(info)
        messages, handshake, task = await ctx["clients"].knowledge.send_chat(
            ctx["auth"],
            content=content,
            conversation_id=conversation_id,
            repository_id=repository_id,
        )
        return SendChatPayload(
            messages=[map_chat_message(m) for m in messages],
            handshake=map_handshake(handshake),
            task=map_task(task) if task else None,
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
