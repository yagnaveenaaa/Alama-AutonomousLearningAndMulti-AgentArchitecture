from __future__ import annotations

import pytest

from alama_common.errors.base import AlamaError
from alama_common.errors.types import (
    AuthenticationError,
    AuthorizationError,
    BudgetExceededError,
    ConflictError,
    DependencyFatalError,
    DependencyTransientError,
    DomainInvariantError,
    NotFoundError,
    PreconditionFailedError,
    RateLimitedError,
    SandboxError,
    ValidationError,
)


@pytest.mark.parametrize(
    ("exc_cls", "expected_code", "expected_status", "expected_retryable"),
    [
        (ValidationError, "validation_error", 400, False),
        (AuthenticationError, "authentication_error", 401, False),
        (AuthorizationError, "authorization_error", 403, False),
        (NotFoundError, "not_found", 404, False),
        (ConflictError, "conflict", 409, False),
        (PreconditionFailedError, "precondition_failed", 412, False),
        (RateLimitedError, "rate_limited", 429, True),
        (BudgetExceededError, "budget_exceeded", 429, False),
        (DomainInvariantError, "domain_invariant_violation", 422, False),
        (DependencyFatalError, "dependency_fatal", 502, False),
        (DependencyTransientError, "dependency_transient", 503, True),
        (SandboxError, "sandbox_error", 500, False),
    ],
)
def test_error_taxonomy_matches_lld(
    exc_cls: type[AlamaError],
    expected_code: str,
    expected_status: int,
    expected_retryable: bool,
) -> None:
    exc = exc_cls("boom", details={"field": "value"})
    assert exc.code == expected_code
    assert exc.http_status == expected_status
    assert exc.retryable is expected_retryable
    assert exc.to_dict()["code"] == expected_code
    assert exc.to_dict()["details"] == {"field": "value"}


def test_rate_limited_retry_after() -> None:
    exc = RateLimitedError("slow down", retry_after_seconds=30)
    assert exc.retry_after_seconds == 30
    assert exc.details["retry_after_seconds"] == 30


def test_sandbox_error_conditional_retryable() -> None:
    exc = SandboxError("tool failed", retryable=True)
    assert exc.retryable is True
