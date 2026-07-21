from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ConflictError, DomainInvariantError, ValidationError
from alama_common.ids import new_uuid7


class TaskState(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActorType(StrEnum):
    SYSTEM = "system"
    AGENT = "agent"
    USER = "user"


_TERMINAL = frozenset({TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED})

# Authoritative transitions (LLD §2.5)
_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset({TaskState.PLANNING, TaskState.CANCELLED, TaskState.FAILED}),
    TaskState.PLANNING: frozenset(
        {TaskState.EXECUTING, TaskState.CANCELLED, TaskState.FAILED}
    ),
    TaskState.EXECUTING: frozenset(
        {TaskState.VERIFYING, TaskState.CANCELLED, TaskState.FAILED}
    ),
    TaskState.VERIFYING: frozenset(
        {
            TaskState.EXECUTING,
            TaskState.AWAITING_APPROVAL,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        }
    ),
    TaskState.AWAITING_APPROVAL: frozenset(
        {TaskState.EXECUTING, TaskState.CANCELLED, TaskState.FAILED}
    ),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


class Task:
    """Task aggregate with authoritative state machine (LLD §2.5 TaskAggregate)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        repository_id: UUID,
        created_by: UUID,
        title: str,
        objective: str,
        state: TaskState,
        workflow_id: str,
        run_id: str,
        base_commit_sha: str,
        branch_name: str | None,
        pr_url: str | None,
        budget_tokens: int,
        budget_usd_micros: int,
        policy_version: str,
        priority: int,
        parent_task_id: UUID | None,
        paused: bool,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
    ) -> None:
        if len(base_commit_sha) != 40:
            raise DomainInvariantError("base_commit_sha must be 40 hex characters")
        if budget_tokens < 1 or budget_usd_micros < 1:
            raise DomainInvariantError("budget must be positive")
        self.id = id
        self.tenant_id = tenant_id
        self.repository_id = repository_id
        self.created_by = created_by
        self.title = title
        self.objective = objective
        self.state = state
        self.workflow_id = workflow_id
        self.run_id = run_id
        self.base_commit_sha = base_commit_sha.lower()
        self.branch_name = branch_name
        self.pr_url = pr_url
        self.budget_tokens = budget_tokens
        self.budget_usd_micros = budget_usd_micros
        self.policy_version = policy_version
        self.priority = priority
        self.parent_task_id = parent_task_id
        self.paused = paused
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        created_by: UUID,
        title: str,
        objective: str,
        base_commit_sha: str,
        budget_tokens: int,
        budget_usd_micros: int,
        policy_version: str,
        priority: int = 0,
        parent_task_id: UUID | None = None,
        workflow_id: str = "",
        run_id: str = "",
    ) -> Task:
        if not objective.strip():
            raise ValidationError("objective is required")
        resolved_title = title.strip() or objective.strip()[:80]
        now = datetime.now(UTC)
        task_id = new_uuid7()
        return cls(
            id=task_id,
            tenant_id=tenant_id,
            repository_id=repository_id,
            created_by=created_by,
            title=resolved_title,
            objective=objective.strip(),
            state=TaskState.QUEUED,
            workflow_id=workflow_id or f"task-{task_id}",
            run_id=run_id,
            base_commit_sha=base_commit_sha,
            branch_name=None,
            pr_url=None,
            budget_tokens=budget_tokens,
            budget_usd_micros=budget_usd_micros,
            policy_version=policy_version,
            priority=priority,
            parent_task_id=parent_task_id,
            paused=False,
            created_at=now,
            updated_at=now,
            version=1,
        )

    @property
    def is_terminal(self) -> bool:
        return self.state in _TERMINAL

    def transition_to(self, new_state: TaskState) -> None:
        if new_state == TaskState.CANCELLED:
            if self.is_terminal and self.state != TaskState.CANCELLED:
                raise ConflictError(f"Cannot cancel task in state {self.state.value}")
            if self.state == TaskState.CANCELLED:
                raise ConflictError("Task already cancelled")
            self._apply(new_state)
            self.paused = False
            return
        if new_state == TaskState.FAILED:
            if self.is_terminal:
                raise ConflictError(f"Cannot fail task in state {self.state.value}")
            self._apply(new_state)
            self.paused = False
            return
        allowed = _TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise ConflictError(
                f"Illegal transition {self.state.value} → {new_state.value}",
                details={"from": self.state.value, "to": new_state.value},
            )
        self._apply(new_state)

    def mark_workflow_started(self, *, run_id: str) -> None:
        self.run_id = run_id
        self.transition_to(TaskState.PLANNING)

    def pause(self) -> None:
        if self.is_terminal:
            raise ConflictError("Cannot pause a terminal task")
        if self.paused:
            raise ConflictError("Task already paused")
        self.paused = True
        self.updated_at = datetime.now(UTC)
        self.version += 1

    def resume(self) -> None:
        if self.is_terminal:
            raise ConflictError("Cannot resume a terminal task")
        if not self.paused:
            raise ConflictError("Task is not paused")
        self.paused = False
        self.updated_at = datetime.now(UTC)
        self.version += 1

    def cancel(self) -> None:
        self.transition_to(TaskState.CANCELLED)

    def _apply(self, new_state: TaskState) -> None:
        self.state = new_state
        self.updated_at = datetime.now(UTC)
        self.version += 1


class Approval:
    """Human gate decision record (LLD §4.5 approvals)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        task_id: UUID,
        gate: str,
        status: ApprovalStatus,
        requested_at: datetime,
        decided_at: datetime | None,
        decided_by: UUID | None,
        policy_version: str,
        reason: str | None,
    ) -> None:
        if not gate.strip():
            raise ValidationError("gate is required")
        self.id = id
        self.tenant_id = tenant_id
        self.task_id = task_id
        self.gate = gate
        self.status = status
        self.requested_at = requested_at
        self.decided_at = decided_at
        self.decided_by = decided_by
        self.policy_version = policy_version
        self.reason = reason

    @classmethod
    def request(
        cls,
        *,
        tenant_id: UUID,
        task_id: UUID,
        gate: str,
        policy_version: str,
    ) -> Approval:
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            task_id=task_id,
            gate=gate,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(UTC),
            decided_at=None,
            decided_by=None,
            policy_version=policy_version,
            reason=None,
        )

    def decide(
        self,
        *,
        decision: str,
        decided_by: UUID,
        reason: str | None = None,
    ) -> None:
        if self.status != ApprovalStatus.PENDING:
            raise ConflictError("Approval already decided")
        normalized = decision.strip().lower()
        if normalized == "approved":
            self.status = ApprovalStatus.APPROVED
        elif normalized == "rejected":
            self.status = ApprovalStatus.REJECTED
        else:
            raise ValidationError("decision must be 'approved' or 'rejected'")
        self.decided_by = decided_by
        self.decided_at = datetime.now(UTC)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class TaskEvent:
    """Ordered task timeline event (LLD §4.5 task_events)."""

    id: UUID
    tenant_id: UUID
    task_id: UUID
    sequence: int
    event_type: str
    payload_ref: str | None
    payload_inline: dict[str, Any] | None
    actor_type: ActorType
    actor_id: str
    created_at: datetime

    @classmethod
    def append(
        cls,
        *,
        tenant_id: UUID,
        task_id: UUID,
        sequence: int,
        event_type: str,
        actor_type: ActorType,
        actor_id: str,
        payload_inline: dict[str, Any] | None = None,
        payload_ref: str | None = None,
    ) -> TaskEvent:
        if sequence < 1:
            raise DomainInvariantError("sequence must be >= 1")
        if payload_inline is not None and payload_ref is not None:
            raise DomainInvariantError("payload_inline and payload_ref are mutually exclusive")
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            task_id=task_id,
            sequence=sequence,
            event_type=event_type,
            payload_ref=payload_ref,
            payload_inline=payload_inline,
            actor_type=actor_type,
            actor_id=actor_id,
            created_at=datetime.now(UTC),
        )
