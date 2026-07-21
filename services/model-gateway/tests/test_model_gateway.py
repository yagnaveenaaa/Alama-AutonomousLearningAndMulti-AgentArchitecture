from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from model_gateway.accounting.usage import InMemoryQuotaService, InMemoryUsageEmitter
from model_gateway.application.gateway import ModelGatewayService
from model_gateway.domain.models import (
    ChatMessage,
    ModelCapability,
    ModelProfile,
    ModelRequest,
    ModelTier,
)
from model_gateway.main import create_app
from model_gateway.policy.egress import EgressPolicy
from model_gateway.policy.redaction import RedactionFilter
from model_gateway.providers.deterministic import (
    DeterministicProviderAdapter,
    TransientFailThenOkAdapter,
)
from model_gateway.router.model_router import ModelRouter, ProviderRegistry
from model_gateway.templates.registry import InMemoryPromptTemplateRegistry


@pytest.mark.asyncio
async def test_complete_with_template_redacts_secrets_and_emits_usage() -> None:
    usage = InMemoryUsageEmitter()
    quotas = InMemoryQuotaService(tenant_token_quota=1_000_000)
    gateway = ModelGatewayService(
        router=ModelRouter(
            [
                ModelProfile(
                    name="alama-strong-v1",
                    provider="deterministic",
                    tier=ModelTier.STRONG,
                    capabilities=frozenset({ModelCapability.COMPLETE, ModelCapability.JSON}),
                    residency="any",
                    cost_per_1k_micros=1,
                    max_context_tokens=8_000,
                )
            ]
        ),
        providers=ProviderRegistry({"deterministic": DeterministicProviderAdapter()}),
        templates=InMemoryPromptTemplateRegistry(),
        usage=usage,
        quotas=quotas,
        redaction=RedactionFilter(),
        egress=EgressPolicy(),
    )
    tenant_id = uuid4()
    result = await gateway.complete(
        ModelRequest(
            tenant_id=tenant_id,
            task_id=uuid4(),
            purpose="plan",
            capability=ModelCapability.COMPLETE,
            preferred_tier=ModelTier.STRONG,
            residency="any",
            template_name="planner",
            template_version="v1",
            template_inputs={
                "objective": "Add auth",
                "repo_summary": "api_key=sk-supersecrettokenvalue",
            },
        )
    )
    assert result.parsed_json is not None
    assert result.parsed_json["objective"] == "Add auth"
    assert usage.records
    assert "[REDACTED]" in RedactionFilter().redact("api_key=sk-supersecrettokenvalue")


@pytest.mark.asyncio
async def test_embed_and_rerank() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        gateway = app.state.container.gateway
        tenant_id = uuid4()
        embedded = await gateway.embed(
            ModelRequest(
                tenant_id=tenant_id,
                task_id=None,
                purpose="index",
                capability=ModelCapability.EMBED,
                preferred_tier=ModelTier.EMBEDDING,
                residency="any",
                texts=("hello world", "auth token"),
            )
        )
        assert embedded.dimension == 64
        assert len(embedded.vectors) == 2

        ranked = await gateway.rerank(
            ModelRequest(
                tenant_id=tenant_id,
                task_id=None,
                purpose="retrieve",
                capability=ModelCapability.RERANK,
                preferred_tier=ModelTier.RERANK,
                residency="any",
                query="jwt auth",
                documents=("unrelated text", "jwt auth middleware"),
            )
        )
        assert ranked.ranked_indices[0] == 1


@pytest.mark.asyncio
async def test_fallback_on_transient_provider_error() -> None:
    primary = TransientFailThenOkAdapter(DeterministicProviderAdapter())
    secondary = DeterministicProviderAdapter()
    gateway = ModelGatewayService(
        router=ModelRouter(
            [
                ModelProfile(
                    name="primary",
                    provider="flaky",
                    tier=ModelTier.STRONG,
                    capabilities=frozenset({ModelCapability.COMPLETE}),
                    residency="any",
                    cost_per_1k_micros=1,
                    max_context_tokens=4_000,
                ),
                ModelProfile(
                    name="secondary",
                    provider="deterministic",
                    tier=ModelTier.MID,
                    capabilities=frozenset({ModelCapability.COMPLETE}),
                    residency="any",
                    cost_per_1k_micros=2,
                    max_context_tokens=4_000,
                ),
            ]
        ),
        providers=ProviderRegistry({"flaky": primary, "deterministic": secondary}),
        templates=InMemoryPromptTemplateRegistry(),
        usage=InMemoryUsageEmitter(),
        quotas=InMemoryQuotaService(tenant_token_quota=1_000_000),
        redaction=RedactionFilter(),
        egress=EgressPolicy(),
    )
    result = await gateway.complete(
        ModelRequest(
            tenant_id=uuid4(),
            task_id=None,
            purpose="chat",
            capability=ModelCapability.COMPLETE,
            preferred_tier=ModelTier.STRONG,
            residency="any",
            messages=(ChatMessage(role="user", content="hello"),),
        )
    )
    assert result.fallback_used is True
    assert result.provider == "deterministic"


def test_http_complete_contract() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/complete",
            headers={"X-Tenant-Id": str(uuid4())},
            json={
                "purpose": "plan",
                "template_name": "planner",
                "template_inputs": {"objective": "Ship feature", "repo_summary": "ok"},
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["parsed_json"]["objective"] == "Ship feature"
        assert body["input_tokens"] >= 1
