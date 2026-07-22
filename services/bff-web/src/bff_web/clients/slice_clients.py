from __future__ import annotations

from uuid import UUID

from alama_common.ids import new_uuid7
from alama_slice.orchestrator import VerticalSliceOrchestrator
from alama_slice.store import SliceStore

from bff_web.auth_context import AuthContext
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


class SliceTaskClient:
    def __init__(self, orch: VerticalSliceOrchestrator) -> None:
        self._orch = orch

    def _task_dto(self, task_id: UUID) -> TaskDto | None:
        task = self._orch.store.tasks.get(task_id)
        if task is None:
            return None
        return TaskDto(
            id=task.id,
            title=task.title,
            objective=task.objective,
            state=task.state,
            repository_id=task.repository_id,
            repository_name=task.repository_name,
            created_at=task.created_at,
            paused=task.paused,
        )

    async def list_tasks(self, ctx: AuthContext) -> list[TaskDto]:
        _ = ctx
        items = [
            TaskDto(
                id=t.id,
                title=t.title,
                objective=t.objective,
                state=t.state,
                repository_id=t.repository_id,
                repository_name=t.repository_name,
                created_at=t.created_at,
                paused=t.paused,
            )
            for t in self._orch.store.tasks.values()
        ]
        return sorted(items, key=lambda t: t.created_at, reverse=True)

    async def get_task(self, ctx: AuthContext, task_id: UUID) -> TaskDto | None:
        _ = ctx
        return self._task_dto(task_id)

    async def list_events(self, ctx: AuthContext, task_id: UUID) -> list[TaskEventDto]:
        _ = ctx
        return [
            TaskEventDto(
                id=e.id,
                sequence=e.sequence,
                event_type=e.event_type,
                actor_type=e.actor_type,
                summary=e.summary,
                created_at=e.created_at,
            )
            for e in self._orch.store.events.get(task_id, [])
        ]

    async def list_approvals(self, ctx: AuthContext, task_id: UUID) -> list[ApprovalDto]:
        _ = ctx
        return [
            ApprovalDto(id=a.id, gate=a.gate, status=a.status, reason=a.reason)
            for a in self._orch.store.approvals.get(task_id, [])
        ]

    async def decide_approval(
        self,
        ctx: AuthContext,
        *,
        task_id: UUID,
        approval_id: UUID,
        decision: str,
    ) -> ApprovalDto:
        _ = ctx
        item = await self._orch.decide_approval(
            task_id=task_id, approval_id=approval_id, decision=decision
        )
        return ApprovalDto(
            id=item.id, gate=item.gate, status=item.status, reason=item.reason
        )

    async def create_task(
        self,
        ctx: AuthContext,
        *,
        repository_id: UUID,
        objective: str,
        title: str | None = None,
    ) -> TaskDto:
        _ = (ctx, repository_id, title)
        task = await self._orch.send_chat(objective)
        dto = self._task_dto(task.id)
        assert dto is not None
        return dto


class SliceRepositoryClient:
    def __init__(self, store: SliceStore) -> None:
        self._store = store

    async def list_repos(self, ctx: AuthContext) -> list[RepoDto]:
        _ = ctx
        return [
            RepoDto(
                id=r.id,
                full_name=r.full_name,
                index_state=r.index_state,
                last_synced_at=r.last_synced_at,
            )
            for r in self._store.repos.values()
        ]


class SliceKnowledgeClient:
    def __init__(
        self,
        orch: VerticalSliceOrchestrator,
        tasks: SliceTaskClient,
        *,
        stream_base_url: str,
    ) -> None:
        self._orch = orch
        self._tasks = tasks
        self._stream_base = stream_base_url.rstrip("/")
        self._conversation_id = new_uuid7()

    async def list_memories(self, ctx: AuthContext) -> list[MemoryDto]:
        _ = ctx
        return [
            MemoryDto(
                id=new_uuid7(),
                title="Prefer pytest for Python fixtures",
                scope="org",
                memory_type="org_semantic",
                status="active",
                confidence=0.9,
                created_at=self._orch.store.messages[0].created_at,
            )
        ]

    async def list_chat(
        self, ctx: AuthContext, conversation_id: UUID | None
    ) -> list[ChatMessageDto]:
        _ = (ctx, conversation_id)
        return [
            ChatMessageDto(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                task_id=m.task_id,
            )
            for m in self._orch.store.messages
        ]

    async def send_chat(
        self,
        ctx: AuthContext,
        *,
        content: str,
        conversation_id: UUID | None,
        repository_id: UUID | None,
    ) -> tuple[list[ChatMessageDto], StreamHandshakeDto, TaskDto | None]:
        _ = (ctx, conversation_id, repository_id)
        task = await self._orch.send_chat(content)
        messages = await self.list_chat(ctx, conversation_id)
        handshake = StreamHandshakeDto(
            conversation_id=self._conversation_id,
            stream_url=f"{self._stream_base}/v1/tasks/{task.id}/events/stream",
            task_id=task.id,
        )
        dto = await self._tasks.get_task(ctx, task.id)
        return messages, handshake, dto


class SliceUsageClient:
    async def get_usage(self, ctx: AuthContext) -> UsageDto:
        _ = ctx
        return UsageDto(
            tokens_used=12_000,
            tokens_budget=1_000_000,
            usd_micros_used=250_000,
            usd_micros_budget=5_000_000,
        )
