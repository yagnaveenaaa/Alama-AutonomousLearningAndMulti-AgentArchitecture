from __future__ import annotations

from agent_worker.domain.ports import ModelGatewayPort
from agent_worker.protocols.artifacts import DiffBundle, PlanStep, TestReport, ToolResult


class TesterAgent:
    """Tester — interpret tool/test outcomes into TestReport (LLD §6.1)."""

    def __init__(self, model: ModelGatewayPort, *, template_name: str) -> None:
        self._model = model
        self._template_name = template_name

    async def verify(
        self,
        *,
        step: PlanStep,
        diff: DiffBundle,
        tool_results: list[ToolResult],
    ) -> TestReport:
        raw = await self._model.complete_json(
            template_name=self._template_name,
            inputs={
                "step_id": step.step_id,
                "goal": step.goal,
                "diff_summary": diff.summary,
                "tool_results": [
                    {"name": r.name, "ok": r.ok, "output": r.output} for r in tool_results
                ],
            },
            schema_name="TestReport",
        )
        failures = tuple(str(f) for f in raw.get("failures", []))
        passed = bool(raw.get("passed", all(r.ok for r in tool_results)))
        return TestReport(
            step_id=step.step_id,
            passed=passed and not failures,
            tests_run=int(raw.get("tests_run", len(tool_results) or 1)),
            failures=failures,
            interpretation=str(raw.get("interpretation", "ok" if passed else "failed")),
            proposed_fix_step=(
                str(raw["proposed_fix_step"]) if raw.get("proposed_fix_step") else None
            ),
        )
