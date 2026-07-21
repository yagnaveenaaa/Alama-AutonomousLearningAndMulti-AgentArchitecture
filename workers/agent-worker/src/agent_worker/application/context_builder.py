from __future__ import annotations

from typing import Any
from uuid import UUID

from agent_worker.domain.ports import RetrievalPort
from agent_worker.protocols.artifacts import (
    AgentRole,
    ArtifactEnvelope,
    ArtifactType,
    WorkingMemory,
)
from agent_worker.protocols.bus import AgentMessageBus


class ContextBuilder:
    """Assemble working memory + retrieval (LLD §2.15). Not an LLM role."""

    def __init__(self, retrieval: RetrievalPort, bus: AgentMessageBus) -> None:
        self._retrieval = retrieval
        self._bus = bus

    async def build(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        objective: str,
        query: str | None = None,
    ) -> tuple[WorkingMemory, dict[str, Any]]:
        pack = await self._retrieval.retrieve(
            tenant_id=tenant_id,
            repository_id=repository_id,
            commit_sha=commit_sha,
            query=query or objective,
        )
        evidence = pack.get("evidence", [])
        summary_parts = [
            f"{item.get('path', '?')}:{item.get('start_line', 0)}" for item in evidence[:8]
        ]
        summary = "; ".join(summary_parts) if summary_parts else "no evidence"
        envelope = ArtifactEnvelope.create(
            artifact_type=ArtifactType.RETRIEVAL_PACK,
            task_id=task_id,
            producer_role=AgentRole.CONTEXT_BUILDER,
            payload=pack,
        )
        self._bus.publish(envelope)
        memory = WorkingMemory(
            task_id=task_id,
            objective=objective,
            repository_id=repository_id,
            commit_sha=commit_sha,
            retrieval_summary=summary,
            artifacts=[envelope],
        )
        return memory, pack
