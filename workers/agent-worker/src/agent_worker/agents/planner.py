from __future__ import annotations

from typing import Any

from alama_common.errors import DomainInvariantError, ValidationError

from agent_worker.domain.ports import ModelGatewayPort
from agent_worker.protocols.artifacts import Plan, PlanStep, RiskLevel


class PlanValidator:
    """Deterministic plan validation (LLD §6.3 step 5)."""

    def __init__(
        self,
        *,
        max_steps: int,
        allowed_tools: frozenset[str],
    ) -> None:
        self._max_steps = max_steps
        self._allowed_tools = allowed_tools

    def validate(self, plan: Plan) -> Plan:
        if len(plan.steps) > self._max_steps:
            raise DomainInvariantError(
                f"Plan exceeds max steps ({self._max_steps})",
                details={"step_count": len(plan.steps)},
            )
        cleaned: list[PlanStep] = []
        for step in plan.steps:
            tools = tuple(t for t in step.tools_needed if t in self._allowed_tools)
            cleaned.append(
                PlanStep(
                    step_id=step.step_id,
                    goal=step.goal,
                    files_likely=step.files_likely,
                    tools_needed=tools,
                    risk=step.risk,
                    verification=step.verification,
                    approval_gates=step.approval_gates,
                    stop_conditions=step.stop_conditions,
                    depends_on=step.depends_on,
                    tags=step.tags,
                )
            )
        return Plan(
            objective=plan.objective,
            steps=tuple(cleaned),
            success_criteria=plan.success_criteria,
            risks=plan.risks,
            stop_conditions=plan.stop_conditions,
        )


class PlannerAgent:
    """Planner role — decompose objective → Plan JSON (LLD §6.1 / §6.8)."""

    def __init__(
        self,
        model: ModelGatewayPort,
        validator: PlanValidator,
        *,
        template_name: str,
    ) -> None:
        self._model = model
        self._validator = validator
        self._template_name = template_name

    async def draft_plan(
        self,
        *,
        objective: str,
        retrieval_pack: dict[str, Any],
        policy_constraints: dict[str, Any],
    ) -> Plan:
        if not objective.strip():
            raise ValidationError("objective is required")
        raw = await self._model.complete_json(
            template_name=self._template_name,
            inputs={
                "objective": objective,
                "repo_summary": retrieval_pack.get("summary", ""),
                "retrieval_pack": retrieval_pack,
                "policy_constraints": policy_constraints,
            },
            schema_name="Plan",
        )
        plan = Plan.from_payload(raw)
        return self._validator.validate(plan)


def default_plan_from_objective(objective: str) -> dict[str, Any]:
    """Deterministic fallback used by in-memory model gateway for tests."""
    return {
        "objective": objective,
        "success_criteria": ["tests pass", "diff matches objective"],
        "risks": ["regression"],
        "stop_conditions": ["budget exhausted", "approval rejected"],
        "steps": [
            {
                "step_id": "step-1",
                "goal": f"Implement: {objective}",
                "files_likely": ["src/main.py"],
                "tools_needed": ["get_file", "apply_patch", "run_tests"],
                "risk": RiskLevel.MEDIUM.value,
                "verification": "run unit tests",
                "approval_gates": [],
                "stop_conditions": ["tests fail twice"],
                "depends_on": [],
                "tags": ["test", "review", "security"],
            }
        ],
    }
