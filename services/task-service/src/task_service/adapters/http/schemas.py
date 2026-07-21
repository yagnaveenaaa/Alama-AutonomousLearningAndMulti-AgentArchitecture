from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class CreateTaskRequest(BaseModel):
    repository_id: UUID
    objective: str = Field(min_length=1, max_length=20_000)
    title: str | None = Field(default=None, max_length=500)
    budget_tokens: int | None = Field(default=None, ge=0)
    budget_usd_micros: int | None = Field(default=None, ge=0)
    base_ref: str | None = Field(default=None, max_length=256)
    base_commit_sha: str | None = Field(default=None, min_length=40, max_length=40)
    priority: int = Field(default=0)


class CancelTaskRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class DecideApprovalRequest(BaseModel):
    decision: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=2000)


class TaskLinks(BaseModel):
    events_stream: str


class TaskResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    repository_id: UUID
    created_by: UUID
    title: str
    objective: str
    state: str
    workflow_id: str
    run_id: str
    base_commit_sha: str
    branch_name: str | None
    pr_url: str | None
    budget_tokens: int
    budget_usd_micros: int
    policy_version: str
    priority: int
    parent_task_id: UUID | None
    paused: bool
    created_at: datetime
    updated_at: datetime
    version: int
    links: TaskLinks | None = None


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    next_cursor: str | None


class TaskEventResponse(BaseModel):
    id: UUID
    task_id: UUID
    sequence: int
    event_type: str
    payload_ref: str | None
    payload_inline: dict[str, Any] | None
    actor_type: str
    actor_id: str
    created_at: datetime


class TaskEventListResponse(BaseModel):
    items: list[TaskEventResponse]
    next_cursor: str | None


class ApprovalResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    task_id: UUID
    gate: str
    status: str
    requested_at: datetime
    decided_at: datetime | None
    decided_by: UUID | None
    policy_version: str
    reason: str | None


class ApprovalListResponse(BaseModel):
    items: list[ApprovalResponse]
