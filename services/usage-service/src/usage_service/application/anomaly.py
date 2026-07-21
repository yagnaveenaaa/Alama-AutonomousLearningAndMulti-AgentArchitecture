from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from usage_service.domain.models import AnomalyFlag, UsageCategory
from usage_service.domain.repositories import AnomalyRepository, UsageLedgerRepository


class AnomalyDetector:
    """Spike detection per tenant (LLD §2.12)."""

    def __init__(
        self,
        ledger: UsageLedgerRepository,
        anomalies: AnomalyRepository,
        *,
        spike_ratio: float,
        min_baseline_events: int,
    ) -> None:
        self._ledger = ledger
        self._anomalies = anomalies
        self._spike_ratio = spike_ratio
        self._min_baseline = min_baseline_events

    async def evaluate(
        self, tenant_id: UUID, category: UsageCategory
    ) -> AnomalyFlag | None:
        now = datetime.now(UTC)
        recent_since = now - timedelta(hours=1)
        baseline_since = now - timedelta(days=7)
        records = await self._ledger.list_for_tenant(
            tenant_id, since=baseline_since, until=None
        )
        cat_records = [r for r in records if r.category == category]
        if len(cat_records) < self._min_baseline + 1:
            return None

        recent = [r for r in cat_records if r.created_at >= recent_since]
        prior = [r for r in cat_records if r.created_at < recent_since]
        if not prior or not recent:
            return None

        prior_hours = max(1.0, (now - baseline_since).total_seconds() / 3600.0 - 1.0)
        baseline = sum(r.quantity for r in prior) / prior_hours
        current = float(sum(r.quantity for r in recent))
        if baseline <= 0:
            return None
        ratio = current / baseline
        if ratio < self._spike_ratio:
            return None

        flag = AnomalyFlag(
            tenant_id=tenant_id,
            category=category,
            ratio=ratio,
            baseline=baseline,
            current=current,
            detected_at=now,
            message=f"Usage spike for {category.value}: {ratio:.1f}x baseline",
        )
        await self._anomalies.save(flag)
        return flag

    async def list_flags(self, tenant_id: UUID) -> list[AnomalyFlag]:
        return await self._anomalies.list_for_tenant(tenant_id)
