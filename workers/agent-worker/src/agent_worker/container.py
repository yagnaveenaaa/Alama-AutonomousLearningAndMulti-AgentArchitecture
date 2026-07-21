from __future__ import annotations

from dataclasses import dataclass, field

from agent_worker.activities.execute import ExecuteStepActivity
from agent_worker.activities.plan import PlanActivity
from agent_worker.activities.verify import VerifyActivity
from agent_worker.adapters.gateways import (
    DeterministicModelGateway,
    DeterministicToolGateway,
    InMemoryRetrievalAdapter,
    InMemoryTaskProjection,
)
from agent_worker.agents.coder import CoderAgent
from agent_worker.agents.planner import PlannerAgent, PlanValidator
from agent_worker.agents.reviewer import ReviewerAgent
from agent_worker.agents.security import SecurityAgent
from agent_worker.agents.tester import TesterAgent
from agent_worker.application.context_builder import ContextBuilder
from agent_worker.config import AgentWorkerSettings
from agent_worker.protocols.bus import AgentMessageBus
from agent_worker.workflows.agent_workflow import AgentWorkflow, AgentWorkflowInput
from agent_worker.workflows.runtime import LocalWorkflowRuntime


@dataclass
class AgentWorkerContainer:
    settings: AgentWorkerSettings
    bus: AgentMessageBus
    model: DeterministicModelGateway
    tools: DeterministicToolGateway
    retrieval: InMemoryRetrievalAdapter
    projections: InMemoryTaskProjection
    workflow: AgentWorkflow
    runtime: LocalWorkflowRuntime
    jobs: list[AgentWorkflowInput] = field(default_factory=list)


def build_container(
    settings: AgentWorkerSettings | None = None,
    *,
    fail_tests: bool = False,
    reject_review: bool = False,
    inject_secret_in_patch: bool = False,
) -> AgentWorkerContainer:
    settings = settings or AgentWorkerSettings()
    bus = AgentMessageBus()
    model = DeterministicModelGateway(
        reject_review=reject_review,
        inject_secret_in_patch=inject_secret_in_patch,
    )
    tools = DeterministicToolGateway(fail_tests=fail_tests)
    retrieval = InMemoryRetrievalAdapter()
    projections = InMemoryTaskProjection()
    allowed_tools = DeterministicToolGateway.ALLOWED
    planner = PlannerAgent(
        model,
        PlanValidator(max_steps=settings.max_plan_steps, allowed_tools=allowed_tools),
        template_name=settings.planner_template,
    )
    coder = CoderAgent(model, template_name=settings.coder_template)
    tester = TesterAgent(model, template_name=settings.tester_template)
    reviewer = ReviewerAgent(model, template_name=settings.reviewer_template)
    security = SecurityAgent(model, template_name=settings.security_template)
    context_builder = ContextBuilder(retrieval, bus)
    workflow = AgentWorkflow(
        PlanActivity(context_builder, planner, bus),
        ExecuteStepActivity(coder, tools, bus),
        VerifyActivity(tester, reviewer, security, bus),
        projections,
        max_reflections=settings.max_reflections,
    )
    runtime = LocalWorkflowRuntime(workflow)
    return AgentWorkerContainer(
        settings=settings,
        bus=bus,
        model=model,
        tools=tools,
        retrieval=retrieval,
        projections=projections,
        workflow=workflow,
        runtime=runtime,
    )
