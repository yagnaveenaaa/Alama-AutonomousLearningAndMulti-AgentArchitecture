from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from alama_common.ids import new_uuid7
from agent_worker.activities.execute import ExecuteStepActivity
from agent_worker.activities.plan import PlanActivity
from agent_worker.activities.verify import VerifyActivity
from agent_worker.adapters.gateways import InMemoryTaskProjection
from agent_worker.agents.coder import CoderAgent
from agent_worker.agents.planner import PlannerAgent, PlanValidator
from agent_worker.agents.reviewer import ReviewerAgent
from agent_worker.agents.security import SecurityAgent
from agent_worker.agents.tester import TesterAgent
from agent_worker.application.context_builder import ContextBuilder
from agent_worker.protocols.bus import AgentMessageBus
from agent_worker.workflows.agent_workflow import (
    AgentWorkflow,
    AgentWorkflowInput,
    WorkflowStatus,
)
from agent_worker.workflows.runtime import LocalWorkflowRuntime
from indexing_worker.container import build_container as build_indexing_container
from indexing_worker.domain.models import IndexJob
from indexing_worker.main import process_one as process_index_job

from alama_slice.model import IndexedRetrievalAdapter, SliceModelGateway
from alama_slice.sandbox import LocalFilesystemSandbox
from alama_slice.store import (
    SliceApproval,
    SliceChatMessage,
    SliceStore,
    SliceTask,
    _now,
)

ALLOWED_TOOLS = frozenset(
    {
        "get_file",
        "search_code",
        "apply_patch",
        "list_dir",
        "run_tests",
        "run_command",
        "open_pr",
        "read_ci",
        "git_checkout",
    }
)


def default_fixture_dir() -> Path:
    # packages/py-alama-slice/src/alama_slice/orchestrator.py → repo root
    here = Path(__file__).resolve()
    root = here.parents[4]
    return root / "fixtures" / "auth-bug-repo"


@dataclass
class PendingSession:
    task_id: UUID
    sandbox: LocalFilesystemSandbox
    objective: str
    commit_sha: str


