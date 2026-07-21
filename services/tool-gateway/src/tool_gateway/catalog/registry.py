from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alama_common.errors import ValidationError

from tool_gateway.domain.models import ToolName


@dataclass(frozen=True, slots=True)
class ToolSchema:
    name: str
    description: str
    required_args: tuple[str, ...]
    optional_args: tuple[str, ...]
    path_arg: str | None = None
    high_risk: bool = False


class ToolSchemaRegistry:
    """JSON-schema-class registry for MVP tools (LLD §2.10 / §6.5)."""

    def __init__(self, schemas: list[ToolSchema] | None = None) -> None:
        items = schemas or default_schemas()
        self._by_name = {s.name: s for s in items}

    def get(self, name: str) -> ToolSchema:
        schema = self._by_name.get(name)
        if schema is None:
            raise ValidationError(f"Unknown tool: {name}")
        return schema

    def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        schema = self.get(name)
        missing = [key for key in schema.required_args if key not in args]
        if missing:
            raise ValidationError(
                f"Missing required args for {name}",
                details={"missing": missing},
            )
        allowed = set(schema.required_args) | set(schema.optional_args)
        unknown = [key for key in args if key not in allowed]
        if unknown:
            raise ValidationError(
                f"Unknown args for {name}",
                details={"unknown": unknown},
            )
        if schema.path_arg and schema.path_arg in args:
            path = str(args[schema.path_arg])
            if path.startswith("/") or ".." in path.replace("\\", "/").split("/"):
                raise ValidationError("path must be workspace-relative without '..'")
        return dict(args)

    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)


def default_schemas() -> list[ToolSchema]:
    return [
        ToolSchema(
            name=ToolName.GET_FILE.value,
            description="Read a workspace file",
            required_args=("path",),
            optional_args=(),
            path_arg="path",
        ),
        ToolSchema(
            name=ToolName.SEARCH_CODE.value,
            description="Search code in workspace",
            required_args=("query",),
            optional_args=("path",),
            path_arg="path",
        ),
        ToolSchema(
            name=ToolName.APPLY_PATCH.value,
            description="Apply a unified diff patch",
            required_args=("path", "diff"),
            optional_args=(),
            path_arg="path",
            high_risk=True,
        ),
        ToolSchema(
            name=ToolName.LIST_DIR.value,
            description="List directory entries",
            required_args=("path",),
            optional_args=(),
            path_arg="path",
        ),
        ToolSchema(
            name=ToolName.RUN_TESTS.value,
            description="Run allowlisted tests",
            required_args=(),
            optional_args=("selector",),
        ),
        ToolSchema(
            name=ToolName.RUN_COMMAND.value,
            description="Run allowlisted command",
            required_args=("command",),
            optional_args=("cwd",),
            high_risk=True,
        ),
        ToolSchema(
            name=ToolName.OPEN_PR.value,
            description="Open pull request via brokered SCM",
            required_args=("title",),
            optional_args=("body",),
            high_risk=True,
        ),
        ToolSchema(
            name=ToolName.READ_CI.value,
            description="Read CI status",
            required_args=(),
            optional_args=("run_id",),
        ),
        ToolSchema(
            name=ToolName.GIT_CHECKOUT.value,
            description="Checkout ref inside sandbox only",
            required_args=("ref",),
            optional_args=(),
            high_risk=True,
        ),
    ]
