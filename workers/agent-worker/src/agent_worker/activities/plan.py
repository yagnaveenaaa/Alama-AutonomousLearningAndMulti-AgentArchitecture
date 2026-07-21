from __future__ import annotations

from typing import Any
from uuid import UUID

from agent_worker.agents.planner import PlannerAgent
from agent_worker.application.context_builder import ContextBuilder
from agent_worker.protocols.artifacts import (
    AgentRole,
    ArtifactEnvelope,
    ArtifactType,
    Plan,
    WorkingMemory,
)
from agent_worker.protocols.bus import AgentMessageBus


class PlanActivity:
    """Call Planner agent after context build (LLD §2.15)."""

    def __init__(
        self,
        context_builder: ContextBuilder,
        planner: PlannerAgent,
        bus: AgentMessageBus,
    ) -> None:
        self._context_builder = context_builder
        self._planner = planner
        self._bus = bus

    async def run(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        objective: str,
        policy_constraints: dict[str, Any] | None = None,
    ) -> tuple[WorkingMemory, Plan]:
        memory, pack = await self._context_builder.build(
            tenant_id=tenant_id,
            task_id=task_id,
            repository_id=repository_id,
            commit_sha=commit_sha,
            objective=objective,
        )
        plan = await self._planner.draft_plan(
            objective=objective,
            retrieval_pack=pack,
            policy_constraints=policy_constraints or {},
        )
        envelope = ArtifactEnvelope.create(
            artifact_type=ArtifactType.PLAN,
            task_id=task_id,
            producer_role=AgentRole.PLANNER,
            payload=plan.to_payload(),
        )
        self._bus.publish(envelope)
        memory.plan = plan
        memory.artifacts.append(envelope)
        return memory, plan