class VerticalSliceOrchestrator:
    """End-to-end local slice: import → index → agent → approval → PR."""

    def __init__(
        self,
        store: SliceStore | None = None,
        *,
        fixture_dir: Path | None = None,
        work_root: Path | None = None,
    ) -> None:
        self.store = store or SliceStore()
        self.store.ensure_defaults()
        self.fixture_dir = Path(fixture_dir or default_fixture_dir())
        self.work_root = work_root
        self.model = SliceModelGateway()
        self.retrieval = IndexedRetrievalAdapter()
        self.projections = InMemoryTaskProjection()

    async def send_chat(self, objective: str) -> SliceTask:
        objective = objective.strip()
        if not objective:
            raise ValueError("objective is required")

        self.store.messages.append(
            SliceChatMessage(
                id=new_uuid7(),
                role="user",
                content=objective,
                created_at=_now(),
            )
        )

        task_id = new_uuid7()
        task = SliceTask(
            id=task_id,
            title=objective[:64],
            objective=objective,
            state="planning",
            repository_id=self.store.repository_id,
            repository_name="alama/auth-bug-demo",
            created_at=_now(),
        )
        self.store.tasks[task_id] = task
        self.store.add_event(
            task_id,
            event_type="com.alama.task.created.v1",
            summary="Created from chat",
            actor_type="user",
        )
        self.store.messages.append(
            SliceChatMessage(
                id=new_uuid7(),
                role="assistant",
                content=(
                    f'Created task “{task.title}”. '
                    "Importing fixture repo, indexing, then running the agent."
                ),
                created_at=_now(),
                task_id=task_id,
            )
        )

        await self._run_until_approval(task)
        return self.store.tasks[task_id]

    async def decide_approval(
        self,
        *,
        task_id: UUID,
        approval_id: UUID,
        decision: str,
    ) -> SliceApproval:
        items = self.store.approvals.get(task_id, [])
        approval = next((a for a in items if a.id == approval_id), None)
        if approval is None:
            raise KeyError("Approval not found")
        if approval.status != "pending":
            raise ValueError("Approval not pending")
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved|rejected")

        approval.status = decision
        self.store.add_event(
            task_id,
            event_type="com.alama.task.approval_decided.v1",
            summary=f"Approval {decision}",
            actor_type="user",
            payload={"approval_id": str(approval_id), "decision": decision},
        )

        if decision == "rejected":
            self.store.set_task_state(task_id, "cancelled")
            return approval

        session: PendingSession | None = self.store.pending_sessions.get(task_id)
        if session is None:
            raise RuntimeError("No pending slice session for task")

        self.store.set_task_state(task_id, "executing")
        self.store.add_event(
            task_id,
            event_type="com.alama.agent.pr_opening.v1",
            summary="Opening local PR artifact",
        )
        from agent_worker.protocols.artifacts import ToolCallIntent

        result = await session.sandbox.invoke(
            task_id=task_id,
            intent=ToolCallIntent(
                name="open_pr",
                args={
                    "title": f"Fix: {session.objective[:72]}",
                    "body": (
                        "Vertical slice completed planner → coder → verifier.\n"
                        "Tests passed in the local sandbox."
                    ),
                },
                reason="approved open_pr",
            ),
        )
        if not result.ok:
            self.store.set_task_state(task_id, "failed")
            self.store.add_event(
                task_id,
                event_type="com.alama.agent.failed.v1",
                summary=f"PR failed: {result.output[:200]}",
            )
            raise RuntimeError(result.output)

        pr_url = result.output.strip()
        self.store.set_task_state(task_id, "completed", pr_url=pr_url)
        self.store.add_event(
            task_id,
            event_type="com.alama.agent.completed.v1",
            summary=f"PR ready: {pr_url}",
            payload={"pr_url": pr_url, "workspace": str(session.sandbox.root)},
        )
        self.store.messages.append(
            SliceChatMessage(
                id=new_uuid7(),
                role="assistant",
                content=f"Approved. Local PR artifact written — {pr_url}",
                created_at=_now(),
                task_id=task_id,
            )
        )
        self.store.pending_sessions.pop(task_id, None)
        return approval

    async def _run_until_approval(self, task: SliceTask) -> None:
        # 1) Import fixture repo into sandbox workspace
        self.store.set_task_state(task.id, "importing")
        self.store.add_event(
            task.id,
            event_type="com.alama.repository.imported.v1",
            summary=f"Imported fixture {self.fixture_dir.name}",
        )
        sandbox = LocalFilesystemSandbox.from_fixture(
            self.fixture_dir, work_root=self.work_root
        )
        task.workspace_path = str(sandbox.root)
        files = {
            path: content
            for path, content in sandbox.read_tree().items()
            if not path.startswith(".alama/")
        }

        # 2) Index
        self.store.set_task_state(task.id, "indexing")
        repo = self.store.repos[self.store.repository_id]
        repo.index_state = "indexing"
        repo.last_synced_at = datetime.now(UTC)
        self.store.add_event(
            task.id,
            event_type="com.alama.repository.snapshot.requested.v1",
            summary="Snapshot queued for indexing",
        )
        commit_sha = hashlib.sha1(  # noqa: S324 — demo commit id
            repr(sorted(files.items())).encode("utf-8")
        ).hexdigest()
        await self._index_files(
            tenant_id=self.store.tenant_id,
            repository_id=self.store.repository_id,
            commit_sha=commit_sha,
            files=files,
        )
        repo.index_state = "ready"
        self.store.add_event(
            task.id,
            event_type="com.alama.repository.index.ready.v1",
            summary="Index generation active",
            payload={"commit_sha": commit_sha, "file_count": len(files)},
        )

        # 3) Agent: plan → retrieve → code → test → verify
        self.store.set_task_state(task.id, "executing")
        runtime, projections = self._build_agent_runtime(sandbox)
        result = await runtime.start(
            AgentWorkflowInput(
                tenant_id=self.store.tenant_id,
                task_id=task.id,
                repository_id=self.store.repository_id,
                commit_sha=commit_sha,
                objective=task.objective,
                policy_constraints={"slice": "auth-bug-demo"},
            )
        )
        for event in projections.events:
            if UUID(event["task_id"]) != task.id:
                continue
            self.store.add_event(
                task.id,
                event_type=str(event["event_type"]),
                summary=self._summarize_agent_event(event),
                actor_type="agent",
                payload=dict(event.get("payload") or {}),
            )

        if result.status != WorkflowStatus.COMPLETED:
            self.store.set_task_state(task.id, "failed")
            self.store.add_event(
                task.id,
                event_type="com.alama.agent.failed.v1",
                summary=result.error or result.status.value,
            )
            self.store.messages.append(
                SliceChatMessage(
                    id=new_uuid7(),
                    role="assistant",
                    content=f"Agent failed: {result.error or result.status.value}",
                    created_at=_now(),
                    task_id=task.id,
                )
            )
            return

        # 4) Approval gate before PR
        approval = SliceApproval(
            id=new_uuid7(),
            gate="open_pr",
            status="pending",
            reason="Open local PR artifact after successful tests",
        )
        self.store.approvals[task.id] = [approval]
        self.store.pending_sessions[task.id] = PendingSession(
            task_id=task.id,
            sandbox=sandbox,
            objective=task.objective,
            commit_sha=commit_sha,
        )
        self.store.set_task_state(task.id, "awaiting_approval")
        self.store.add_event(
            task.id,
            event_type="com.alama.task.approval_requested.v1",
            summary="Gate: open_pr",
            payload={"approval_id": str(approval.id)},
        )
        self.store.messages.append(
            SliceChatMessage(
                id=new_uuid7(),
                role="assistant",
                content=(
                    "Tests passed. Approval required to open the local PR "
                    f"(workspace: {sandbox.root})."
                ),
                created_at=_now(),
                task_id=task.id,
            )
        )

    async def _index_files(
        self,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        files: dict[str, str],
    ) -> None:
        indexing = build_indexing_container()
        snapshot_id = new_uuid7()
        manifest_ref = f"snapshots/{repository_id}/{commit_sha}.json"
        indexing.snapshot_source.put_snapshot(
            manifest_ref=manifest_ref,
            repository_id=repository_id,
            commit_sha=commit_sha,
            parent_commit_sha=None,
            files=files,
        )
        await indexing.queue.enqueue(
            IndexJob(
                tenant_id=tenant_id,
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                commit_sha=commit_sha,
                manifest_ref=manifest_ref,
            )
        )
        ok = await process_index_job(indexing)
        if not ok:
            raise RuntimeError("indexing worker produced no work")

        active = await indexing.meta.get_active(repository_id)
        if active is None:
            raise RuntimeError("index generation missing")

        chunks: list[dict[str, Any]] = []
        for chunk in indexing.lexical.indexes.get(active.lexical_index_name, []):
            chunks.append(
                {
                    "path": chunk.path,
                    "text": chunk.text,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "symbol": chunk.symbol,
                }
            )
        # Always include full source files for precise coder patches.
        for path, content in files.items():
            if path.endswith(".py"):
                chunks.append(
                    {
                        "path": path,
                        "text": content,
                        "start_line": 1,
                        "end_line": max(1, content.count("\n") + 1),
                        "symbol": None,
                    }
                )
        self.retrieval.seed_from_index(files=files, chunks=chunks)

    def _build_agent_runtime(
        self, sandbox: LocalFilesystemSandbox
    ) -> tuple[LocalWorkflowRuntime, InMemoryTaskProjection]:
        bus = AgentMessageBus()
        projections = InMemoryTaskProjection()
        planner = PlannerAgent(
            self.model,
            PlanValidator(max_steps=12, allowed_tools=ALLOWED_TOOLS),
            template_name="planner.v1",
        )
        coder = CoderAgent(self.model, template_name="coder.v1")
        tester = TesterAgent(self.model, template_name="tester.v1")
        reviewer = ReviewerAgent(self.model, template_name="reviewer.v1")
        security = SecurityAgent(self.model, template_name="security.v1")
        context_builder = ContextBuilder(self.retrieval, bus)
        workflow = AgentWorkflow(
            PlanActivity(context_builder, planner, bus),
            ExecuteStepActivity(coder, sandbox, bus),
            VerifyActivity(tester, reviewer, security, bus),
            projections,
            max_reflections=3,
        )
        return LocalWorkflowRuntime(workflow), projections

    @staticmethod
    def _summarize_agent_event(event: dict[str, Any]) -> str:
        et = str(event.get("event_type", ""))
        payload = event.get("payload") or {}
        if et.endswith("workflow_started.v1"):
            return "Agent workflow started"
        if et.endswith("plan_ready.v1"):
            return f"Planner published plan steps={payload.get('steps')}"
        if et.endswith("step_completed.v1"):
            return f"Step completed: {payload.get('step_id')}"
        if et.endswith("completed.v1"):
            return "Agent verifier completed"
        if et.endswith("failed.v1"):
            return f"Agent failed: {payload}"
        return et
