from __future__ import annotations

from uuid import UUID

from alama_common.errors import BudgetExceededError, NotFoundError

from task_service.application.dto import (
    CancelTaskCommand,
    CreateTaskCommand,
    PauseResumeCommand,
)
from task_service.application.events import TaskEventProjector
from task_service.domain.models import ActorType, Task
from task_service.domain.repositories import (
    OutboxRepository,
    PolicyPort,
    TaskRepository,
    TaskWorkflowPort,
)


class CreateTaskHandler:
    """Validate policy + budget → persist → start workflow (LLD §2.5)."""

    def __init__(
        self,
        tasks: TaskRepository,
        workflows: TaskWorkflowPort,
        policy: PolicyPort,
        projector: TaskEventProjector,
        outbox: OutboxRepository,
        *,
        default_budget_tokens: int,
        default_budget_usd_micros: int,
        default_policy_version: str,
        default_base_commit_sha: str = "0" * 40,
    ) -> None:
        self._tasks = tasks
        self._workflows = workflows
        self._policy = policy
        self._projector = projector
        self._outbox = outbox
        self._default_budget_tokens = default_budget_tokens
        self._default_budget_usd_micros = default_budget_usd_micros
        self._default_policy_version = default_policy_version
        self._default_base_commit_sha = default_base_commit_sha

    async def handle(self, command: CreateTaskCommand) -> Task:
        policy_version = await self._policy.assert_can_create_task(
            tenant_id=command.tenant_id,
            subject_id=command.subject_id,
            repository_id=command.repository_id,
        )

        budget_tokens = (
            command.budget_tokens
            if command.budget_tokens is not None
            else self._default_budget_tokens
        )
        budget_usd = (
            command.budget_usd_micros
            if command.budget_usd_micros is not None
            else self._default_budget_usd_micros
        )
        if budget_tokens < 1 or budget_usd < 1:
            raise BudgetExceededError(
                "Task budget exhausted or invalid",
                details={"budget_tokens": budget_tokens, "budget_usd_micros": budget_usd},
            )

        task = Task.create(
            tenant_id=command.tenant_id,
            repository_id=command.repository_id,
            created_by=command.subject_id,
            title=command.title or "",
            objective=command.objective,
            base_commit_sha=command.base_commit_sha or self._default_base_commit_sha,
            budget_tokens=budget_tokens,
            budget_usd_micros=budget_usd,
            policy_version=policy_version or self._default_policy_version,
            priority=command.priority,
            parent_task_id=command.parent_task_id,
        )
        await self._tasks.save(task)
        await self._projector.project(
            tenant_id=task.tenant_id,
            task_id=task.id,
            event_type="com.alama.task.created.v1",
            actor_type=ActorType.USER,
            actor_id=str(command.subject_id),
            payload={
                "repository_id": str(task.repository_id),
                "objective": task.objective,
                "state": task.state.value,
            },
        )

        handle = await self._workflows.start(task)
        task.workflow_id = handle.workflow_id
        task.mark_workflow_started(run_id=handle.run_id)
        await self._tasks.save(task)
        await self._projector.project(
            tenant_id=task.tenant_id,
            task_id=task.id,
            event_type="com.alama.task.workflow_started.v1",
            actor_type=ActorType.SYSTEM,
            actor_id="task-service",
            payload={"workflow_id": task.workflow_id, "run_id": task.run_id},
        )
        await self._outbox.enqueue(
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="com.alama.task.started.v1",
            payload={
                "task_id": str(task.id),
                "tenant_id": str(task.tenant_id),
                "workflow_id": task.workflow_id,
                "run_id": task.run_id,
            },
        )
        return task


class TaskLifecycleService:
    """Cancel / pause / resume with Temporal signals."""

    def __init__(
        self,
        tasks: TaskRepository,
        workflows: TaskWorkflowPort,
        projector: TaskEventProjector,
    ) -> None:
        self._tasks = tasks
        self._workflows = workflows
        self._projector = projector

    async def _load(self, tenant_id: UUID, task_id: UUID) -> Task:
        task = await self._tasks.get_by_id(task_id)
        if task is None or task.tenant_id != tenant_id:
            raise NotFoundError("Task not found")
        return task

    async def cancel(self, command: CancelTaskCommand) -> Task:
        task = await self._load(command.tenant_id, command.task_id)
        task.cancel()
        await self._workflows.signal_cancel(task.workflow_id, command.reason)
        await self._tasks.save(task)
        await self._projector.project(
            tenant_id=task.tenant_id,
            task_id=task.id,
            event_type="com.alama.task.cancelled.v1",
            actor_type=ActorType.USER,
            actor_id=str(command.subject_id),
            payload={"reason": command.reason},
        )
        return task

    async def pause(self, command: PauseResumeCommand) -> Task:
        task = await self._load(command.tenant_id, command.task_id)
        task.pause()
        await self._workflows.signal_pause(task.workflow_id)
        await self._tasks.save(task)
        await self._projector.project(
            tenant_id=task.tenant_id,
            task_id=task.id,
            event_type="com.alama.task.paused.v1",
            actor_type=ActorType.USER,
            actor_id=str(command.subject_id),
        )
        return task

    async def resume(self, command: PauseResumeCommand) -> Task:
        task = await self._load(command.tenant_id, command.task_id)
        task.resume()
        await self._workflows.signal_resume(task.workflow_id)
        await self._tasks.save(task)
        await self._projector.project(
            tenant_id=task.tenant_id,
            task_id=task.id,
            event_type="com.alama.task.resumed.v1",
            actor_type=ActorType.USER,
            actor_id=str(command.subject_id),
        )
        return task
