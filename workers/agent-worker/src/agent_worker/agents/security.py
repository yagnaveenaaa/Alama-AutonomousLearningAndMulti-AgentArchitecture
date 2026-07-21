from __future__ import annotations

import re
from typing import Any

from agent_worker.domain.ports import ModelGatewayPort
from agent_worker.protocols.artifacts import (
    DiffBundle,
    PlanStep,
    SecurityFinding,
    SecurityReport,
)

# Deterministic secret/vuln patterns (LLD §13) — model supplements, does not replace.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "generic_secret",
        re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?\S{8,}"),
    ),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
)


class SecurityAgent:
    """Security — secret/vuln/authz review of changes (LLD §6.1 / §6.8 / §13)."""

    def __init__(self, model: ModelGatewayPort, *, template_name: str) -> None:
        self._model = model
        self._template_name = template_name

    async def review(
        self,
        *,
        step: PlanStep,
        diff: DiffBundle,
        policy_constraints: dict[str, Any] | None = None,
    ) -> SecurityReport:
        scanned = self._scan_diff(diff)
        raw = await self._model.complete_json(
            template_name=self._template_name,
            inputs={
                "step_id": step.step_id,
                "goal": step.goal,
                "diff_summary": diff.summary,
                "patches": list(diff.patches),
                "secret_scan": [
                    {"severity": f.severity, "kind": f.kind, "detail": f.detail, "path": f.path}
                    for f in scanned
                ],
                "policy_constraints": policy_constraints or {},
            },
            schema_name="SecurityReport",
        )
        model_findings = tuple(
            SecurityFinding(
                severity=str(item.get("severity", "medium")),
                kind=str(item.get("kind", "model")),
                detail=str(item.get("detail", "")),
                path=str(item["path"]) if item.get("path") else None,
            )
            for item in raw.get("findings", [])
            if isinstance(item, dict)
        )
        findings = scanned + model_findings
        blocking = tuple(
            f for f in findings if f.severity in {"high", "critical", "secret"}
        )
        passed = bool(raw.get("passed", True)) and not blocking
        return SecurityReport(
            step_id=step.step_id,
            passed=passed,
            findings=findings,
            summary=str(
                raw.get(
                    "summary",
                    "no_blocking_findings" if passed else "blocking_security_findings",
                )
            ),
        )

    def _scan_diff(self, diff: DiffBundle) -> tuple[SecurityFinding, ...]:
        findings: list[SecurityFinding] = []
        for patch in diff.patches:
            path = patch.get("path")
            body = patch.get("diff", "")
            for kind, pattern in _SECRET_PATTERNS:
                if pattern.search(body):
                    findings.append(
                        SecurityFinding(
                            severity="secret",
                            kind=kind,
                            detail=f"Potential secret matched ({kind})",
                            path=path,
                        )
                    )
        return tuple(findings)
