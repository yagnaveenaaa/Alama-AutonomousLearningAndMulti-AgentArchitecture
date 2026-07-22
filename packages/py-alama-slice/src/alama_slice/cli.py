from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from alama_slice.orchestrator import VerticalSliceOrchestrator, default_fixture_dir


async def _run(objective: str, *, auto_approve: bool, fixture: Path | None) -> int:
    orch = VerticalSliceOrchestrator(fixture_dir=fixture)
    print(f"Fixture: {orch.fixture_dir}")
    print(f"Objective: {objective}")
    task = await orch.send_chat(objective)
    print(f"Task {task.id} state={task.state}")
    for event in orch.store.events.get(task.id, []):
        print(f"  [{event.sequence}] {event.event_type}: {event.summary}")

    if task.state == "failed":
        return 1

    approvals = orch.store.approvals.get(task.id, [])
    if not approvals:
        print("No approval gate — unexpected for this slice.")
        return 1

    approval = approvals[0]
    if not auto_approve:
        answer = input(f"Approve open_pr ({approval.id})? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            await orch.decide_approval(
                task_id=task.id, approval_id=approval.id, decision="rejected"
            )
            print("Rejected.")
            return 2
    updated = await orch.decide_approval(
        task_id=task.id, approval_id=approval.id, decision="approved"
    )
    task = orch.store.tasks[task.id]
    print(f"Approval={updated.status} task={task.state} pr={task.pr_url}")
    if task.workspace_path:
        print(f"Workspace: {task.workspace_path}")
        pr_md = Path(task.workspace_path) / ".alama" / "PR.md"
        if pr_md.exists():
            print(f"PR markdown: {pr_md}")
    return 0 if task.state == "completed" else 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Alama vertical slice demo")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run"],
        help="Command to execute",
    )
    parser.add_argument(
        "--objective",
        default="Fix authentication bug",
        help="User objective",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Approve the open_pr gate without prompting",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help=f"Fixture repo path (default: {default_fixture_dir()})",
    )
    args = parser.parse_args(argv)
    code = asyncio.run(
        _run(args.objective, auto_approve=args.auto_approve, fixture=args.fixture)
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main(sys.argv[1:])
