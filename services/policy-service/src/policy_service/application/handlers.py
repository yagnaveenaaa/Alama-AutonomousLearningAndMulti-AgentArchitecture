from __future__ import annotations

from uuid import UUID

from alama_common.errors import NotFoundError, ValidationError

from policy_service.application.dto import (
    ActivateBundleCommand,
    EvaluatePolicyCommand,
    UpsertDraftBundleCommand,
)
from policy_service.domain.models import (
    BundleStatus,
    PolicyBundle,
    PolicyDecision,
    PolicyInput,
)
from policy_service.domain.repositories import PolicyBundleRepository, PolicyEngine
from policy_service.engine.defaults import (
    build_default_bundle,
    rules_checksum,
    rules_from_payload,
)


class EvaluatePolicyHandler:
    """Admission + tool-time evaluation (LLD §2.6)."""

    def __init__(
        self,
        bundles: PolicyBundleRepository,
        engine: PolicyEngine,
        *,
        default_version: str,
        ensure_default: bool = True,
    ) -> None:
        self._bundles = bundles
        self._engine = engine
        self._default_version = default_version
        self._ensure_default = ensure_default

    async def handle(self, command: EvaluatePolicyCommand) -> PolicyDecision:
        bundle = await self._resolve_bundle(command.tenant_id, command.policy_version)
        return self._engine.evaluate(
            bundle,
            PolicyInput(
                tenant_id=command.tenant_id,
                subject_id=command.subject_id,
                action=command.action,
                attributes=dict(command.attributes),
            ),
        )

    async def _resolve_bundle(
        self, tenant_id: UUID, version: str | None
    ) -> PolicyBundle:
        if version:
            bundle = await self._bundles.get_by_version(tenant_id, version)
            if bundle is None:
                raise NotFoundError(f"Policy bundle {version} not found")
            return bundle

        bundle = await self._bundles.get_active(tenant_id)
        if bundle is not None:
            return bundle
        if not self._ensure_default:
            raise NotFoundError("No active policy bundle")
        seeded = build_default_bundle(tenant_id=tenant_id, version=self._default_version)
        seeded.activate()
        await self._bundles.save(seeded)
        return seeded


class ActivateBundleHandler:
    def __init__(self, bundles: PolicyBundleRepository) -> None:
        self._bundles = bundles

    async def handle(self, command: ActivateBundleCommand) -> PolicyBundle:
        target = await self._bundles.get_by_version(command.tenant_id, command.version)
        if target is None:
            raise NotFoundError(f"Policy bundle {command.version} not found")

        current = await self._bundles.get_active(command.tenant_id)
        if current is not None and current.version != target.version:
            current.retire()
            await self._bundles.save(current)

        target.activate()
        await self._bundles.save(target)
        return target


class ListBundlesHandler:
    def __init__(self, bundles: PolicyBundleRepository) -> None:
        self._bundles = bundles

    async def handle(self, tenant_id: UUID) -> list[PolicyBundle]:
        items = await self._bundles.list_for_tenant(tenant_id)
        return sorted(items, key=lambda b: b.version)


class UpsertDraftBundleHandler:
    def __init__(self, bundles: PolicyBundleRepository) -> None:
        self._bundles = bundles

    async def handle(self, command: UpsertDraftBundleCommand) -> PolicyBundle:
        rules = rules_from_payload(command.rules_payload)
        if not rules:
            raise ValidationError("rules payload must contain at least one rule")
        checksum = rules_checksum(rules)
        existing = await self._bundles.get_by_version(command.tenant_id, command.version)
        if existing is not None:
            if existing.status == BundleStatus.ACTIVE:
                raise ValidationError(
                    "Cannot overwrite an active bundle; create a new version"
                )
            bundle = PolicyBundle(
                id=existing.id,
                tenant_id=existing.tenant_id,
                version=existing.version,
                bundle_ref=existing.bundle_ref,
                checksum=checksum,
                status=BundleStatus.DRAFT,
                rules=rules,
                created_at=existing.created_at,
                activated_at=None,
            )
            await self._bundles.save(bundle)
            return bundle

        bundle = PolicyBundle.create(
            tenant_id=command.tenant_id,
            version=command.version,
            rules=rules,
            checksum=checksum,
            status=BundleStatus.DRAFT,
        )
        await self._bundles.save(bundle)
        return bundle
