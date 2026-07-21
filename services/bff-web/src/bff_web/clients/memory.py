from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from alama_common.errors import NotFoundError, ValidationError
from alama_common.ids import new_uuid7

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


def _now() -> datetime:
    return datetime.now(UTC)


class InMemoryTaskClient:
    def __init__(self) -> None:
        repo_a = UUID("01900000-0000-7000-8000-000000000001")
        repo_b = UUID("01900000-0000-7000-8000-000000000002")
        t1 = UUID("01900000-0000-7000-8000-000000000101")
        t2 = UUID("01900000-0000-7000-8000-000000000102")
        self._repos = {
            repo_a: "alama/platform",
            repo_b: "alama/retrieval",
        }
        self.tasks: dict[UUID, TaskDto] = {
            t1: TaskDto(
                id=t1,
                title="Harden JWT verification",
                objective="Add TokenVerifier helper with tests and docs",
                state="executing",
                repository_id=repo_a,
                repository_name=self._repos[repo_a],
                created_at=_now(),
                paused=False,
            ),
            t2: TaskDto(
                id=t2,
                title="Fix flaky retrieval tests",
                objective="Stabilize hybrid retrieval contract suite",
                state="awaiting_approval",
                repository_id=repo_b,
                repository_name=self._repos[repo_b],
                created_at=_now(),
                paused=False,
            ),
        }
        self.events: dict[UUID, list[TaskEventDto]] = {
            t1: [
                TaskEventDto(
                    id=new_uuid7(),
                    sequence=1,
                    event_type="com.alama.task.created.v1",
                    actor_type="user",
                    summary="Task created",
                    created_at=_now(),
                ),
                TaskEventDto(
                    id=new_uuid7(),
                    sequence=2,
                    event_type="com.alama.agent.plan_ready.v1",
                    actor_type="agent",
                    summary="Planner published 1-step plan",
                    created_at=_now(),
                ),
            ],
            t2: [
                TaskEventDto(
                    id=new_uuid7(),
                    sequence=1,
                    event_type="com.alama.task.created.v1",
                    actor_type="user",
                    summary="Task created",
                    created_at=_now(),
                ),
                TaskEventDto(
                    id=new_uuid7(),
                    sequence=2,
                    event_type="com.alama.task.approval_requested.v1",
                    actor_type="system",
                    summary="Gate: protected_branch_write",
                    created_at=_now(),
                ),
            ],
        }
        self.approvals: dict[UUID, list[ApprovalDto]] = {
            t2: [
                ApprovalDto(
                    id=UUID("01900000-0000-7000-8000-000000000201"),
                    gate="protected_branch_write",
                    status="pending",
                )
            ]
        }

    async def list_tasks(self, ctx: AuthContext) -> list[TaskDto]:
        _ = ctx
        return sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)

    async def get_task(self, ctx: AuthContext, task_id: UUID) -> TaskDto | None:
        _ = ctx
        return self.tasks.get(task_id)

    async def list_events(self, ctx: AuthContext, task_id: UUID) -> list[TaskEventDto]:
        _ = ctx
        return list(self.events.get(task_id, []))

    async def list_approvals(self, ctx: AuthContext, task_id: UUID) -> list[ApprovalDto]:
        _ = ctx
        return list(self.approvals.get(task_id, []))

    async def decide_approval(
        self,
        ctx: AuthContext,
        *,
        task_id: UUID,
        approval_id: UUID,
        decision: str,
    ) -> ApprovalDto:
        _ = ctx
        items = self.approvals.get(task_id, [])
        for item in items:
            if item.id == approval_id:
                if item.status != "pending":
                    raise ValidationError("Approval not pending")
                updated = ApprovalDto(
                    id=item.id,
                    gate=item.gate,
                    status=decision,
                    reason=item.reason,
                )
                self.approvals[task_id] = [
                    updated if a.id == approval_id else a for a in items
                ]
                task = self.tasks.get(task_id)
                if task is not None:
                    self.tasks[task_id] = TaskDto(
                        id=task.id,
                        title=task.title,
                        objective=task.objective,
                        state="executing" if decision == "approved" else "cancelled",
                        repository_id=task.repository_id,
                        repository_name=task.repository_name,
                        created_at=task.created_at,
                        paused=task.paused,
                    )
                return updated
        raise NotFoundError("Approval not found")

    async def create_task(
        self,
        ctx: AuthContext,
        *,
        repository_id: UUID,
        objective: str,
        title: str | None = None,
    ) -> TaskDto:
        _ = ctx
        repo_name = self._repos.get(repository_id, "alama/platform")
        task_id = new_uuid7()
        task = TaskDto(
            id=task_id,
            title=(title or objective)[:64],
            objective=objective,
            state="planning",
            repository_id=repository_id,
            repository_name=repo_name,
            created_at=_now(),
            paused=False,
        )
        self.tasks[task_id] = task
        self.events[task_id] = [
            TaskEventDto(
                id=new_uuid7(),
                sequence=1,
                event_type="com.alama.task.created.v1",
                actor_type="user",
                summary="Created from chat",
                created_at=_now(),
            )
        ]
        return task


