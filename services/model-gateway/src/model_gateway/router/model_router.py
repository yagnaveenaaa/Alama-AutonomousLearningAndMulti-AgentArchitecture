from __future__ import annotations

from alama_common.errors import DependencyFatalError, NotFoundError

from model_gateway.domain.models import ModelCapability, ModelProfile, ModelRequest, ModelTier


class ModelRouter:
    """Choose model for ModelRequest by capability/cost/residency (LLD §2.9)."""

    def __init__(self, profiles: list[ModelProfile]) -> None:
        if not profiles:
            raise ValueError("at least one model profile is required")
        self._profiles = list(profiles)

    def route(self, request: ModelRequest) -> tuple[ModelProfile, list[ModelProfile]]:
        eligible = [
            profile
            for profile in self._profiles
            if request.capability in profile.capabilities
            and (profile.residency == request.residency or profile.residency == "any")
            and self._tier_ok(profile.tier, request.preferred_tier, request.capability)
        ]
        if not eligible:
            raise NotFoundError(
                "No model matches request constraints",
                details={
                    "capability": request.capability.value,
                    "tier": request.preferred_tier.value,
                    "residency": request.residency,
                },
            )
        eligible.sort(key=lambda p: (p.cost_per_1k_micros, -p.max_context_tokens))
        primary = eligible[0]
        fallbacks = eligible[1:]
        return primary, fallbacks

    @staticmethod
    def _tier_ok(
        profile_tier: ModelTier,
        preferred: ModelTier,
        capability: ModelCapability,
    ) -> bool:
        if capability == ModelCapability.EMBED:
            return profile_tier == ModelTier.EMBEDDING
        if capability == ModelCapability.RERANK:
            return profile_tier == ModelTier.RERANK
        if preferred == ModelTier.STRONG:
            return profile_tier in {ModelTier.STRONG, ModelTier.MID}
        return profile_tier == preferred or profile_tier == ModelTier.MID


class ProviderRegistry:
    def __init__(self, adapters: dict[str, object]) -> None:
        self._adapters = adapters

    def get(self, provider: str) -> object:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise DependencyFatalError(f"Unknown provider adapter: {provider}")
        return adapter
