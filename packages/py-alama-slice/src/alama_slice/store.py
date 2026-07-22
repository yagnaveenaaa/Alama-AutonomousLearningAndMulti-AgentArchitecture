from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from alama_common.ids import new_uuid7


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class SliceTask:
    id: UUID
    title: str
    objective: str
    state: str
    repository_id: UUID
    repository_name: str
    created_at: datetime
    paused: bool = False
    pr_url: str | None = None
    workspace_path: str | None = None


@dataclass
class SliceEvent:
    id: UUID
    sequence: int
    event_type: str
    actor_type: str
    summary: str
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SliceApproval:
    id: UUID
    gate: str
    status: str
    reason: str | None = None


@dataclass
class SliceRepo:
    id: UUID
    full_name: str
    index_state: str
    last_synced_at: datetime


@dataclass
class SliceChatMessage:
    id: UUID
    role: str
    content: str
    created_at: datetime
    task_id: UUID | None = None


@dataclass
class SliceStore:
    """In-process projection store backing the vertical-slice BFF/UI."""

    tenant_id: UUID = field(default_factory=new_uuid7)
    subject_id: UUID = field(default_factory=new_uuid7)
    repository_id: UUID = field(default_factory=new_uuid7)
    repos: dict[UUID, SliceRepo] = field(default_factory=dict)
    tasks: dict[UUID, SliceTask] = field(default_factory=dict)
    events: dict[UUID, list[SliceEvent]] = field(default_factory=dict)
    approvals: dict[UUID, list[SliceApproval]] = field(default_factory=dict)
    messages: list[SliceChatMessage] = field(default_factory=list)
    pending_sessions: dict[UUID, Any] = field(default_factory=dict)

    def ensure_defaults(self) -> None:
        if self.repository_id not in self.repos:
            self.repos[self.repository_id] = SliceRepo(
                id=self.repository_id,
                full_name="alama/auth-bug-demo",
                index_state="idle",
                last_synced_at=_now(),
            )
        if not self.messages:
            self.messages.append(
                SliceChatMessage(
                    id=new_uuid7(),
                    role="assistant",
                    content=(
                        "Vertical slice ready. Try: “Fix authentication bug” "
                        "against the fixture Python repo."
                    ),
                    created_at=_now(),
                )
            )

    def add_event(
        self,
        task_id: UUID,
        *,
        event_type: str,
        summary: str,
        actor_type: str = "system",
        payload: dict[str, Any] | None = None,
    ) -> SliceEvent:
        seq = len(self.events.get(task_id, [])) + 1
        event = SliceEvent(
            id=new_uuid7(),
            sequence=seq,
            event_type=event_type,
            actor_type=actor_type,
            summary=summary,
            created_at=_now(),
            payload=payload or {},
        )
        self.events.setdefault(task_id, []).append(event)
        return event

    def set_task_state(self, task_id: UUID, state: str, *, pr_url: str | None = None) -> None:
        task = self.tasks[task_id]
        task.state = state
        if pr_url is not None:
            task.pr_url = pr_url
