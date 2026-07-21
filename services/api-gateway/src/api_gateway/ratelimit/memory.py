from __future__ import annotations

import time
from collections import defaultdict
from uuid import UUID

from alama_common.errors import RateLimitedError


class InMemoryRateLimiter:
    """Fixed-window counters for IP / subject / tenant (LLD §2.1)."""

    def __init__(
        self,
        *,
        ip_per_minute: int,
        subject_per_minute: int,
        tenant_per_minute: int,
    ) -> None:
        self._ip_limit = ip_per_minute
        self._subject_limit = subject_per_minute
        self._tenant_limit = tenant_per_minute
        self._buckets: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    async def check(
        self,
        *,
        ip: str,
        subject_id: UUID,
        tenant_id: UUID,
    ) -> None:
        window = int(time.time() // 60)
        self._bump(f"ip:{ip}", window, self._ip_limit, "ip")
        self._bump(f"subject:{subject_id}", window, self._subject_limit, "subject")
        self._bump(f"tenant:{tenant_id}", window, self._tenant_limit, "tenant")

    def _bump(self, key: str, window: int, limit: int, dimension: str) -> None:
        # Drop old windows for this key
        bucket = self._buckets[key]
        for stale in [w for w in bucket if w < window - 1]:
            del bucket[stale]
        bucket[window] += 1
        if bucket[window] > limit:
            raise RateLimitedError(
                f"Rate limit exceeded ({dimension})",
                retry_after_seconds=60,
                details={"dimension": dimension, "limit": limit},
            )
