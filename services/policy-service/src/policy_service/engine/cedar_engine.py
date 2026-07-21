from __future__ import annotations

from typing import Any

from policy_service.domain.models import (
    PolicyBundle,
    PolicyDecision,
    PolicyEffect,
    PolicyInput,
    PolicyRule,
)


class CedarStylePolicyEngine:
    """OPA/Cedar-class evaluator wrapper (LLD §2.6).

    First-match deny wins; otherwise first approval_required; else allow.
    Match semantics:
    - rule.when keys compared to input.attributes (plus action)
    - list values mean membership
    - ``*`` matches any present value
    - keys ending in ``_gte`` / ``_lte`` compare numeric attributes
    """

    def evaluate(self, bundle: PolicyBundle, policy_input: PolicyInput) -> PolicyDecision:
        matched: list[tuple[PolicyRule, dict[str, Any]]] = []
        for rule in bundle.rules:
            if rule.action not in {"*", policy_input.action.value}:
                continue
            if self._matches(rule.when, policy_input):
                matched.append((rule, dict(rule.constraints)))

        denies = [item for item in matched if item[0].effect == PolicyEffect.DENY]
        if denies:
            rule, constraints = denies[0]
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                required_approvals=(),
                constraints=constraints,
                policy_version=bundle.version,
                reasons=(rule.reason or rule.id,),
            )

        approvals = [
            item for item in matched if item[0].effect == PolicyEffect.APPROVAL_REQUIRED
        ]
        if approvals:
            rule, constraints = approvals[0]
            return PolicyDecision(
                effect=PolicyEffect.APPROVAL_REQUIRED,
                required_approvals=rule.required_approvals,
                constraints=constraints,
                policy_version=bundle.version,
                reasons=(rule.reason or rule.id,),
            )

        allows = [item for item in matched if item[0].effect == PolicyEffect.ALLOW]
        if allows:
            rule, constraints = allows[0]
            return PolicyDecision(
                effect=PolicyEffect.ALLOW,
                required_approvals=(),
                constraints=constraints,
                policy_version=bundle.version,
                reasons=(rule.reason or rule.id,),
            )

        return PolicyDecision(
            effect=PolicyEffect.DENY,
            required_approvals=(),
            constraints={},
            policy_version=bundle.version,
            reasons=("no_matching_allow_rule",),
        )

    def _matches(self, when: dict[str, Any], policy_input: PolicyInput) -> bool:
        attrs: dict[str, Any] = {
            "action": policy_input.action.value,
            **policy_input.attributes,
        }
        for key, expected in when.items():
            if key.endswith("_gte"):
                actual = attrs.get(key[:-4])
                if actual is None or not isinstance(actual, (int, float)):
                    return False
                if not isinstance(expected, (int, float)) or actual < expected:
                    return False
                continue
            if key.endswith("_lte"):
                actual = attrs.get(key[:-4])
                if actual is None or not isinstance(actual, (int, float)):
                    return False
                if not isinstance(expected, (int, float)) or actual > expected:
                    return False
                continue
            actual = attrs.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif expected == "*":
                if key not in attrs:
                    return False
            elif actual != expected:
                return False
        return True
