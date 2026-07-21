from __future__ import annotations

from uuid import uuid4

import pytest
from alama_common.errors import BudgetExceededError
from httpx import ASGITransport, AsyncClient

from usage_service.application.dto import IngestUsageCommand, UpsertBudgetCommand
from usage_service.config import UsageSettings
from usage_service.container import build_container
from usage_service.domain.models import BudgetPeriod, UsageCategory, UsageUnit
from usage_service.main import create_app


@pytest.fixture
def container():
    return build_container(
        UsageSettings(
            use_in_memory_store=True,
            default_limit_tokens=10_000,
            default_limit_usd_micros=1_000_000,
        )
    )


@pytest.fixture
async def client():
    app = create_app(
        UsageSettings(
            use_in_memory_store=True,
            default_limit_tokens=10_000,
            default_limit_usd_micros=1_000_000,
        )
    )
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as http,
        app.router.lifespan_context(app),
    ):
        yield http


def _headers(tenant_id=None, subject_id=None) -> dict[str, str]:
    return {
        "X-Tenant-Id": str(tenant_id or uuid4()),
        "X-Subject-Id": str(subject_id or uuid4()),
    }


@pytest.mark.asyncio
async def test_idempotent_ingest_and_summary(container) -> None:
    tenant_id = uuid4()
    cmd = IngestUsageCommand(
        tenant_id=tenant_id,
        category=UsageCategory.MODEL_TOKENS,
        quantity=100,
        unit=UsageUnit.TOKENS,
        price_version="price.v1",
        provider="openai",
        idempotency_key="evt-1",
        model="gpt-test",
    )
    first, created1 = await container.ingestor.ingest(cmd)
    second, created2 = await container.ingestor.ingest(cmd)
    assert created1 is True
    assert created2 is False
    assert first.id == second.id
    summary = await container.summary.summarize(tenant_id)
    assert summary.tokens_used == 100
    assert summary.by_category["model_tokens"] == 100


@pytest.mark.asyncio
async def test_hard_stop_budget(container) -> None:
    tenant_id = uuid4()
    await container.budgets.upsert(
        UpsertBudgetCommand(
            tenant_id=tenant_id,
            period=BudgetPeriod.MONTHLY,
            limit_usd_micros=1000,
            limit_tokens=500,
            hard_stop=True,
        )
    )
    with pytest.raises(BudgetExceededError):
        await container.ingestor.ingest(
            IngestUsageCommand(
                tenant_id=tenant_id,
                category=UsageCategory.MODEL_TOKENS,
                quantity=600,
                unit=UsageUnit.TOKENS,
                price_version="price.v1",
                provider="openai",
                idempotency_key="over",
            )
        )


@pytest.mark.asyncio
async def test_http_summary_and_budgets(client) -> None:
    headers = _headers()
    health = await client.get("/health")
    assert health.status_code == 200

    ingest = await client.post(
        "/v1/usage/events",
        headers=headers,
        json={
            "category": "model_tokens",
            "quantity": 250,
            "unit": "tokens",
            "provider": "openai",
            "idempotency_key": "http-1",
            "model": "gpt-test",
        },
    )
    assert ingest.status_code == 201

    replay = await client.post(
        "/v1/usage/events",
        headers=headers,
        json={
            "category": "model_tokens",
            "quantity": 250,
            "unit": "tokens",
            "provider": "openai",
            "idempotency_key": "http-1",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["created"] is False

    summary = await client.get("/v1/usage/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body.get("tokens_used", body.get("tokensUsed")) == 250

    budgets = await client.get("/v1/usage/budgets", headers=headers)
    assert budgets.status_code == 200
    assert len(budgets.json()["items"]) >= 1
