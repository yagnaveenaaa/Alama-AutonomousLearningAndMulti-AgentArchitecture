from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from task_service.application.dto import CreateTaskCommand, DecideApprovalCommand
from task_service.domain.models import TaskState
from task_service.main import create_app

COMMIT = "a" * 40


def _headers(tenant_id: object, subject_id: object) -> dict[str, str]:
    return {
        "X-Tenant-Id": str(tenant_id),
        "X-Subject-Id": str(subject_id),
    }


@pytest.mark.asyncio
async def test_create_task_starts_workflow_and_projects_events() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        container = app.state.container
        tenant_id = uuid4()
        subject_id = uuid4()
        repository_id = uuid4()
        task = await container.create_task.handle(
            CreateTaskCommand(
                tenant_id=tenant_id,
                subject_id=subject_id,
                repository_id=repository_id,
                objective="Add JWT verification helper",
                title="JWT helper",
                base_commit_sha=COMMIT,
            )
        )
        assert task.state == TaskState.PLANNING
        assert task.run_id
        assert any(s["type"] == "start" for s in container.workflows.signals)
        events, _ = await container.events.list_for_task(
            task.id, from_seq=None, limit=10, cursor=None
        )
        assert [e.event_type for e in events] == [
            "com.alama.task.created.v1",
            "com.alama.task.workflow_started.v1",
        ]
        assert container.store.outbox.events


@pytest.mark.asyncio
async def test_budget_zero_is_rejected() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        from alama_common.errors import BudgetExceededError

        with pytest.raises(BudgetExceededError):
            await app.state.container.create_task.handle(
                CreateTaskCommand(
                    tenant_id=uuid4(),
                    subject_id=uuid4(),
                    repository_id=uuid4(),
                    objective="x",
                    budget_tokens=0,
                    base_commit_sha=COMMIT,
                )
            )


@pytest.mark.asyncio
async def test_cancel_pause_resume_and_approval_flow() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        container = app.state.container
        tenant_id = uuid4()
        subject_id = uuid4()
        task = await container.create_task.handle(
            CreateTaskCommand(
                tenant_id=tenant_id,
                subject_id=subject_id,
                repository_id=uuid4(),
                objective="Ship feature",
                base_commit_sha=COMMIT,
            )
        )
        from task_service.application.dto import CancelTaskCommand, PauseResumeCommand

        paused = await container.lifecycle.pause(
            PauseResumeCommand(
                tenant_id=tenant_id, subject_id=subject_id, task_id=task.id
            )
        )
        assert paused.paused is True
        resumed = await container.lifecycle.resume(
            PauseResumeCommand(
                tenant_id=tenant_id, subject_id=subject_id, task_id=task.id
            )
        )
        assert resumed.paused is False

        # Drive state machine to verifying so approval gate is legal.
        task.transition_to(TaskState.EXECUTING)
        task.transition_to(TaskState.VERIFYING)
        await container.tasks.save(task)

        approval = await container.approval_service.request_gate(
            tenant_id=tenant_id,
            task_id=task.id,
            gate="protected_branch_write",
            policy_version="policy.v1",
        )
        refreshed = await container.tasks.get_by_id(task.id)
        assert refreshed is not None
        assert refreshed.state == TaskState.AWAITING_APPROVAL

        decided = await container.approval_service.decide(
            DecideApprovalCommand(
                tenant_id=tenant_id,
                subject_id=subject_id,
                approval_id=approval.id,
                decision="approved",
            )
        )
        assert decided.status.value == "approved"
        after = await container.tasks.get_by_id(task.id)
        assert after is not None
        assert after.state == TaskState.EXECUTING

        cancelled = await container.lifecycle.cancel(
            CancelTaskCommand(
                tenant_id=tenant_id,
                subject_id=subject_id,
                task_id=task.id,
                reason="user abort",
            )
        )
        assert cancelled.state == TaskState.CANCELLED


def test_http_create_and_list_contract() -> None:
    app = create_app()
    tenant_id = uuid4()
    subject_id = uuid4()
    repository_id = uuid4()
    with TestClient(app) as client:
        created = client.post(
            "/v1/tasks",
            headers=_headers(tenant_id, subject_id),
            json={
                "repository_id": str(repository_id),
                "objective": "Fix flaky test",
                "base_commit_sha": COMMIT,
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["state"] == "planning"
        assert body["links"]["events_stream"].endswith("/events/stream")

        listed = client.get("/v1/tasks", headers=_headers(tenant_id, subject_id))
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        events = client.get(
            f"/v1/tasks/{body['id']}/events",
            headers=_headers(tenant_id, subject_id),
        )
        assert events.status_code == 200
        assert len(events.json()["items"]) >= 2
