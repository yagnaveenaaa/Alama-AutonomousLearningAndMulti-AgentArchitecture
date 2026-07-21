from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from agent_worker.activities.execute import ExecuteStepActivity
from agent_worker.activities.plan import PlanActivity
from agent_worker.activities.verify import VerifyActivity
from agent_worker.domain.ports import TaskProjectionPort
from agent_worker.protocols.artifacts import (
    ArtifactType,
    Plan,
    PlanStep,
    VerifierDecision,
    WorkingMemory,
)


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentWorkflowInput:
    tenant_id: UUID
    task_id: UUID
    repository_id: UUID
    commit_sha: str
    objective: str
    policy_constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentWorkflowResult:
    status: WorkflowStatus
    memory: WorkingMemory
    plan: Plan | None
    decision: VerifierDecision | None
    error: str | None = None


class AgentWorkflow:
    """Durable Planner→Executor→Verifier control loop (LLD §2.15 / §6.3).

    Hardening slice: Planner + Coder + Tester + Reviewer + Security.
    Temporal SDK wiring is behind ``LocalWorkflowRuntime``; production hosts
    this definition on Temporal.
    """

    def __init__(
        self,
        plan_activity: PlanActivity,
        execute_activity: ExecuteStepActivity,
        verify_activity: VerifyActivity,
        projections: TaskProjectionPort,
        *,
        max_reflections: int = 5,
    ) -> None:
        self._plan = plan_activity
        self._execute = execute_activity
        self._verify = verify_activity
        self._projections = projections
        self._max_reflections = max_reflections
        self._cancelled = False
        self._paused = False

    def signal_cancel(self) -> None:
        self._cancelled = True

    def signal_pause(self) -> None:
        self._paused = True

    def signal_resume(self) -> None:
        self._paused = False

    async def run(self, inp: AgentWorkflowInput) -> AgentWorkflowResult:
        await self._projections.project_event(
            task_id=inp.task_id,
            event_type="com.alama.agent.workflow_started.v1",
            payload={"objective": inp.objective},
        )
        memory, plan = await self._plan.run(
            tenant_id=inp.tenant_id,
            task_id=inp.task_id,
            repository_id=inp.repository_id,
            commit_sha=inp.commit_sha,
            objective=inp.objective,
            policy_constraints=inp.policy_constraints,
        )
        await self._projections.project_event(
            task_id=inp.task_id,
            event_type="com.alama.agent.plan_ready.v1",
            payload={"steps": [s.step_id for s in plan.steps]},
        )

        retrieval = memory.latest(ArtifactType.RETRIEVAL_PACK)
        retrieval_pack = retrieval.payload if retrieval else {}
        prior_failures: list[str] = []
        ready = self._ready_steps(plan.steps, set(memory.completed_steps))

        while ready:
            if self._cancelled:
                return AgentWorkflowResult(
                    status=WorkflowStatus.CANCELLED,
                    memory=memory,
                    plan=plan,
                    decision=None,
                    error="cancelled",
                )
            if self._paused:
                return AgentWorkflowResult(
                    status=WorkflowStatus.AWAITING_APPROVAL,
                    memory=memory,
                    plan=plan,
                    decision=VerifierDecision.APPROVE_WAIT,
                    error="paused",
                )

            step = ready[0]
            diff, step_result, tool_results = await self._execute.run(
                task_id=inp.task_id,
                step=step,
                retrieval_pack=retrieval_pack,
                prior_failures=prior_failures,
            )
            remaining = len(plan.steps) - len(memory.completed_steps) - 1
            outcome = await self._verify.run(
                task_id=inp.task_id,
                step=step,
                diff=diff,
                tool_results=tool_results,
                remaining_steps=remaining,
                objective=inp.objective,
                policy_constraints=inp.policy_constraints,
            )
            decision = outcome.decision

            if decision == VerifierDecision.APPROVE_WAIT:
                await self._projections.project_event(
                    task_id=inp.task_id,
                    event_type="com.alama.agent.approval_required.v1",
                    payload={"step_id": step.step_id, "gates": list(step.approval_gates)},
                )
                return AgentWorkflowResult(
                    status=WorkflowStatus.AWAITING_APPROVAL,
                    memory=memory,
                    plan=plan,
                    decision=decision,
                )

            if decision == VerifierDecision.FAIL or step_result.status == "failed":
                memory.reflections += 1
                failures = list(outcome.failure_messages) or ["verify_failed"]
                prior_failures.extend(failures)
                if memory.reflections > self._max_reflections:
                    await self._projections.project_event(
                        task_id=inp.task_id,
                        event_type="com.alama.agent.failed.v1",
                        payload={"reason": "max_reflections"},
                    )
                    return AgentWorkflowResult(
                        status=WorkflowStatus.FAILED,
                        memory=memory,
                        plan=plan,
                        decision=VerifierDecision.FAIL,
                        error="max_reflections",
                    )
                await self._projections.project_event(
                    task_id=inp.task_id,
                    event_type="com.alama.agent.step_failed.v1",
                    payload={
                        "step_id": step.step_id,
                        "failures": failures,
                    },
                )
                return AgentWorkflowResult(
                    status=WorkflowStatus.FAILED,
                    memory=memory,
                    plan=plan,
                    decision=VerifierDecision.FAIL,
                    error=failures[0],
                )

            memory.completed_steps.append(step.step_id)
            await self._projections.project_event(
                task_id=inp.task_id,
                event_type="com.alama.agent.step_completed.v1",
                payload={"step_id": step.step_id},
            )

            if decision == VerifierDecision.COMPLETE:
                await self._projections.project_event(
                    task_id=inp.task_id,
                    event_type="com.alama.agent.completed.v1",
                    payload={"completed_steps": list(memory.completed_steps)},
                )
                return AgentWorkflowResult(
                    status=WorkflowStatus.COMPLETED,
                    memory=memory,
                    plan=plan,
                    decision=decision,
                )

            ready = self._ready_steps(plan.steps, set(memory.completed_steps))

        await self._projections.project_event(
            task_id=inp.task_id,
            event_type="com.alama.agent.completed.v1",
            payload={"completed_steps": list(memory.completed_steps)},
        )
        return AgentWorkflowResult(
            status=WorkflowStatus.COMPLETED,
            memory=memory,
            plan=plan,
            decision=VerifierDecision.COMPLETE,
        )

    @staticmethod
    def _ready_steps(steps: tuple[PlanStep, ...], completed: set[str]) -> list[PlanStep]:
        ready: list[PlanStep] = []
        for step in steps:
            if step.step_id in completed:
                continue
            if all(dep in completed for dep in step.depends_on):
                ready.append(step)
        return ready
