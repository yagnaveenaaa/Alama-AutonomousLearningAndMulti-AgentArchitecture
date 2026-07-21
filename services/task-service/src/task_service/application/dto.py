from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    tenant_id: UUID
    subject_id: UUID
    repository_id: UUID
    objective: str
    title: str | None = None
    budget_tokens: int | None = None
    budget_usd_micros: int | None = None
    base_commit_sha: str | None = None
    priority: int = 0
    parent_task_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CancelTaskCommand:
    tenant_id: UUID
    subject_id: UUID
    task_id: UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PauseResumeCommand:
    tenant_id: UUID
    subject_id: UUID
    task_id: UUID


@dataclass(frozen=True, slots=True)
class DecideApprovalCommand:
    tenant_id: UUID
    subject_id: UUID
    approval_id: UUID
    decision: str
    reason: str | None = None
