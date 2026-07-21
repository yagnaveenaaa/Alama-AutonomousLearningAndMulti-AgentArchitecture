from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from alama_common.errors import AuthorizationError, SandboxError, ValidationError

from tool_gateway.domain.models import SandboxResult

_ALLOWED_COMMANDS = frozenset({"pytest", "ruff", "mypy", "python", "npm", "pnpm"})


class InMemorySandboxExecutor:
    """MicroVM executor stand-in with egress deny + path constraints (LLD §2.10 / §13.6)."""

    def __init__(self) -> None:
        self.workspace: dict[str, str] = {
            "src/main.py": "def main():\n    return 0\n",
            "README.md": "# demo\n",
        }
        self.calls: list[dict[str, Any]] = []

    async def exec(
        self,
        *,
        tool: str,
        args: dict[str, Any],
        paths: tuple[str, ...],
        task_id: UUID,
    ) -> SandboxResult:
        started = time.perf_counter()
        self.calls.append({"tool": tool, "args": args, "task_id": str(task_id)})
        try:
            output = self._dispatch(tool, args, paths)
            ok = True
            exit_code = 0
            error_code = None
        except (ValidationError, AuthorizationError) as exc:
            output = str(exc)
            ok = False
            exit_code = 2
            error_code = type(exc).__name__
        except SandboxError as exc:
            output = str(exc)
            ok = False
            exit_code = 1
            error_code = "sandbox_error"
        duration_ms = int((time.perf_counter() - started) * 1000)
        return SandboxResult(
            ok=ok,
            output=output,
            exit_code=exit_code,
            duration_ms=duration_ms,
            error_code=error_code,
        )

    def _dispatch(self, tool: str, args: dict[str, Any], paths: tuple[str, ...]) -> str:
        if tool == "get_file":
            path = self._authorize_path(str(args["path"]), paths)
            if path not in self.workspace:
                raise ValidationError(f"file not found: {path}")
            return self.workspace[path]
        if tool == "list_dir":
            path = self._authorize_path(str(args.get("path", ".")), paths or (".",))
            prefix = "" if path in {".", ""} else path.rstrip("/") + "/"
            entries = sorted(
                {
                    key[len(prefix) :].split("/", 1)[0]
                    for key in self.workspace
                    if key.startswith(prefix)
                }
            )
            return "\n".join(entries)
        if tool == "search_code":
            query = str(args["query"]).lower()
            hits = [
                f"{path}: {content.splitlines()[0]}"
                for path, content in self.workspace.items()
                if query in content.lower()
            ]
            return "\n".join(hits) if hits else "no matches"
        if tool == "apply_patch":
            path = self._authorize_path(str(args["path"]), paths)
            diff = str(args["diff"])
            self.workspace[path] = self.workspace.get(path, "") + "\n" + diff
            return f"patched {path}"
        if tool == "run_tests":
            selector = str(args.get("selector", "unit"))
            return f"passed: {selector}"
        if tool == "run_command":
            command = str(args["command"]).strip().split()[0]
            if command not in _ALLOWED_COMMANDS:
                raise AuthorizationError(f"command not allowlisted: {command}")
            return f"ran {command}"
        if tool == "open_pr":
            return f"pr://sandbox/{args.get('title', 'change')}"
        if tool == "read_ci":
            return "ci: success"
        if tool == "git_checkout":
            return f"checked out {args['ref']}"
        raise ValidationError(f"unsupported sandbox tool: {tool}")

    def _authorize_path(self, path: str, paths: tuple[str, ...]) -> str:
        normalized = path.replace("\\", "/").lstrip("./")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise AuthorizationError("path escape denied")
        allowed_all = "." in paths or "*" in paths
        path_ok = any(
            normalized == allowed or normalized.startswith(allowed.rstrip("/") + "/")
            for allowed in paths
        )
        if paths and not allowed_all and not path_ok:
            raise AuthorizationError("path not permitted by capability")
        return normalized
