from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from alama_common.ids import new_uuid7
from alama_common.pagination import decode_cursor, encode_cursor

from task_service.domain.models import Approval, Task, TaskEvent, TaskState


class InMemoryOutbox:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def enqueue(
        self,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        self.events.append(
            {
                "id": str(new_uuid7()),
                "aggregate_type": aggregate_type,
                "aggregate_id": str(aggregate_id),
                "event_type": event_type,
                "payload": payload,
            }
        )


class InMemoryTaskStore:
    def __init__(self) -> None:
        self.tasks: dict[UUID, Task] = {}
        self.approvals: dict[UUID, Approval] = {}
        self.events: dict[UUID, list[TaskEvent]] = {}
        self.outbox = InMemoryOutbox()


class InMemoryTaskRepository:
    def __init__(self, store: InMemoryTaskStore) -> None:
        self._store = store

    async def get_by_id(self, task_id: UUID) -> Task | None:
        return self._store.tasks.get(task_id)

    async def save(self, task: Task) -> None:
        self._store.tasks[task.id] = task

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        repository_id: UUID | None,
        state: TaskState | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Task], str | None]:
        items = [
            task
            for task in self._store.tasks.values()
            if task.tenant_id == tenant_id
            and (repository_id is None or task.repository_id == repository_id)
            and (state is None or task.state == state)
        ]
        items.sort(key=lambda t: t.created_at, reverse=True)
        offset = 0
        if cursor:
            decoded = decode_cursor(cursor)
            offset = int(decoded.get("offset", 0))
        page = items[offset : offset + limit]
        next_cursor = (
            encode_cursor({"offset": offset + limit}) if offset + limit < len(items) else None
        )
        return page, next_cursor


class InMemoryApprovalRepository:
    def __init__(self, store: InMemoryTaskStore) -> None:
        self._store = store

    async def get_by_id(self, approval_id: UUID) -> Approval | None:
        return self._store.approvals.get(approval_id)

    async def list_for_task(self, task_id: UUID) -> list[Approval]:
        return [a for a in self._store.approvals.values() if a.task_id == task_id]

    async def save(self, approval: Approval) -> None:
        self._store.approvals[approval.id] = approval


class InMemoryTaskEventRepository:
    def __init__(self, store: InMemoryTaskStore) -> None:
        self._store = store

    async def next_sequence(self, task_id: UUID) -> int:
        return len(self._store.events.get(task_id, [])) + 1

    async def append(self, event: TaskEvent) -> None:
        self._store.events.setdefault(event.task_id, []).append(event)

    async def list_for_task(
        self,
        task_id: UUID,
        *,
        from_seq: int | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[TaskEvent], str | None]:
        events = list(self._store.events.get(task_id, []))
        events.sort(key=lambda e: e.sequence)
        if from_seq is not None:
            events = [e for e in events if e.sequence >= from_seq]
        offset = 0
        if cursor:
            decoded = decode_cursor(cursor)
            offset = int(decoded.get("offset", 0))
        page = events[offset : offset + limit]
        next_cursor = (
            encode_cursor({"offset": offset + limit}) if offset + limit < len(events) else None
        )
        return page, next_cursor


@dataclass
class InMemoryWorkflowHandle:
    workflow_id: str
    run_id: str


@dataclass
class InMemoryTaskWorkflowAdapter:
    """Local Temporal stand-in for start/signal (LLD §2.5 TaskWorkflowPort)."""

    signals: list[dict[str, object]] = field(default_factory=list)

    async def start(self, task: Task) -> InMemoryWorkflowHandle:
        run_id = f"run-{new_uuid7()}"
        self.signals.append(
            {"type": "start", "workflow_id": task.workflow_id, "task_id": str(task.id)}
        )
        return InMemoryWorkflowHandle(workflow_id=task.workflow_id, run_id=run_id)

    async def signal_cancel(self, workflow_id: str, reason: str | None) -> None:
        self.signals.append({"type": "cancel", "workflow_id": workflow_id, "reason": reason})

    async def signal_pause(self, workflow_id: str) -> None:
        self.signals.append({"type": "pause", "workflow_id": workflow_id})

    async def signal_resume(self, workflow_id: str) -> None:
        self.signals.append({"type": "resume", "workflow_id": workflow_id})

    async def signal_approval(
        self,
        workflow_id: str,
        *,
        approval_id: UUID,
        decision: str,
    ) -> None:
        self.signals.append(
            {
                "type": "approval",
                "workflow_id": workflow_id,
                "approval_id": str(approval_id),
                "decision": decision,
            }
        )


class AllowAllPolicyAdapter:
    """Stub until policy-service is wired; returns active policy version."""

    def __init__(self, policy_version: str) -> None:
        self._policy_version = policy_version

    async def assert_can_create_task(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        repository_id: UUID,
    ) -> str:
        _ = (tenant_id, subject_id, repository_id)
        return self._policy_version
