from __future__ import annotations

from typing import Any

from agent_worker.domain.ports import ModelGatewayPort
from agent_worker.protocols.artifacts import DiffBundle, PlanStep, ReviewReport


class ReviewerAgent:
    """Reviewer — independent review of diff vs objective/policy (LLD §6.1 / §6.8)."""

    def __init__(self, model: ModelGatewayPort, *, template_name: str) -> None:
        self._model = model
        self._template_name = template_name

    async def review(
        self,
        *,
        step: PlanStep,
        objective: str,
        diff: DiffBundle,
        policy_constraints: dict[str, Any] | None = None,
    ) -> ReviewReport:
        raw = await self._model.complete_json(
            template_name=self._template_name,
            inputs={
                "step_id": step.step_id,
                "goal": step.goal,
                "objective": objective,
                "diff_summary": diff.summary,
                "patches": list(diff.patches),
                "standards": "minimal_diff_matches_objective",
                "policy_constraints": policy_constraints or {},
            },
            schema_name="ReviewReport",
        )
        findings = tuple(str(f) for f in raw.get("findings", []))
        policy_notes = tuple(str(n) for n in raw.get("policy_notes", []))
        approved = bool(raw.get("approved", True))
        if not diff.patches:
            approved = False
            findings = (*findings, "empty_diff")
        return ReviewReport(
            step_id=step.step_id,
            approved=approved,
            findings=findings,
            policy_notes=policy_notes,
            summary=str(raw.get("summary", "approved" if approved else "changes_requested")),
        )
