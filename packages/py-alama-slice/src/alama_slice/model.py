from __future__ import annotations

from typing import Any
from uuid import UUID

from alama_slice.fix import FIXED_AUTH_PY


class SliceModelGateway:
    """Deterministic one-model stand-in that can fix the auth-bug fixture."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete_json(
        self,
        *,
        template_name: str,
        inputs: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {"template": template_name, "schema": schema_name, "inputs": inputs}
        )
        if schema_name == "Plan" or template_name.startswith("planner"):
            return self._plan(inputs)
        if schema_name == "CoderOutput" or template_name.startswith("coder"):
            return self._coder(inputs)
        if schema_name == "TestReport" or template_name.startswith("tester"):
            results = inputs.get("tool_results", [])
            failed = [r for r in results if not r.get("ok", True)]
            return {
                "passed": not failed,
                "tests_run": max(1, len(results)),
                "failures": [str(r.get("output", "fail"))[:500] for r in failed],
                "interpretation": "all green" if not failed else "tool failure",
                "proposed_fix_step": None if not failed else "narrow patch and retest",
            }
        if schema_name == "ReviewReport" or template_name.startswith("reviewer"):
            return {
                "approved": True,
                "findings": [],
                "policy_notes": ["slice.policy.v1"],
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

    def _plan(self, inputs: dict[str, Any]) -> dict[str, Any]:
        objective = str(inputs.get("objective", "Fix authentication bug"))
        pack = inputs.get("retrieval_pack") or {}
        evidence = pack.get("evidence") or []
        paths = [str(e.get("path")) for e in evidence if e.get("path")]
        target = paths[0] if paths else "src/auth.py"
        return {
            "objective": objective,
            "success_criteria": ["pytest passes", "empty tokens rejected"],
            "risks": ["auth regression"],
            "stop_conditions": ["tests fail twice", "approval rejected"],
            "steps": [
                {
                    "step_id": "step-1",
                    "goal": f"Implement: {objective}",
                    "files_likely": [target],
                    "tools_needed": ["get_file", "apply_patch", "run_tests"],
                    "risk": "medium",
                    "verification": "run unit tests",
                    "approval_gates": [],
                    "stop_conditions": ["tests fail twice"],
                    "depends_on": [],
                    "tags": ["test", "review", "security"],
                }
            ],
        }

    def _coder(self, inputs: dict[str, Any]) -> dict[str, Any]:
        step = inputs.get("step") or {}
        pack = inputs.get("retrieval_pack") or {}
        evidence = pack.get("evidence") or []
        path = (step.get("files_likely") or ["src/auth.py"])[0]
        buggy = any(
            "anonymous" in str(e.get("content", "")) or "missing strip" in str(e.get("content", "")).lower()
            for e in evidence
        ) or "auth" in path
        if buggy or "auth" in str(step.get("goal", "")).lower():
            content = FIXED_AUTH_PY
            return {
                "summary": f"Reject empty tokens in {path}",
                "patches": [{"path": path, "diff": content}],
                "tool_intents": [
                    {
                        "name": "get_file",
                        "args": {"path": path},
                        "reason": "read before patch",
                    },
                    {
                        "name": "apply_patch",
                        "args": {"path": path, "content": content},
                        "reason": step.get("goal", "fix auth"),
                    },
                    {
                        "name": "run_tests",
                        "args": {"selector": "unit"},
                        "reason": "verify",
                    },
                ],
            }
        # Generic no-op-safe fallback: touch a comment via full rewrite of first file.
        existing = ""
        for item in evidence:
            if item.get("path") == path:
                existing = str(item.get("content", ""))
                break
        content = existing + ("\n# alama slice touch\n" if existing else "print('ok')\n")
        return {
            "summary": f"Apply patch for {step.get('goal', '')}",
            "patches": [{"path": path, "diff": content}],
            "tool_intents": [
                {"name": "get_file", "args": {"path": path}, "reason": "read"},
                {
                    "name": "apply_patch",
                    "args": {"path": path, "content": content},
                    "reason": step.get("goal", "implement"),
                },
                {"name": "run_tests", "args": {"selector": "unit"}, "reason": "verify"},
            ],
        }


class IndexedRetrievalAdapter:
    """Retrieve from indexed lexical chunks + live workspace files."""

    def __init__(self) -> None:
        self._chunks: list[dict[str, Any]] = []
        self._files: dict[str, str] = {}

    def seed_from_index(
        self,
        *,
        files: dict[str, str],
        chunks: list[dict[str, Any]],
    ) -> None:
        self._files = dict(files)
        self._chunks = list(chunks)

    async def retrieve(
        self,
        *,
        tenant_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        query: str,
    ) -> dict[str, Any]:
        _ = (tenant_id, repository_id)
        q = query.lower()
        scored: list[tuple[int, dict[str, Any]]] = []
        for chunk in self._chunks:
            text = str(chunk.get("text", ""))
            path = str(chunk.get("path", ""))
            score = 0
            for token in q.replace("/", " ").split():
                if token and token in text.lower():
                    score += 2
                if token and token in path.lower():
                    score += 3
            if "auth" in path.lower():
                score += 5
            if score:
                scored.append(
                    (
                        score,
                        {
                            "path": path,
                            "start_line": chunk.get("start_line", 1),
                            "end_line": chunk.get("end_line", 1),
                            "content": text,
                            "symbol": chunk.get("symbol"),
                        },
                    )
                )
        if not scored:
            for path, content in self._files.items():
                if "auth" in path.lower() or any(t in content.lower() for t in q.split() if t):
                    scored.append(
                        (
                            1,
                            {
                                "path": path,
                                "start_line": 1,
                                "end_line": max(1, content.count("\n")),
                                "content": content,
                                "symbol": None,
                            },
                        )
                    )
        scored.sort(key=lambda item: item[0], reverse=True)
        evidence = [item for _, item in scored[:8]]
        return {
            "summary": f"Indexed evidence for query={query!r} ({len(evidence)} hits)",
            "commit_sha": commit_sha,
            "evidence": evidence,
            "citations": [
                {"path": e["path"], "start_line": e["start_line"], "end_line": e["end_line"]}
                for e in evidence
            ],
        }
