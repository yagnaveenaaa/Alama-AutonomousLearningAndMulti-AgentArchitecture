from __future__ import annotations

from alama_common.errors import NotFoundError

from model_gateway.domain.models import PromptTemplate


class InMemoryPromptTemplateRegistry:
    """Versioned immutable prompt templates (LLD §6.8)."""

    def __init__(self, templates: list[PromptTemplate] | None = None) -> None:
        self._templates: dict[tuple[str, str], PromptTemplate] = {}
        self._latest: dict[str, str] = {}
        for template in templates or default_templates():
            self.register(template)

    def register(self, template: PromptTemplate) -> None:
        self._templates[(template.name, template.version)] = template
        self._latest[template.name] = template.version

    async def get(self, name: str, version: str | None = None) -> PromptTemplate:
        resolved = version or self._latest.get(name)
        if resolved is None:
            raise NotFoundError(f"Unknown prompt template: {name}")
        template = self._templates.get((name, resolved))
        if template is None:
            raise NotFoundError(f"Unknown prompt template version: {name}.{resolved}")
        return template


def default_templates() -> list[PromptTemplate]:
    return [
        PromptTemplate(
            name="planner",
            version="v1",
            body=(
                "You are the Planner. Objective: {{objective}}. "
                "Repo summary: {{repo_summary}}. Return Plan JSON only."
            ),
            output_schema="Plan",
        ),
        PromptTemplate(
            name="coder",
            version="v1",
            body="You are the Coder. Implement the step with tool intents only.",
            output_schema="CoderOutput",
        ),
        PromptTemplate(
            name="tester",
            version="v1",
            body="You are the Tester. Interpret results into TestReport JSON.",
            output_schema="TestReport",
        ),
    ]
