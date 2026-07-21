from __future__ import annotations

from dataclasses import dataclass

from task_service.adapters.persistence.memory import (
    AllowAllPolicyAdapter,
    InMemoryApprovalRepository,
    InMemoryTaskEventRepository,
    InMemoryTaskRepository,
    InMemoryTaskStore,
    InMemoryTaskWorkflowAdapter,
)
from task_service.application.approvals import ApprovalService
from task_service.application.create import CreateTaskHandler, TaskLifecycleService
from task_service.application.events import TaskEventProjector
from task_service.config import TaskSettings


@dataclass
class TaskContainer:
    store: InMemoryTaskStore
    tasks: InMemoryTaskRepository
    approvals: InMemoryApprovalRepository
    events: InMemoryTaskEventRepository
    workflows: InMemoryTaskWorkflowAdapter
    create_task: CreateTaskHandler
    lifecycle: TaskLifecycleService
    approval_service: ApprovalService
    projector: TaskEventProjector


def build_container(settings: TaskSettings | None = None) -> TaskContainer:
    settings = settings or TaskSettings()
    store = InMemoryTaskStore()
    tasks = InMemoryTaskRepository(store)
    approvals = InMemoryApprovalRepository(store)
    events = InMemoryTaskEventRepository(store)
    workflows = InMemoryTaskWorkflowAdapter()
    projector = TaskEventProjector(events)
    create_task = CreateTaskHandler(
        tasks,
        workflows,
        AllowAllPolicyAdapter(settings.policy_version),
        projector,
        store.outbox,
        default_budget_tokens=settings.default_budget_tokens,
        default_budget_usd_micros=settings.default_budget_usd_micros,
        default_policy_version=settings.policy_version,
    )
    lifecycle = TaskLifecycleService(tasks, workflows, projector)
    approval_service = ApprovalService(approvals, tasks, workflows, projector)
    return TaskContainer(
        store=store,
        tasks=tasks,
        approvals=approvals,
        events=events,
        workflows=workflows,
        create_task=create_task,
        lifecycle=lifecycle,
        approval_service=approval_service,
        projector=projector,
    )
