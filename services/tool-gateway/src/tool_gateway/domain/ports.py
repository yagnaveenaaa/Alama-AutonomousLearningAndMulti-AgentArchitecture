from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from tool_gateway.domain.models import (
    CapabilityToken,
    PolicyDecision,
    SandboxResult,
    ToolCallRequest,
    ToolInvokeResult,
    ToolReceipt,
)


class CapabilityIssuer(Protocol):
    async def mint(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        subject_id: UUID,
        tool: str,
        paths: list[str],
        policy_version: str,
    ) -> CapabilityToken: ...

    async def verify(self, raw: str) -> CapabilityToken: ...


class SandboxExecutor(Protocol):
    async def exec(
        self,
        *,
        tool: str,
        args: dict[str, Any],
        paths: tuple[str, ...],
        task_id: UUID,
    ) -> SandboxResult: ...


class PolicyBridge(Protocol):
    async def evaluate_tool(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        tool: str,
        args: dict[str, Any],
    ) -> PolicyDecision: ...


class AuditPort(Protocol):
    async def emit_receipt(self, receipt: ToolReceipt) -> None: ...


class ToolGateway(Protocol):
    async def mint_capability(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        subject_id: UUID,
        tool: str,
        paths: list[str],
    ) -> CapabilityToken: ...

    async def invoke(self, request: ToolCallRequest) -> ToolInvokeResult: ...
