from __future__ import annotations

from dataclasses import dataclass

from model_gateway.accounting.usage import InMemoryQuotaService, InMemoryUsageEmitter
from model_gateway.application.gateway import ModelGatewayService
from model_gateway.config import ModelGatewaySettings
from model_gateway.domain.models import ModelCapability, ModelProfile, ModelTier
from model_gateway.policy.egress import EgressPolicy
from model_gateway.policy.redaction import RedactionFilter
from model_gateway.providers.deterministic import DeterministicProviderAdapter
from model_gateway.router.model_router import ModelRouter, ProviderRegistry
from model_gateway.templates.registry import InMemoryPromptTemplateRegistry


@dataclass
class ModelGatewayContainer:
    settings: ModelGatewaySettings
    gateway: ModelGatewayService
    usage: InMemoryUsageEmitter
    quotas: InMemoryQuotaService
    templates: InMemoryPromptTemplateRegistry


def default_profiles(settings: ModelGatewaySettings) -> list[ModelProfile]:
    return [
        ModelProfile(
            name=settings.default_completion_model,
            provider="deterministic",
            tier=ModelTier.STRONG,
            capabilities=frozenset(
                {ModelCapability.COMPLETE, ModelCapability.JSON}
            ),
            residency="any",
            cost_per_1k_micros=500,
            max_context_tokens=128_000,
        ),
        ModelProfile(
            name="alama-mid-v1",
            provider="deterministic",
            tier=ModelTier.MID,
            capabilities=frozenset({ModelCapability.COMPLETE, ModelCapability.JSON}),
            residency="any",
            cost_per_1k_micros=100,
            max_context_tokens=64_000,
        ),
        ModelProfile(
            name=settings.default_embedding_model,
            provider="deterministic",
            tier=ModelTier.EMBEDDING,
            capabilities=frozenset({ModelCapability.EMBED}),
            residency="any",
            cost_per_1k_micros=20,
            max_context_tokens=8_192,
        ),
        ModelProfile(
            name=settings.default_rerank_model,
            provider="deterministic",
            tier=ModelTier.RERANK,
            capabilities=frozenset({ModelCapability.RERANK}),
            residency="any",
            cost_per_1k_micros=50,
            max_context_tokens=8_192,
        ),
    ]


def build_container(settings: ModelGatewaySettings | None = None) -> ModelGatewayContainer:
    settings = settings or ModelGatewaySettings()
    provider = DeterministicProviderAdapter(embedding_dim=settings.embedding_dim)
    usage = InMemoryUsageEmitter()
    quotas = InMemoryQuotaService(tenant_token_quota=settings.tenant_token_quota)
    templates = InMemoryPromptTemplateRegistry()
    gateway = ModelGatewayService(
        router=ModelRouter(default_profiles(settings)),
        providers=ProviderRegistry({"deterministic": provider}),
        templates=templates,
        usage=usage,
        quotas=quotas,
        redaction=RedactionFilter(),
        egress=EgressPolicy(allow_provider_training=settings.allow_provider_training),
    )
    return ModelGatewayContainer(
        settings=settings,
        gateway=gateway,
        usage=usage,
        quotas=quotas,
        templates=templates,
    )
