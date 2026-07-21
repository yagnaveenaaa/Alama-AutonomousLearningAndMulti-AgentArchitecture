from __future__ import annotations

from usage_service.application.anomaly import AnomalyDetector
from usage_service.application.budget import BudgetService
from usage_service.application.dto import IngestUsageCommand
from usage_service.domain.models import UsageCategory, UsageRecord, UsageUnit
from usage_service.domain.repositories import UsageLedgerRepository


class UsageIngestor:
    """Idempotent ledger append + budget apply (LLD §2.12)."""

    def __init__(
        self,
        ledger: UsageLedgerRepository,
        budgets: BudgetService,
        anomalies: AnomalyDetector,
    ) -> None:
        self._ledger = ledger
        self._budgets = budgets
        self._anomalies = anomalies

    async def ingest(self, command: IngestUsageCommand) -> tuple[UsageRecord, bool]:
        existing = await self._ledger.get_by_idempotency_key(
            command.tenant_id, command.idempotency_key
        )
        if existing is not None:
            return existing, False

        record = UsageRecord.create(
            tenant_id=command.tenant_id,
            category=command.category,
            quantity=command.quantity,
            unit=command.unit,
            price_version=command.price_version,
            provider=command.provider,
            idempotency_key=command.idempotency_key,
            task_id=command.task_id,
            model=command.model,
        )
        if command.enforce_budget:
            tokens = 0
            usd = 0
            if command.unit == UsageUnit.TOKENS:
                tokens = command.quantity
            elif command.unit == UsageUnit.USD_MICROS:
                usd = command.quantity
            if command.category == UsageCategory.MODEL_USD:
                usd = command.quantity if command.unit == UsageUnit.USD_MICROS else usd
            await self._budgets.apply_usage(
                command.tenant_id, tokens=tokens, usd_micros=usd
            )
        await self._ledger.append(record)
        await self._anomalies.evaluate(command.tenant_id, command.category)
        return record, True
