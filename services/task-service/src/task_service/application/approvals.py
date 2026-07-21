from __future__ import annotations

from uuid import UUID

from alama_common.errors import NotFoundError

from task_service.application.dto import DecideApprovalCommand
from task_service.application.events import TaskEventProjector
from task_service.domain.models import ActorType, Approval, ApprovalStatus, TaskState
from task_service.domain.repositories import (
    ApprovalRepository,
    TaskRepository,
    TaskWorkflowPort,
)


class ApprovalService:
    """Record human decision; signal workflow (LLD §2.5)."""

    def __init__(
        self,
        approvals: ApprovalRepository,
        tasks: TaskRepository,
        workflows: TaskWorkflowPort,
        projector: TaskEventProjector,
    ) -> None:
        self._approvals = approvals
        self._tasks = tasks
        self._workflows = workflows
        self._projector = projector

    async def request_gate(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        gate: str,
        policy_version: str,
    ) -> Approval:
        task = await self._tasks.get_by_id(task_id)
        if task is None or task.tenant_id != tenant_id:
            raise NotFoundError("Task not found")
        task.transition_to(TaskState.AWAITING_APPROVAL)
        await self._tasks.save(task)
        approval = Approval.request(
            tenant_id=tenant_id,
            task_id=task_id,
            gate=gate,
            policy_version=policy_version,
        )
        await self._approvals.save(approval)
        await self._projector.project(
            tenant_id=tenant_id,
            task_id=task_id,
            event_type="com.alama.task.approval_requested.v1",
            actor_type=ActorType.SYSTEM,
            actor_id="task-service",
            payload={"approval_id": str(approval.id), "gate": gate},
        )
        return approval

    async def decide(self, command: DecideApprovalCommand) -> Approval:
        approval = await self._approvals.get_by_id(command.approval_id)
        if approval is None or approval.tenant_id != command.tenant_id:
            raise NotFoundError("Approval not found")

        task = await self._tasks.get_by_id(approval.task_id)
        if task is None:
            raise NotFoundError("Task not found")

        approval.decide(
            decision=command.decision,
            decided_by=command.subject_id,
            reason=command.reason,
        )
        await self._approvals.save(approval)
        await self._workflows.signal_approval(
            task.workflow_id,
            approval_id=approval.id,
            decision=approval.status.value,
        )

        if approval.status == ApprovalStatus.APPROVED:
            task.transition_to(TaskState.EXECUTING)
        else:
            task.cancel()
        await self._tasks.save(task)

        await self._projector.project(
            tenant_id=task.tenant_id,
            task_id=task.id,
            event_type="com.alama.task.approval_decided.v1",
            actor_type=ActorType.USER,
            actor_id=str(command.subject_id),
            payload={
                "approval_id": str(approval.id),
                "decision": approval.status.value,
                "reason": command.reason,
            },
        )
        return approval
