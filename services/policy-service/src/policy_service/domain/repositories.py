from __future__ import annotations

from typing import Protocol
from uuid import UUID

from policy_service.domain.models import PolicyBundle, PolicyDecision, PolicyInput


class PolicyBundleRepository(Protocol):
    async def get_by_version(self, tenant_id: UUID, version: str) -> PolicyBundle | None: ...

    async def get_active(self, tenant_id: UUID) -> PolicyBundle | None: ...

    async def list_for_tenant(self, tenant_id: UUID) -> list[PolicyBundle]: ...

    async def save(self, bundle: PolicyBundle) -> None: ...


class PolicyEngine(Protocol):
    def evaluate(self, bundle: PolicyBundle, input: PolicyInput) -> PolicyDecision: ...


class BundleStore(Protocol):
    async def put(self, bundle_ref: str, payload: dict[str, object]) -> str: ...

    async def get(self, bundle_ref: str) -> dict[str, object] | None: ...
