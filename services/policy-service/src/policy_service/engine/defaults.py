from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from policy_service.domain.models import (
    BundleStatus,
    PolicyAction,
    PolicyBundle,
    PolicyEffect,
    PolicyRule,
)


def default_rules() -> tuple[PolicyRule, ...]:
    """Baseline Cedar-style rules for tools, models, repos, budgets, data class."""
    return (
        PolicyRule(
            id="deny-forbidden-tools",
            action=PolicyAction.INVOKE_TOOL.value,
            effect=PolicyEffect.DENY,
            when={"tool": ["exfiltrate", "disable_audit", "raw_network"]},
            reason="forbidden_tool",
        ),
        PolicyRule(
            id="approve-high-risk-tools",
            action=PolicyAction.INVOKE_TOOL.value,
            effect=PolicyEffect.APPROVAL_REQUIRED,
            when={"high_risk": True},
            required_approvals=("high_risk_tool",),
            constraints={"gate": "high_risk_tool"},
            reason="high_risk_tool_requires_approval",
        ),
        PolicyRule(
            id="allow-invoke-tool",
            action=PolicyAction.INVOKE_TOOL.value,
            effect=PolicyEffect.ALLOW,
            when={},
            reason="tool_allowed",
        ),
        PolicyRule(
            id="deny-training-models",
            action=PolicyAction.COMPLETE_MODEL.value,
            effect=PolicyEffect.DENY,
            when={"purpose": "training"},
            reason="training_use_forbidden",
        ),
        PolicyRule(
            id="deny-residency-mismatch",
            action=PolicyAction.COMPLETE_MODEL.value,
            effect=PolicyEffect.DENY,
            when={"residency_ok": False},
            reason="model_residency_violation",
        ),
        PolicyRule(
            id="allow-complete-model",
            action=PolicyAction.COMPLETE_MODEL.value,
            effect=PolicyEffect.ALLOW,
            when={},
            reason="model_allowed",
        ),
        PolicyRule(
            id="allow-embed-model",
            action=PolicyAction.EMBED_MODEL.value,
            effect=PolicyEffect.ALLOW,
            when={},
            reason="embed_allowed",
        ),
        PolicyRule(
            id="approve-protected-branch",
            action=PolicyAction.WRITE_BRANCH.value,
            effect=PolicyEffect.APPROVAL_REQUIRED,
            when={"branch": ["main", "master", "release"]},
            required_approvals=("protected_branch",),
            reason="protected_branch_write",
        ),
        PolicyRule(
            id="allow-write-branch",
            action=PolicyAction.WRITE_BRANCH.value,
            effect=PolicyEffect.ALLOW,
            when={},
            reason="branch_write_allowed",
        ),
        PolicyRule(
            id="allow-connect-repo",
            action=PolicyAction.CONNECT_REPO.value,
            effect=PolicyEffect.ALLOW,
            when={},
            reason="repo_connect_allowed",
        ),
        PolicyRule(
            id="deny-secret-export",
            action=PolicyAction.EXPORT_MEMORY.value,
            effect=PolicyEffect.DENY,
            when={"data_class": ["secret", "restricted"]},
            reason="data_class_export_denied",
        ),
        PolicyRule(
            id="allow-export-memory",
            action=PolicyAction.EXPORT_MEMORY.value,
            effect=PolicyEffect.ALLOW,
            when={},
            reason="memory_export_allowed",
        ),
        PolicyRule(
            id="deny-over-budget",
            action=PolicyAction.CREATE_TASK.value,
            effect=PolicyEffect.DENY,
            when={"budget_exceeded": True},
            reason="budget_hard_stop",
        ),
        PolicyRule(
            id="approve-high-budget",
            action=PolicyAction.CREATE_TASK.value,
            effect=PolicyEffect.APPROVAL_REQUIRED,
            when={"budget_usd_micros_gte": 50_000_000},
            required_approvals=("budget_owner",),
            reason="high_budget_requires_approval",
        ),
        PolicyRule(
            id="allow-create-task",
            action=PolicyAction.CREATE_TASK.value,
            effect=PolicyEffect.ALLOW,
            when={},
            reason="task_create_allowed",
        ),
    )


def rules_checksum(rules: tuple[PolicyRule, ...]) -> str:
    payload = [_rule_to_dict(rule) for rule in rules]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def rules_to_payload(rules: tuple[PolicyRule, ...]) -> dict[str, Any]:
    return {"schema_version": 1, "rules": [_rule_to_dict(rule) for rule in rules]}


def rules_from_payload(payload: dict[str, Any]) -> tuple[PolicyRule, ...]:
    raw_rules = payload.get("rules", [])
    if not isinstance(raw_rules, list):
        return ()
    rules: list[PolicyRule] = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        approvals = item.get("required_approvals") or []
        constraints = item.get("constraints") or {}
        when = item.get("when") or {}
        rules.append(
            PolicyRule(
                id=str(item["id"]),
                action=str(item["action"]),
                effect=PolicyEffect(str(item["effect"])),
                when=dict(when),
                required_approvals=tuple(str(a) for a in approvals),
                constraints=dict(constraints),
                reason=str(item.get("reason") or ""),
            )
        )
    return tuple(rules)


def build_default_bundle(*, tenant_id: UUID, version: str = "policy.v1") -> PolicyBundle:
    rules = default_rules()
    return PolicyBundle.create(
        tenant_id=tenant_id,
        version=version,
        rules=rules,
        checksum=rules_checksum(rules),
        status=BundleStatus.ACTIVE,
    )


def _rule_to_dict(rule: PolicyRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "action": rule.action,
        "effect": rule.effect.value,
        "when": rule.when,
        "required_approvals": list(rule.required_approvals),
        "constraints": rule.constraints,
        "reason": rule.reason,
    }
