from __future__ import annotations

import pytest

from alama_common.errors.types import DependencyTransientError
from alama_common.retry.policy import RetryPolicy, retry_with_policy


def test_retry_policy_succeeds_after_transient_failure() -> None:
    attempts = {"count": 0}

    def operation() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise DependencyTransientError("temporary")
        return "ok"

    policy = RetryPolicy.outbound_http()
    result = retry_with_policy(policy, operation)
    assert result == "ok"
    assert attempts["count"] == 3


def test_retry_policy_stops_on_non_retryable_error() -> None:
    attempts = {"count": 0}

    def operation() -> None:
        attempts["count"] += 1
        raise ValueError("fatal")

    policy = RetryPolicy.outbound_http()
    with pytest.raises(ValueError):
        retry_with_policy(policy, operation)
    assert attempts["count"] == 1
