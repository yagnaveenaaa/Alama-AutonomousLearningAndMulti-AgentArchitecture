from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from alama_common.ids import new_uuid7

from agent_worker.protocols.artifacts import ToolCallIntent, ToolResult


@dataclass
class SandboxResult:
    ok: bool
    output: str
    exit_code: int = 0


@dataclass
class LocalFilesystemSandbox:
    """Real workspace sandbox for the vertical slice (no microVM)."""

    root: Path
    calls: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_fixture(cls, fixture_dir: Path, *, work_root: Path | None = None) -> LocalFilesystemSandbox:
        base = Path(work_root or tempfile.mkdtemp(prefix="alama-slice-"))
        workspace = base / "workspace"
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(fixture_dir, workspace, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".pytest_cache", "*.egg-info", ".alama"
        ))
        (workspace / ".alama").mkdir(exist_ok=True)
        return cls(root=workspace)

    def read_tree(self) -> dict[str, str]:
        files: dict[str, str] = {}
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            if any(part.startswith(".") and part not in {".alama"} for part in path.parts):
                if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                    continue
            if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                continue
            try:
                files[rel] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
        return files

    async def invoke(self, *, task_id: UUID, intent: ToolCallIntent) -> ToolResult:
        self.calls.append({"task_id": str(task_id), "name": intent.name, "args": intent.args})
        try:
            result = self._dispatch(intent.name, intent.args)
            return ToolResult(
                name=intent.name,
                ok=result.ok,
                output=result.output[:8000],
                receipt_id=new_uuid7(),
            )
        except Exception as exc:  # noqa: BLE001 — surface tool failures to agent
            return ToolResult(
                name=intent.name,
                ok=False,
                output=str(exc),
                receipt_id=new_uuid7(),
            )

    def _dispatch(self, tool: str, args: dict[str, Any]) -> SandboxResult:
        if tool == "get_file":
            path = self._resolve(str(args["path"]))
            return SandboxResult(ok=True, output=path.read_text(encoding="utf-8"))
        if tool == "list_dir":
            path = self._resolve(str(args.get("path", ".")))
            if not path.exists():
                return SandboxResult(ok=False, output=f"missing: {path}", exit_code=1)
            entries = sorted(p.name for p in path.iterdir())
            return SandboxResult(ok=True, output="\n".join(entries))
        if tool == "search_code":
            query = str(args["query"]).lower()
            hits: list[str] = []
            for rel, content in self.read_tree().items():
                if query in content.lower() or query in rel.lower():
                    first = content.splitlines()[0] if content.splitlines() else ""
                    hits.append(f"{rel}: {first}")
            return SandboxResult(ok=True, output="\n".join(hits) if hits else "no matches")
        if tool == "apply_patch":
            path = self._resolve(str(args["path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            if "content" in args:
                path.write_text(str(args["content"]), encoding="utf-8")
            else:
                # Treat diff body as full replacement when no unified header.
                body = str(args.get("diff", ""))
                if body.lstrip().startswith(("---", "diff ")):
                    path.write_text(self._apply_unified(path, body), encoding="utf-8")
                else:
                    cleaned = "\n".join(
                        line[1:] if line.startswith("+") else line
                        for line in body.splitlines()
                        if not line.startswith("-")
                    )
                    if cleaned.strip():
                        path.write_text(cleaned + ("\n" if not cleaned.endswith("\n") else ""), encoding="utf-8")
                    else:
                        return SandboxResult(ok=False, output="empty patch", exit_code=1)
            return SandboxResult(ok=True, output=f"patched {args['path']}")
        if tool == "run_tests":
            return self._run_pytest()
        if tool == "open_pr":
            return self._open_pr(
                title=str(args.get("title", "Alama change")),
                body=str(args.get("body", "")),
            )
        if tool == "run_command":
            command = str(args["command"]).strip().split()
            if not command or command[0] not in {"pytest", "python", "ruff", "mypy"}:
                return SandboxResult(ok=False, output="command not allowlisted", exit_code=2)
            proc = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            return SandboxResult(ok=proc.returncode == 0, output=output, exit_code=proc.returncode)
        return SandboxResult(ok=False, output=f"unsupported tool: {tool}", exit_code=2)

    def _run_pytest(self) -> SandboxResult:
        proc = subprocess.run(
            ["python", "-m", "pytest"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return SandboxResult(ok=proc.returncode == 0, output=output or "pytest finished", exit_code=proc.returncode)

    def _open_pr(self, *, title: str, body: str) -> SandboxResult:
        alama = self.root / ".alama"
        alama.mkdir(exist_ok=True)
        patch = self._git_style_diff()
        (alama / "change.patch").write_text(patch, encoding="utf-8")
        pr_md = (
            f"# {title}\n\n"
            f"Opened by Alama vertical slice at {datetime.now(UTC).isoformat()}\n\n"
            f"{body or 'Automated fix from planner → coder → verifier.'}\n\n"
            f"## Patch\n\n```diff\n{patch}\n```\n"
        )
        (alama / "PR.md").write_text(pr_md, encoding="utf-8")
        pr_url = f"pr://local/{self.root.name}/{title.replace(' ', '-').lower()}"
        (alama / "pr_url.txt").write_text(pr_url + "\n", encoding="utf-8")
        return SandboxResult(ok=True, output=pr_url)

    def _git_style_diff(self) -> str:
        # Prefer auth.py content as the meaningful demo diff.
        auth = self.root / "src" / "auth.py"
        if auth.exists():
            content = auth.read_text(encoding="utf-8")
            lines = "".join(f"+{line}\n" for line in content.splitlines())
            return f"--- a/src/auth.py\n+++ b/src/auth.py\n{lines}"
        return "# no diff"

    def _resolve(self, rel: str) -> Path:
        normalized = rel.replace("\\", "/").lstrip("./")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise PermissionError("path escape denied")
        return self.root / normalized

    @staticmethod
    def _apply_unified(path: Path, body: str) -> str:
        # Minimal fallback: keep existing file if we cannot parse.
        if path.exists():
            return path.read_text(encoding="utf-8")
        return body
