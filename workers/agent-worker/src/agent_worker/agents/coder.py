from __future__ import annotations

from typing import Any

from agent_worker.domain.ports import ModelGatewayPort
from agent_worker.protocols.artifacts import DiffBundle, PlanStep, ToolCallIntent


class CoderAgent:
    """Coder/Executor — emit tool intents and patch summary (LLD §6.1 / §6.5)."""

    def __init__(self, model: ModelGatewayPort, *, template_name: str) -> None:
        self._model = model
        self._template_name = template_name

    async def execute_step(
        self,
        *,
        step: PlanStep,
        retrieval_pack: dict[str, Any],
        prior_failures: list[str],
    ) -> tuple[DiffBundle, list[ToolCallIntent]]:
        raw = await self._model.complete_json(
            template_name=self._template_name,
            inputs={
                "step": {
                    "step_id": step.step_id,
                    "goal": step.goal,
                    "files_likely": list(step.files_likely),
                    "tools_needed": list(step.tools_needed),
                },
                "retrieval_pack": retrieval_pack,
                "prior_failures": prior_failures,
            },
            schema_name="CoderOutput",
        )
        intents = [
            ToolCallIntent(
                name=str(item["name"]),
                args=dict(item.get("args", {})),
                reason=str(item.get("reason", step.goal)),
            )
            for item in raw.get("tool_intents", [])
        ]
        if not intents:
            intents = [
                ToolCallIntent(
                    name="apply_patch",
                    args={"path": step.files_likely[0] if step.files_likely else "src/main.py"},
                    reason=step.goal,
                )
            ]
        # Strip forbidden tools — never emit raw shell.
        intents = [i for i in intents if i.name != "raw_shell"]
        diff = DiffBundle(
            step_id=step.step_id,
            summary=str(raw.get("summary", step.goal)),
            patches=tuple(dict(p) for p in raw.get("patches", [])),
            tool_intents=tuple(intents),
        )
        return diff, intents
