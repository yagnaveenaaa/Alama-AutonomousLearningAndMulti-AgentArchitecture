from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from alama_common.auth import Principal
from alama_common.context import RequestContext, bind_request_context
from alama_common.errors import AuthenticationError, NotFoundError
from alama_common.ids import new_uuid7
from alama_common.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from fastapi import APIRouter, Depends, Header, Query, Request
from sse_starlette.sse import EventSourceResponse

from task_service.adapters.http.schemas import (
    ApprovalListResponse,
    ApprovalResponse,
    CancelTaskRequest,
    CreateTaskRequest,
    DecideApprovalRequest,
    HealthResponse,
    TaskEventListResponse,
    TaskEventResponse,
    TaskLinks,
    TaskListResponse,
    TaskResponse,
)
from task_service.application.dto import (
    CancelTaskCommand,
    CreateTaskCommand,
    DecideApprovalCommand,
    PauseResumeCommand,
)
from task_service.container import TaskContainer
from task_service.domain.models import Approval, Task, TaskEvent, TaskState

router = APIRouter()


def get_container(request: Request) -> TaskContainer:
    return request.app.state.container  # type: ignore[no-any-return]


async def get_principal(
    request: Request,
    x_subject_id: str | None = Header(default=None, alias="X-Subject-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> Principal:
    if x_subject_id is None or x_tenant_id is None:
        raise AuthenticationError("Missing identity headers")
    try:
        subject_id = UUID(x_subject_id)
        tenant_id = UUID(x_tenant_id)
    except ValueError as exc:
        raise AuthenticationError("Invalid identity headers") from exc

    principal = Principal(
        subject_id=subject_id,
        tenant_ids=(tenant_id,),
        scopes=frozenset({"tasks:read", "tasks:write"}),
    )
    bind_request_context(
        RequestContext(
            request_id=new_uuid7(),
            tenant_id=tenant_id,
            principal=principal,
            trace_id=request.headers.get("traceparent"),
        )
    )
    return principal


def _task_response(task: Task, *, include_links: bool = False) -> TaskResponse:
    links = None
    if include_links:
        links = TaskLinks(events_stream=f"/v1/tasks/{task.id}/events/stream")
    return TaskResponse(
        id=task.id,
        tenant_id=task.tenant_id,
        repository_id=task.repository_id,
        created_by=task.created_by,
        title=task.title,
        objective=task.objective,
        state=task.state.value,
        workflow_id=task.workflow_id,
        run_id=task.run_id,
        base_commit_sha=task.base_commit_sha,
        branch_name=task.branch_name,
        pr_url=task.pr_url,
        budget_tokens=task.budget_tokens,
        budget_usd_micros=task.budget_usd_micros,
        policy_version=task.policy_version,
        priority=task.priority,
        parent_task_id=task.parent_task_id,
        paused=task.paused,
        created_at=task.created_at,
        updated_at=task.updated_at,
        version=task.version,
        links=links,
    )


def _event_response(event: TaskEvent) -> TaskEventResponse:
    return TaskEventResponse(
        id=event.id,
        task_id=event.task_id,
        sequence=event.sequence,
        event_type=event.event_type,
        payload_ref=event.payload_ref,
        payload_inline=event.payload_inline,
        actor_type=event.actor_type.value,
        actor_id=event.actor_id,
        created_at=event.created_at,
    )


def _approval_response(approval: Approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        tenant_id=approval.tenant_id,
        task_id=approval.task_id,
        gate=approval.gate,
        status=approval.status.value,
        requested_at=approval.requested_at,
        decided_at=approval.decided_at,
        decided_by=approval.decided_by,
        policy_version=approval.policy_version,
        reason=approval.reason,
    )


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="task-service")


@router.post("/v1/tasks", response_model=TaskResponse, status_code=201, tags=["tasks"])
async def create_task(
    body: CreateTaskRequest,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
) -> TaskResponse:
    tenant_id = principal.primary_tenant_id()
    task = await container.create_task.handle(
        CreateTaskCommand(
            tenant_id=tenant_id,
            subject_id=principal.subject_id,
            repository_id=body.repository_id,
            objective=body.objective,
            title=body.title,
            budget_tokens=body.budget_tokens,
            budget_usd_micros=body.budget_usd_micros,
            base_commit_sha=body.base_commit_sha,
            priority=body.priority,
        )
    )
    return _task_response(task, include_links=True)


@router.get("/v1/tasks", response_model=TaskListResponse, tags=["tasks"])
async def list_tasks(
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
    repository_id: UUID | None = Query(default=None),
    state: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
) -> TaskListResponse:
    task_state = TaskState(state) if state else None
    items, next_cursor = await container.tasks.list_for_tenant(
        principal.primary_tenant_id(),
        repository_id=repository_id,
        state=task_state,
        limit=limit,
        cursor=cursor,
    )
    return TaskListResponse(
        items=[_task_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/v1/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
async def get_task(
    task_id: UUID,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
) -> TaskResponse:
    task = await container.tasks.get_by_id(task_id)
    if task is None or task.tenant_id != principal.primary_tenant_id():
        raise NotFoundError("Task not found")
    return _task_response(task, include_links=True)


@router.post("/v1/tasks/{task_id}/cancel", response_model=TaskResponse, tags=["tasks"])
async def cancel_task(
    task_id: UUID,
    body: CancelTaskRequest,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
) -> TaskResponse:
    task = await container.lifecycle.cancel(
        CancelTaskCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            task_id=task_id,
            reason=body.reason,
        )
    )
    return _task_response(task)


@router.post("/v1/tasks/{task_id}/pause", response_model=TaskResponse, tags=["tasks"])
async def pause_task(
    task_id: UUID,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
) -> TaskResponse:
    task = await container.lifecycle.pause(
        PauseResumeCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            task_id=task_id,
        )
    )
    return _task_response(task)


@router.post("/v1/tasks/{task_id}/resume", response_model=TaskResponse, tags=["tasks"])
async def resume_task(
    task_id: UUID,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
) -> TaskResponse:
    task = await container.lifecycle.resume(
        PauseResumeCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            task_id=task_id,
        )
    )
    return _task_response(task)


