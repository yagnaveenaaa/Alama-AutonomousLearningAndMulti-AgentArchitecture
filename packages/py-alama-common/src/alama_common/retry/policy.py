from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from alama_common.errors.base import AlamaError
from alama_common.errors.types import DependencyTransientError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry configuration aligned with LLD §3.3."""

    name: str
    max_attempts: int
    initial_backoff_ms: int
    max_backoff_ms: int
    jitter: bool = True
    retryable_exceptions: tuple[type[BaseException], ...] = (DependencyTransientError,)

    @classmethod
    def outbound_http(cls) -> RetryPolicy:
        return cls(
            name="outbound_http",
            max_attempts=3,
            initial_backoff_ms=100,
            max_backoff_ms=2000,
            jitter=True,
        )

    @classmethod
    def kafka_consumer(cls) -> RetryPolicy:
        return cls(
            name="kafka_consumer",
            max_attempts=5,
            initial_backoff_ms=100,
            max_backoff_ms=5000,
            jitter=True,
        )

    @classmethod
    def model_gateway(cls) -> RetryPolicy:
        return cls(
            name="model_gateway",
            max_attempts=2,
            initial_backoff_ms=200,
            max_backoff_ms=2000,
            jitter=True,
        )

    @classmethod
    def tool_read_only(cls) -> RetryPolicy:
        return cls(
            name="tool_read_only",
            max_attempts=2,
            initial_backoff_ms=100,
            max_backoff_ms=500,
            jitter=False,
        )

    @classmethod
    def embedding_batch(cls) -> RetryPolicy:
        return cls(
            name="embedding_batch",
            max_attempts=5,
            initial_backoff_ms=200,
            max_backoff_ms=5000,
            jitter=True,
        )

    @classmethod
    def notification(cls) -> RetryPolicy:
        return cls(
            name="notification",
            max_attempts=8,
            initial_backoff_ms=500,
            max_backoff_ms=3_600_000,
            jitter=True,
        )


def _compute_backoff_ms(policy: RetryPolicy, attempt: int) -> int:
    backoff = min(policy.initial_backoff_ms * (2 ** (attempt - 1)), policy.max_backoff_ms)
    if policy.jitter:
        return int(random.randint(0, backoff))
    return int(backoff)


def _should_retry(policy: RetryPolicy, exc: BaseException) -> bool:
    if isinstance(exc, AlamaError):
        return exc.retryable
    return isinstance(exc, policy.retryable_exceptions)


def retry_with_policy[T](
    policy: RetryPolicy,
    operation: Callable[[], T],
    *,
    deadline_monotonic: float | None = None,
) -> T:
    """Execute a synchronous operation with bounded retries."""

    attempt = 0
    while True:
        attempt += 1
        try:
            return operation()
        except BaseException as exc:
            if attempt >= policy.max_attempts or not _should_retry(policy, exc):
                raise
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                raise
            time.sleep(_compute_backoff_ms(policy, attempt) / 1000.0)


async def retry_with_policy_async[T](
    policy: RetryPolicy,
    operation: Callable[[], Awaitable[T]],
    *,
    deadline_monotonic: float | None = None,
) -> T:
    """Execute an async operation with bounded retries."""

    attempt = 0
    while True:
        attempt += 1
        try:
            return await operation()
        except BaseException as exc:
            if attempt >= policy.max_attempts or not _should_retry(policy, exc):
                raise
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                raise
            await asyncio.sleep(_compute_backoff_ms(policy, attempt) / 1000.0)
