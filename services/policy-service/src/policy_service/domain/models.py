from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from alama_common.errors import ConflictError, ValidationError
from alama_common.ids import new_uuid7


class BundleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class PolicyAction(StrEnum):
    CREATE_TASK = "create_task"
    INVOKE_TOOL = "invoke_tool"
    COMPLETE_MODEL = "complete_model"
    EMBED_MODEL = "embed_model"
    CONNECT_REPO = "connect_repo"
    WRITE_BRANCH = "write_branch"
    EXPORT_MEMORY = "export_memory"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Evaluation result (LLD §2.6)."""

    effect: PolicyEffect
    required_approvals: tuple[str, ...]
    constraints: dict[str, Any]
    policy_version: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyInput:
    tenant_id: UUID
    subject_id: UUID | None
    action: PolicyAction
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """Cedar/OPA-class rule: when match → effect."""

    id: str
    action: str
    effect: PolicyEffect
    when: dict[str, Any]
    required_approvals: tuple[str, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class PolicyBundle:
    """Immutable versioned policy document (LLD §4.8)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        version: str,
        bundle_ref: str,
        checksum: str,
        status: BundleStatus,
        rules: tuple[PolicyRule, ...],
        created_at: datetime,
        activated_at: datetime | None = None,
    ) -> None:
        if not version.strip():
            raise ValidationError("version is required")
        self.id = id
        self.tenant_id = tenant_id
        self.version = version
        self.bundle_ref = bundle_ref
        self.checksum = checksum
        self.status = status
        self.rules = rules
        self.created_at = created_at
        self.activated_at = activated_at

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        version: str,
        rules: tuple[PolicyRule, ...],
        checksum: str,
        bundle_ref: str | None = None,
        status: BundleStatus = BundleStatus.DRAFT,
    ) -> PolicyBundle:
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            version=version,
            bundle_ref=bundle_ref or f"policy-bundles/{tenant_id}/{version}.json",
            checksum=checksum,
            status=status,
            rules=rules,
            created_at=datetime.now(UTC),
        )

    def activate(self) -> None:
        if self.status == BundleStatus.RETIRED:
            raise ConflictError("Cannot activate a retired bundle")
        self.status = BundleStatus.ACTIVE
        self.activated_at = datetime.now(UTC)

    def retire(self) -> None:
        if self.status != BundleStatus.ACTIVE:
            raise ConflictError("Only active bundles can be retired")
        self.status = BundleStatus.RETIRED
