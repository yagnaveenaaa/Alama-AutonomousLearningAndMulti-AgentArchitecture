from __future__ import annotations

from uuid import uuid4

import pytest

from agent_worker.container import build_container
from agent_worker.main import enqueue, process_one
from agent_worker.protocols.artifacts import ArtifactType
from agent_worker.workflows.agent_workflow import AgentWorkflowInput, WorkflowStatus

COMMIT = "c" * 40


@pytest.mark.asyncio
async def test_agent_workflow_planner_coder_verifier_happy_path() -> None:
    container = build_container()
    task_id = uuid4()
    result = await container.runtime.start(
        AgentWorkflowInput(
            tenant_id=uuid4(),
            task_id=task_id,
            repository_id=uuid4(),
            commit_sha=COMMIT,
            objective="Add health check endpoint",
        )
    )
    assert result.status == WorkflowStatus.COMPLETED
    assert result.plan is not None
    assert result.memory.completed_steps == ["step-1"]
    types = [a.artifact_type for a in container.bus.history()]
    assert ArtifactType.RETRIEVAL_PACK in types
    assert ArtifactType.PLAN in types
    assert ArtifactType.DIFF_BUNDLE in types
    assert ArtifactType.TEST_REPORT in types
    assert ArtifactType.REVIEW_REPORT in types
    assert ArtifactType.SECURITY_REPORT in types
    assert ArtifactType.TOOL_CALL_INTENT in types
    assert any(i.name == "apply_patch" for i in container.tools.invocations)
    assert any(
        e["event_type"] == "com.alama.agent.completed.v1" for e in container.projections.events
    )


@pytest.mark.asyncio
async def test_agent_workflow_fails_when_tests_fail() -> None:
    container = build_container(fail_tests=True)
    result = await container.runtime.start(
        AgentWorkflowInput(
            tenant_id=uuid4(),
            task_id=uuid4(),
            repository_id=uuid4(),
            commit_sha=COMMIT,
            objective="Broken change",
        )
    )
    assert result.status == WorkflowStatus.FAILED
    assert result.decision is not None
    assert result.decision.value == "fail"


@pytest.mark.asyncio
async def test_agent_workflow_fails_when_reviewer_rejects() -> None:
    container = build_container(reject_review=True)
    result = await container.runtime.start(
        AgentWorkflowInput(
            tenant_id=uuid4(),
            task_id=uuid4(),
            repository_id=uuid4(),
            commit_sha=COMMIT,
            objective="Review rejected change",
        )
    )
    assert result.status == WorkflowStatus.FAILED
    assert result.decision is not None
    assert result.decision.value == "fail"
    assert ArtifactType.REVIEW_REPORT in [a.artifact_type for a in container.bus.history()]


@pytest.mark.asyncio
async def test_agent_workflow_fails_on_secret_in_diff() -> None:
    container = build_container(inject_secret_in_patch=True)
    result = await container.runtime.start(
        AgentWorkflowInput(
            tenant_id=uuid4(),
            task_id=uuid4(),
            repository_id=uuid4(),
            commit_sha=COMMIT,
            objective="Leak a key",
        )
    )
    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert "secret" in result.error or "API" in result.error or "generic_secret" in result.error
    assert ArtifactType.SECURITY_REPORT in [a.artifact_type for a in container.bus.history()]


@pytest.mark.asyncio
async def test_worker_queue_processes_enqueued_job() -> None:
    container = build_container()
    enqueue(
        container,
        AgentWorkflowInput(
            tenant_id=uuid4(),
            task_id=uuid4(),
            repository_id=uuid4(),
            commit_sha=COMMIT,
            objective="Queue job",
        ),
    )
    assert await process_one(container) is True
    assert container.runtime.results[-1].status == WorkflowStatus.COMPLETED
    assert await process_one(container) is False