class InMemoryRepositoryClient:
    def __init__(self) -> None:
        self._repos = [
            RepoDto(
                id=UUID("01900000-0000-7000-8000-000000000001"),
                full_name="alama/platform",
                index_state="ready",
                last_synced_at=_now(),
            ),
            RepoDto(
                id=UUID("01900000-0000-7000-8000-000000000002"),
                full_name="alama/retrieval",
                index_state="indexing",
                last_synced_at=_now(),
            ),
        ]

    async def list_repos(self, ctx: AuthContext) -> list[RepoDto]:
        _ = ctx
        return list(self._repos)


class InMemoryKnowledgeClient:
    def __init__(self, tasks: InMemoryTaskClient, *, stream_base_url: str) -> None:
        self._tasks = tasks
        self._stream_base = stream_base_url.rstrip("/")
        self._conversation_id = UUID("01900000-0000-7000-8000-000000000301")
        self.messages: list[ChatMessageDto] = [
            ChatMessageDto(
                id=new_uuid7(),
                role="assistant",
                content="Describe an objective. Alama will create a task and stream progress.",
                created_at=_now(),
            )
        ]
        self.memories: list[MemoryDto] = [
            MemoryDto(
                id=new_uuid7(),
                title="Prefer pytest",
                scope="org",
                memory_type="org_semantic",
                status="active",
                confidence=0.9,
                created_at=_now(),
            )
        ]

    async def list_memories(self, ctx: AuthContext) -> list[MemoryDto]:
        _ = ctx
        return list(self.memories)

    async def list_chat(
        self, ctx: AuthContext, conversation_id: UUID | None
    ) -> list[ChatMessageDto]:
        _ = (ctx, conversation_id)
        return list(self.messages)

    async def send_chat(
        self,
        ctx: AuthContext,
        *,
        content: str,
        conversation_id: UUID | None,
        repository_id: UUID | None,
    ) -> tuple[list[ChatMessageDto], StreamHandshakeDto, TaskDto | None]:
        _ = conversation_id
        repo_id = repository_id or UUID("01900000-0000-7000-8000-000000000001")
        task = await self._tasks.create_task(
            ctx, repository_id=repo_id, objective=content
        )
        user_msg = ChatMessageDto(
            id=new_uuid7(),
            role="user",
            content=content,
            created_at=_now(),
            task_id=task.id,
        )
        assistant_msg = ChatMessageDto(
            id=new_uuid7(),
            role="assistant",
            content=(
                f'Created task “{task.title}”. '
                f"Planner is drafting steps against {task.repository_name}."
            ),
            created_at=_now(),
            task_id=task.id,
        )
        self.messages.extend([user_msg, assistant_msg])
        handshake = StreamHandshakeDto(
            conversation_id=self._conversation_id,
            stream_url=f"{self._stream_base}/v1/tasks/{task.id}/events/stream",
            task_id=task.id,
        )
        return list(self.messages), handshake, task


class InMemoryUsageClient:
    async def get_usage(self, ctx: AuthContext) -> UsageDto:
        _ = ctx
        return UsageDto(
            tokens_used=240_000,
            tokens_budget=1_000_000,
            usd_micros_used=1_250_000,
            usd_micros_budget=5_000_000,
        )
