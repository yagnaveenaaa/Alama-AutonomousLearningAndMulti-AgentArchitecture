from __future__ import annotations

from typing import Any
from uuid import UUID

from alama_common.ids import new_uuid7

from agent_worker.agents.planner import default_plan_from_objective
from agent_worker.protocols.artifacts import ToolCallIntent, ToolResult


class DeterministicModelGateway:
    """Local Model Gateway stand-in that returns schema-valid JSON (LLD §6.8)."""

    def __init__(
        self,
        *,
        reject_review: bool = False,
        inject_secret_in_patch: bool = False,
    ) -> None:
        self.reject_review = reject_review
        self.inject_secret_in_patch = inject_secret_in_patch

    async def complete_json(
        self,
        *,
        template_name: str,
        inputs: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        if schema_name == "Plan" or template_name.startswith("planner"):
            return default_plan_from_objective(str(inputs.get("objective", "")))
        if schema_name == "CoderOutput" or template_name.startswith("coder"):
            step = inputs.get("step", {})
            path = (step.get("files_likely") or ["src/main.py"])[0]
            diff_body = f"+ # {step.get('goal', '')}\n"
            if self.inject_secret_in_patch:
                diff_body += '+ API_KEY="sk-supersecrettokenvalue123"\n'
            return {
                "summary": f"Apply patch for {step.get('goal', '')}",
                "patches": [{"path": path, "diff": diff_body}],
                "tool_intents": [
                    {
                        "name": "get_file",
                        "args": {"path": path},
                        "reason": "read before patch",
                    },
                    {
                        "name": "apply_patch",
                        "args": {"path": path, "diff": diff_body},
                        "reason": step.get("goal", "implement"),
                    },
                    {
                        "name": "run_tests",
                        "args": {"selector": "unit"},
                        "reason": "verify",
                    },
                ],
            }
        if schema_name == "TestReport" or template_name.startswith("tester"):
            results = inputs.get("tool_results", [])
            failed = [r for r in results if not r.get("ok", True)]
            return {
                "passed": not failed,
                "tests_run": max(1, len(results)),
                "failures": [str(r.get("output", "fail")) for r in failed],
                "interpretation": "all green" if not failed else "tool failure",
                "proposed_fix_step": None if not failed else "retry with narrower patch",
            }
        if schema_name == "ReviewReport" or template_name.startswith("reviewer"):
            if self.reject_review:
                return {
                    "approved": False,
                    "findings": ["diff does not match objective"],
                    "policy_notes": [],
                    "summary": "changes_requested",
                }
            return {
                "approved": True,
                "findings": [],
                "policy_notes": ["policy.v1 ok"],
                "summary": "approved",
            }
        if schema_name == "SecurityReport" or template_name.startswith("security"):
            scan = inputs.get("secret_scan", [])
            return {
                "passed": not scan,
                "findings": [],
                "summary": "clean" if not scan else "secrets_in_diff",
            }
        return {}


class DeterministicToolGateway:
    """Local Tool Gateway stand-in — schema validate + sandbox stub (LLD §6.5)."""

    ALLOWED = frozenset(
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

    def __init__(self, *, fail_tests: bool = False) -> None:
        self.fail_tests = fail_tests
        self.invocations: list[ToolCallIntent] = []

    async def invoke(self, *, task_id: UUID, intent: ToolCallIntent) -> ToolResult:
        _ = task_id
        self.invocations.append(intent)
        if intent.name not in self.ALLOWED:
            return ToolResult(
                name=intent.name,
                ok=False,
                output=f"forbidden tool: {intent.name}",
                receipt_id=new_uuid7(),
            )
        if intent.name == "run_tests" and self.fail_tests:
            return ToolResult(
                name=intent.name,
                ok=False,
                output="1 failed: test_example",
                receipt_id=new_uuid7(),
            )
        return ToolResult(
            name=intent.name,
            ok=True,
            output=f"{intent.name} ok args={intent.args}",
            receipt_id=new_uuid7(),
        )


class InMemoryRetrievalAdapter:
    async def retrieve(
        self,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        query: str,
    ) -> dict[str, Any]:
        _ = (tenant_id, repository_id)
        return {
            "summary": f"repo conventions for {query}",
            "commit_sha": commit_sha,
            "evidence": [
                {
                    "path": "src/main.py",
                    "start_line": 1,
                    "end_line": 20,
                    "content": "# existing module",
                }
            ],
            "citations": [],
        }


class InMemoryTaskProjection:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def project_event(
        self,
        *,
        task_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.append(
            {"task_id": str(task_id), "event_type": event_type, "payload": payload}
        )
