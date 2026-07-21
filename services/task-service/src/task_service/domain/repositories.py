from __future__ import annotations

from typing import Protocol
from uuid import UUID

from task_service.domain.models import Approval, Task, TaskEvent, TaskState


class TaskRepository(Protocol):
    async def get_by_id(self, task_id: UUID) -> Task | None: ...

    async def save(self, task: Task) -> None: ...

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        repository_id: UUID | None,
        state: TaskState | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Task], str | None]: ...


class ApprovalRepository(Protocol):
    async def get_by_id(self, approval_id: UUID) -> Approval | None: ...

    async def list_for_task(self, task_id: UUID) -> list[Approval]: ...

    async def save(self, approval: Approval) -> None: ...


class TaskEventRepository(Protocol):
    async def next_sequence(self, task_id: UUID) -> int: ...

    async def append(self, event: TaskEvent) -> None: ...

    async def list_for_task(
        self,
        task_id: UUID,
        *,
        from_seq: int | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[TaskEvent], str | None]: ...


class OutboxRepository(Protocol):
    async def enqueue(
        self,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> None: ...


class WorkflowHandle(Protocol):
    workflow_id: str
    run_id: str


class TaskWorkflowPort(Protocol):
    async def start(self, task: Task) -> WorkflowHandle: ...

    async def signal_cancel(self, workflow_id: str, reason: str | None) -> None: ...

    async def signal_pause(self, workflow_id: str) -> None: ...

    async def signal_resume(self, workflow_id: str) -> None: ...

    async def signal_approval(
        self,
        workflow_id: str,
        *,
        approval_id: UUID,
        decision: str,
    ) -> None: ...


class PolicyPort(Protocol):
    async def assert_can_create_task(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        repository_id: UUID,
    ) -> str: ...
