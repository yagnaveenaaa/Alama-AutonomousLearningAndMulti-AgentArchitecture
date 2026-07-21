from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from alama_common.errors import AuthorizationError

from tool_gateway.catalog.registry import ToolSchemaRegistry
from tool_gateway.domain.models import (
    CapabilityToken,
    PolicyEffect,
    ToolCallRequest,
    ToolInvokeResult,
    ToolReceipt,
)
from tool_gateway.domain.ports import (
    AuditPort,
    CapabilityIssuer,
    PolicyBridge,
    SandboxExecutor,
)


class ToolGatewayService:
    """schema → policy → capability → sandbox → bound output → receipt (LLD §6.5)."""

    def __init__(
        self,
        catalog: ToolSchemaRegistry,
        issuer: CapabilityIssuer,
        policy: PolicyBridge,
        sandbox: SandboxExecutor,
        audit: AuditPort,
        *,
        policy_version: str,
        max_output_bytes: int,
    ) -> None:
        self._catalog = catalog
        self._issuer = issuer
        self._policy = policy
        self._sandbox = sandbox
        self._audit = audit
        self._policy_version = policy_version
        self._max_output_bytes = max_output_bytes

    async def mint_capability(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        subject_id: UUID,
        tool: str,
        paths: list[str],
    ) -> CapabilityToken:
        self._catalog.get(tool)
        decision = await self._policy.evaluate_tool(
            tenant_id=tenant_id,
            task_id=task_id,
            tool=tool,
            args={},
        )
        if decision.effect == PolicyEffect.DENY:
            raise AuthorizationError(
                "Policy denied capability mint",
                details={"reasons": list(decision.reasons)},
            )
        return await self._issuer.mint(
            tenant_id=tenant_id,
            task_id=task_id,
            subject_id=subject_id,
            tool=tool,
            paths=paths,
            policy_version=decision.policy_version or self._policy_version,
        )

    async def invoke(self, request: ToolCallRequest) -> ToolInvokeResult:
        args = self._catalog.validate_args(request.tool, request.args)
        capability = await self._issuer.verify(request.capability_raw)
        self._assert_capability(capability, request)

        decision = await self._policy.evaluate_tool(
            tenant_id=request.tenant_id,
            task_id=request.task_id,
            tool=request.tool,
            args=args,
        )
        if decision.effect == PolicyEffect.DENY:
            raise AuthorizationError(
                "Policy denied tool invocation",
                details={"reasons": list(decision.reasons)},
            )
        if decision.effect == PolicyEffect.APPROVAL_REQUIRED:
            raise AuthorizationError(
                "Tool requires approval",
                details={
                    "required_approvals": list(decision.required_approvals),
                    "reasons": list(decision.reasons),
                },
            )

        result = await self._sandbox.exec(
            tool=request.tool,
            args=args,
            paths=capability.paths,
            task_id=request.task_id,
        )
        output = self._bound_output(result.output)
        receipt = ToolReceipt.create(
            tenant_id=request.tenant_id,
            task_id=request.task_id,
            tool=request.tool,
            inputs_hash=hash_args(args),
            output=output,
            duration_ms=result.duration_ms,
            policy_version=decision.policy_version,
            capability_id=capability.token_id,
            ok=result.ok,
            max_inline_bytes=self._max_output_bytes,
        )
        await self._audit.emit_receipt(receipt)
        return ToolInvokeResult(ok=result.ok, output=output, receipt=receipt)

    def _assert_capability(self, capability: CapabilityToken, request: ToolCallRequest) -> None:
        if capability.tenant_id != request.tenant_id:
            raise AuthorizationError("Capability tenant mismatch")
        if capability.task_id != request.task_id:
            raise AuthorizationError("Capability task mismatch")
        if capability.tool != request.tool:
            raise AuthorizationError("Capability tool mismatch")
        if capability.is_expired():
            raise AuthorizationError("Capability expired")

    def _bound_output(self, output: str) -> str:
        encoded = output.encode("utf-8")
        if len(encoded) <= self._max_output_bytes:
            return output
        return encoded[: self._max_output_bytes].decode("utf-8", errors="ignore") + "…[truncated]"


def hash_args(args: dict[str, Any]) -> str:
    raw = json.dumps(args, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
