from __future__ import annotations

from agent_worker.workflows.agent_workflow import (
    AgentWorkflow,
    AgentWorkflowInput,
    AgentWorkflowResult,
)


class LocalWorkflowRuntime:
    """In-process Temporal-class runner for local/tests (LLD §6.7).

    Production replaces this with Temporal worker registration of ``AgentWorkflow``.
    """

    def __init__(self, workflow: AgentWorkflow) -> None:
        self._workflow = workflow
        self.results: list[AgentWorkflowResult] = []

    async def start(self, inp: AgentWorkflowInput) -> AgentWorkflowResult:
        result = await self._workflow.run(inp)
        self.results.append(result)
        return result