@router.get(
    "/v1/tasks/{task_id}/events",
    response_model=TaskEventListResponse,
    tags=["events"],
)
async def list_events(
    task_id: UUID,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
    from_seq: int | None = Query(default=None, ge=1),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
) -> TaskEventListResponse:
    task = await container.tasks.get_by_id(task_id)
    if task is None or task.tenant_id != principal.primary_tenant_id():
        raise NotFoundError("Task not found")
    items, next_cursor = await container.events.list_for_task(
        task_id,
        from_seq=from_seq,
        limit=limit,
        cursor=cursor,
    )
    return TaskEventListResponse(
        items=[_event_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/v1/tasks/{task_id}/events/stream", tags=["events"])
async def stream_events(
    task_id: UUID,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
    from_seq: int = Query(default=1, ge=1),
) -> EventSourceResponse:
    task = await container.tasks.get_by_id(task_id)
    if task is None or task.tenant_id != principal.primary_tenant_id():
        raise NotFoundError("Task not found")

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        cursor_seq = from_seq
        idle_rounds = 0
        while idle_rounds < 30:
            items, _ = await container.events.list_for_task(
                task_id,
                from_seq=cursor_seq,
                limit=50,
                cursor=None,
            )
            if not items:
                idle_rounds += 1
                await asyncio.sleep(0.05)
                continue
            idle_rounds = 0
            for item in items:
                cursor_seq = item.sequence + 1
                yield {
                    "event": item.event_type,
                    "id": str(item.sequence),
                    "data": json.dumps(
                        {
                            "id": str(item.id),
                            "sequence": item.sequence,
                            "event_type": item.event_type,
                            "payload_inline": item.payload_inline,
                            "actor_type": item.actor_type.value,
                            "actor_id": item.actor_id,
                        }
                    ),
                }
            current = await container.tasks.get_by_id(task_id)
            if current is not None and current.is_terminal:
                break

    return EventSourceResponse(event_generator())


@router.get(
    "/v1/tasks/{task_id}/approvals",
    response_model=ApprovalListResponse,
    tags=["approvals"],
)
async def list_approvals(
    task_id: UUID,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
) -> ApprovalListResponse:
    task = await container.tasks.get_by_id(task_id)
    if task is None or task.tenant_id != principal.primary_tenant_id():
        raise NotFoundError("Task not found")
    items = await container.approvals.list_for_task(task_id)
    return ApprovalListResponse(items=[_approval_response(item) for item in items])


@router.post(
    "/v1/approvals/{approval_id}/decide",
    response_model=ApprovalResponse,
    tags=["approvals"],
)
async def decide_approval(
    approval_id: UUID,
    body: DecideApprovalRequest,
    principal: Principal = Depends(get_principal),
    container: TaskContainer = Depends(get_container),
) -> ApprovalResponse:
    approval = await container.approval_service.decide(
        DecideApprovalCommand(
            tenant_id=principal.primary_tenant_id(),
            subject_id=principal.subject_id,
            approval_id=approval_id,
            decision=body.decision,
            reason=body.reason,
        )
    )
    return _approval_response(approval)
