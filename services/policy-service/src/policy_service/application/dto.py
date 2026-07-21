from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from policy_service.domain.models import PolicyAction, PolicyDecision


@dataclass(frozen=True, slots=True)
class EvaluatePolicyCommand:
    tenant_id: UUID
    subject_id: UUID | None
    action: PolicyAction
    attributes: dict[str, Any]
    policy_version: str | None = None
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class ActivateBundleCommand:
    tenant_id: UUID
    version: str
    subject_id: UUID


@dataclass(frozen=True, slots=True)
class UpsertDraftBundleCommand:
    tenant_id: UUID
    version: str
    rules_payload: dict[str, Any]
    subject_id: UUID


__all__ = [
    "ActivateBundleCommand",
    "EvaluatePolicyCommand",
    "PolicyDecision",
    "UpsertDraftBundleCommand",
]
