from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from usage_service.application.anomaly import AnomalyDetector
from usage_service.application.budget import BudgetService
from usage_service.domain.models import BudgetPeriod, UsageSummary
from usage_service.domain.repositories import UsageLedgerRepository


class UsageSummaryService:
    """Showback aggregates for GET /usage/summary (LLD §5.6)."""

    def __init__(
        self,
        ledger: UsageLedgerRepository,
        budgets: BudgetService,
        anomalies: AnomalyDetector,
    ) -> None:
        self._ledger = ledger
        self._budgets = budgets
        self._anomalies = anomalies

    async def summarize(
        self, tenant_id: UUID, *, period: BudgetPeriod = BudgetPeriod.MONTHLY
    ) -> UsageSummary:
        budget = await self._budgets.ensure_budget(tenant_id, period)
        records = await self._ledger.list_for_tenant(tenant_id, since=None, until=None)
        by_category: dict[str, int] = defaultdict(int)
        for record in records:
            by_category[record.category.value] += record.quantity
        flags = await self._anomalies.list_flags(tenant_id)
        return UsageSummary(
            tenant_id=tenant_id,
            period=period.value,
            tokens_used=budget.spent_tokens,
            tokens_budget=budget.limit_tokens,
            usd_micros_used=budget.spent_usd_micros,
            usd_micros_budget=budget.limit_usd_micros,
            soft_warning=budget.soft_warning(),
            by_category=dict(by_category),
            anomalies=tuple(flags),
        )
