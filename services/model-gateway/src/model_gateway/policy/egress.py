from __future__ import annotations

from alama_common.errors import AuthorizationError, ValidationError

from model_gateway.domain.models import ModelRequest


class EgressPolicy:
    """Training prohibition / retention constraints before provider call."""

    def __init__(self, *, allow_provider_training: bool = False) -> None:
        self._allow_training = allow_provider_training

    def assert_allowed(self, request: ModelRequest) -> None:
        if not request.purpose.strip():
            raise ValidationError("purpose is required")
        constraints = request.template_inputs.get("policy_constraints", {})
        if isinstance(constraints, dict) and constraints.get("deny_egress"):
            raise AuthorizationError("Policy denies model egress")
        if not self._allow_training and constraints.get("provider_training") is True:
            raise AuthorizationError("Provider training use is prohibited")
