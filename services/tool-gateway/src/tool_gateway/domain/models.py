from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ValidationError
from alama_common.ids import new_uuid7


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class ToolName(StrEnum):
    GET_FILE = "get_file"
    SEARCH_CODE = "search_code"
    APPLY_PATCH = "apply_patch"
    LIST_DIR = "list_dir"
    RUN_TESTS = "run_tests"
    RUN_COMMAND = "run_command"
    OPEN_PR = "open_pr"
    READ_CI = "read_ci"
    GIT_CHECKOUT = "git_checkout"


FORBIDDEN_TOOLS = frozenset(
    {
        "raw_shell",
        "secret_read",
        "cloud_admin",
        "force_push",
        "prod_deploy",
        "network_egress",
    }
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    effect: PolicyEffect
    required_approvals: tuple[str, ...]
    constraints: dict[str, Any]
    policy_version: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CapabilityToken:
    """Scoped JWT-like capability (LLD §13.2): aud=tool-gateway, task, tool, paths, exp."""

    token_id: UUID
    audience: str
    tenant_id: UUID
    task_id: UUID
    subject_id: UUID
    tool: str
    paths: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    policy_version: str
    raw: str

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    tenant_id: UUID
    task_id: UUID
    tool: str
    args: dict[str, Any]
    capability_raw: str

    def __post_init__(self) -> None:
        if not self.tool.strip():
            raise ValidationError("tool is required")
        if self.tool in FORBIDDEN_TOOLS:
            raise ValidationError(f"tool is forbidden: {self.tool}")


@dataclass(frozen=True, slots=True)
class SandboxResult:
    ok: bool
    output: str
    exit_code: int
    duration_ms: int
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ToolReceipt:
    """Audit receipt for every tool call (LLD §2.10)."""

    receipt_id: UUID
    tenant_id: UUID
    task_id: UUID
    tool: str
    inputs_hash: str
    output_ref: str | None
    output_inline: str | None
    duration_ms: int
    policy_version: str
    capability_id: UUID
    ok: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        task_id: UUID,
        tool: str,
        inputs_hash: str,
        output: str,
        duration_ms: int,
        policy_version: str,
        capability_id: UUID,
        ok: bool,
        max_inline_bytes: int,
    ) -> ToolReceipt:
        if len(output.encode("utf-8")) > max_inline_bytes:
            output_ref = f"tool-outputs/{task_id}/{new_uuid7()}.txt"
            output_inline = None
        else:
            output_ref = None
            output_inline = output
        return cls(
            receipt_id=new_uuid7(),
            tenant_id=tenant_id,
            task_id=task_id,
            tool=tool,
            inputs_hash=inputs_hash,
            output_ref=output_ref,
            output_inline=output_inline,
            duration_ms=duration_ms,
            policy_version=policy_version,
            capability_id=capability_id,
            ok=ok,
        )


@dataclass(frozen=True, slots=True)
class ToolInvokeResult:
    ok: bool
    output: str
    receipt: ToolReceipt
