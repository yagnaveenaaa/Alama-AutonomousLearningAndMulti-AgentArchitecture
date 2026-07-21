from __future__ import annotations

from typing import Any
from uuid import UUID

from tool_gateway.catalog.registry import ToolSchemaRegistry
from tool_gateway.domain.models import PolicyDecision, PolicyEffect


class AllowlistPolicyBridge:
    """Policy-service bridge stand-in until policy-service is wired (LLD §2.10)."""

    def __init__(self, catalog: ToolSchemaRegistry, *, policy_version: str) -> None:
        self._catalog = catalog
        self._policy_version = policy_version

    async def evaluate_tool(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        tool: str,
        args: dict[str, Any],
    ) -> PolicyDecision:
        _ = (tenant_id, task_id, args)
        try:
            schema = self._catalog.get(tool)
        except Exception:
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                required_approvals=(),
                constraints={},
                policy_version=self._policy_version,
                reasons=("unknown_tool",),
            )
        if schema.high_risk and tool in {"open_pr", "run_command"}:
            return PolicyDecision(
                effect=PolicyEffect.APPROVAL_REQUIRED,
                required_approvals=("high_risk_tool",),
                constraints={"tool": tool},
                policy_version=self._policy_version,
                reasons=("high_risk_tool_requires_approval",),
            )
        return PolicyDecision(
            effect=PolicyEffect.ALLOW,
            required_approvals=(),
            constraints={},
            policy_version=self._policy_version,
            reasons=("allowlisted",),
        )
