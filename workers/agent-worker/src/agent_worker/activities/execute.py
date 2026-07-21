from __future__ import annotations

from uuid import UUID

from agent_worker.agents.coder import CoderAgent
from agent_worker.domain.ports import ToolGatewayPort
from agent_worker.protocols.artifacts import (
    AgentRole,
    ArtifactEnvelope,
    ArtifactType,
    DiffBundle,
    PlanStep,
    StepResult,
    ToolResult,
)
from agent_worker.protocols.bus import AgentMessageBus


class ExecuteStepActivity:
    """Call Coder/Executor via tools (LLD §2.15 / §6.5)."""

    def __init__(
        self,
        coder: CoderAgent,
        tools: ToolGatewayPort,
        bus: AgentMessageBus,
    ) -> None:
        self._coder = coder
        self._tools = tools
        self._bus = bus

    async def run(
        self,
        *,
        task_id: UUID,
        step: PlanStep,
        retrieval_pack: dict[str, object],
        prior_failures: list[str],
    ) -> tuple[DiffBundle, StepResult, list[ToolResult]]:
        diff, intents = await self._coder.execute_step(
            step=step,
            retrieval_pack=dict(retrieval_pack),
            prior_failures=prior_failures,
        )
        for intent in intents:
            self._bus.publish(
                ArtifactEnvelope.create(
                    artifact_type=ArtifactType.TOOL_CALL_INTENT,
                    task_id=task_id,
                    producer_role=AgentRole.CODER,
                    payload={
                        "name": intent.name,
                        "args": intent.args,
                        "reason": intent.reason,
                    },
                )
            )

        results: list[ToolResult] = []
        for intent in intents:
            result = await self._tools.invoke(task_id=task_id, intent=intent)
            results.append(result)
            self._bus.publish(
                ArtifactEnvelope.create(
                    artifact_type=ArtifactType.TOOL_RESULT,
                    task_id=task_id,
                    producer_role=AgentRole.SYSTEM,
                    payload={
                        "name": result.name,
                        "ok": result.ok,
                        "output": result.output[:4000],
                        "receipt_id": str(result.receipt_id) if result.receipt_id else None,
                    },
                )
            )

        status = "succeeded" if all(r.ok for r in results) else "failed"
        step_result = StepResult(
            step_id=step.step_id,
            status=status,
            summary=diff.summary,
            tool_results=tuple(results),
        )
        self._bus.publish(
            ArtifactEnvelope.create(
                artifact_type=ArtifactType.DIFF_BUNDLE,
                task_id=task_id,
                producer_role=AgentRole.CODER,
                payload={
                    "step_id": diff.step_id,
                    "summary": diff.summary,
                    "patches": list(diff.patches),
                },
            )
        )
        self._bus.publish(
            ArtifactEnvelope.create(
                artifact_type=ArtifactType.STEP_RESULT,
                task_id=task_id,
                producer_role=AgentRole.CODER,
                payload={
                    "step_id": step_result.step_id,
                    "status": step_result.status,
                    "summary": step_result.summary,
                },
            )
        )
        return diff, step_result, results
