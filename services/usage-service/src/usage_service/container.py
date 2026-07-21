from __future__ import annotations

from dataclasses import dataclass

from usage_service.adapters.memory import (
    InMemoryAnomalyRepository,
    InMemoryBudgetRepository,
    InMemoryUsageLedgerRepository,
    InMemoryUsageStore,
)
from usage_service.application.anomaly import AnomalyDetector
from usage_service.application.budget import BudgetService
from usage_service.application.ingest import UsageIngestor
from usage_service.application.summary import UsageSummaryService
from usage_service.config import UsageSettings


@dataclass
class UsageContainer:
    store: InMemoryUsageStore
    ingestor: UsageIngestor
    budgets: BudgetService
    summary: UsageSummaryService
    anomalies: AnomalyDetector


def build_container(settings: UsageSettings | None = None) -> UsageContainer:
    settings = settings or UsageSettings()
    store = InMemoryUsageStore()
    ledger = InMemoryUsageLedgerRepository(store)
    budget_repo = InMemoryBudgetRepository(store)
    anomaly_repo = InMemoryAnomalyRepository(store)
    budgets = BudgetService(
        budget_repo,
        default_limit_tokens=settings.default_limit_tokens,
        default_limit_usd_micros=settings.default_limit_usd_micros,
        default_soft_pct=settings.default_soft_pct,
    )
    anomalies = AnomalyDetector(
        ledger,
        anomaly_repo,
        spike_ratio=settings.anomaly_spike_ratio,
        min_baseline_events=settings.anomaly_min_baseline_events,
    )
    ingestor = UsageIngestor(ledger, budgets, anomalies)
    return UsageContainer(
        store=store,
        ingestor=ingestor,
        budgets=budgets,
        summary=UsageSummaryService(ledger, budgets, anomalies),
        anomalies=anomalies,
    )
