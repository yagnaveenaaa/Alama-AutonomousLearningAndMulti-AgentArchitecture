from __future__ import annotations

from pathlib import Path

import pytest

from alama_slice.orchestrator import VerticalSliceOrchestrator, default_fixture_dir


@pytest.fixture
def fixture_dir() -> Path:
    path = default_fixture_dir()
    assert path.exists(), f"missing fixture at {path}"
    return path


@pytest.mark.asyncio
async def test_vertical_slice_fix_auth_approve_pr(fixture_dir: Path, tmp_path: Path) -> None:
    orch = VerticalSliceOrchestrator(fixture_dir=fixture_dir, work_root=tmp_path)
    task = await orch.send_chat("Fix authentication bug")

    assert task.state == "awaiting_approval"
    events = orch.store.events[task.id]
    types = [e.event_type for e in events]
    assert "com.alama.repository.imported.v1" in types
    assert "com.alama.repository.index.ready.v1" in types
    assert "com.alama.agent.plan_ready.v1" in types
    assert "com.alama.agent.step_completed.v1" in types
    assert "com.alama.task.approval_requested.v1" in types

    approvals = orch.store.approvals[task.id]
    assert len(approvals) == 1
    assert approvals[0].gate == "open_pr"

    workspace = Path(task.workspace_path or "")
    auth_py = (workspace / "src" / "auth.py").read_text(encoding="utf-8")
    assert "missing token" in auth_py

    updated = await orch.decide_approval(
        task_id=task.id,
        approval_id=approvals[0].id,
        decision="approved",
    )
    assert updated.status == "approved"
    final = orch.store.tasks[task.id]
    assert final.state == "completed"
    assert final.pr_url and final.pr_url.startswith("pr://local/")
    assert (workspace / ".alama" / "PR.md").exists()
    assert (workspace / ".alama" / "change.patch").exists()


@pytest.mark.asyncio
async def test_vertical_slice_reject_cancels(fixture_dir: Path, tmp_path: Path) -> None:
    orch = VerticalSliceOrchestrator(fixture_dir=fixture_dir, work_root=tmp_path)
    task = await orch.send_chat("Fix authentication bug")
    approval = orch.store.approvals[task.id][0]
    await orch.decide_approval(
        task_id=task.id, approval_id=approval.id, decision="rejected"
    )
    assert orch.store.tasks[task.id].state == "cancelled"
