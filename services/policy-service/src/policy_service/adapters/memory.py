from __future__ import annotations

from uuid import UUID

from alama_common.errors import ConflictError

from policy_service.domain.models import BundleStatus, PolicyBundle
from policy_service.engine.defaults import build_default_bundle, rules_to_payload


class InMemoryBundleStore:
    """Object-storage stand-in for immutable bundle JSON (LLD §2.6)."""

    def __init__(self) -> None:
        self._objects: dict[str, dict[str, object]] = {}

    async def put(self, bundle_ref: str, payload: dict[str, object]) -> str:
        self._objects[bundle_ref] = dict(payload)
        return bundle_ref

    async def get(self, bundle_ref: str) -> dict[str, object] | None:
        payload = self._objects.get(bundle_ref)
        return dict(payload) if payload is not None else None


class InMemoryPolicyBundleRepository:
    def __init__(self, store: InMemoryBundleStore | None = None) -> None:
        self._bundles: dict[tuple[UUID, str], PolicyBundle] = {}
        self._store = store or InMemoryBundleStore()

    async def get_by_version(self, tenant_id: UUID, version: str) -> PolicyBundle | None:
        return self._bundles.get((tenant_id, version))

    async def get_active(self, tenant_id: UUID) -> PolicyBundle | None:
        for bundle in self._bundles.values():
            if bundle.tenant_id == tenant_id and bundle.status == BundleStatus.ACTIVE:
                return bundle
        return None

    async def list_for_tenant(self, tenant_id: UUID) -> list[PolicyBundle]:
        return [b for b in self._bundles.values() if b.tenant_id == tenant_id]

    async def save(self, bundle: PolicyBundle) -> None:
        if bundle.status == BundleStatus.ACTIVE:
            for other in list(self._bundles.values()):
                if (
                    other.tenant_id == bundle.tenant_id
                    and other.status == BundleStatus.ACTIVE
                    and other.version != bundle.version
                ):
                    raise ConflictError("Tenant already has an active policy bundle")
        payload = rules_to_payload(bundle.rules)
        await self._store.put(bundle.bundle_ref, payload)
        self._bundles[(bundle.tenant_id, bundle.version)] = bundle

    async def ensure_default(self, tenant_id: UUID, version: str) -> PolicyBundle:
        active = await self.get_active(tenant_id)
        if active is not None:
            return active
        existing = await self.get_by_version(tenant_id, version)
        if existing is not None:
            existing.activate()
            await self.save(existing)
            return existing
        bundle = build_default_bundle(tenant_id=tenant_id, version=version)
        bundle.activate()
        await self.save(bundle)
        return bundle
