from __future__ import annotations

from dataclasses import dataclass

from policy_service.adapters.memory import InMemoryBundleStore, InMemoryPolicyBundleRepository
from policy_service.application.handlers import (
    ActivateBundleHandler,
    EvaluatePolicyHandler,
    ListBundlesHandler,
    UpsertDraftBundleHandler,
)
from policy_service.config import PolicySettings
from policy_service.engine.cedar_engine import CedarStylePolicyEngine


@dataclass
class PolicyContainer:
    bundles: InMemoryPolicyBundleRepository
    bundle_store: InMemoryBundleStore
    engine: CedarStylePolicyEngine
    evaluate: EvaluatePolicyHandler
    activate: ActivateBundleHandler
    list_bundles: ListBundlesHandler
    upsert_draft: UpsertDraftBundleHandler


def build_container(settings: PolicySettings | None = None) -> PolicyContainer:
    settings = settings or PolicySettings()
    store = InMemoryBundleStore()
    bundles = InMemoryPolicyBundleRepository(store)
    engine = CedarStylePolicyEngine()
    return PolicyContainer(
        bundles=bundles,
        bundle_store=store,
        engine=engine,
        evaluate=EvaluatePolicyHandler(
            bundles,
            engine,
            default_version=settings.default_bundle_version,
            ensure_default=True,
        ),
        activate=ActivateBundleHandler(bundles),
        list_bundles=ListBundlesHandler(bundles),
        upsert_draft=UpsertDraftBundleHandler(bundles),
    )
