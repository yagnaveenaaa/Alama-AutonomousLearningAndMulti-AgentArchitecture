from __future__ import annotations

from alama_common.errors import ConflictError, ValidationError

from identity_service.application.dto import CreateTenantCommand
from identity_service.domain.membership import MembershipService
from identity_service.domain.models import RoleBinding, Tenant
from identity_service.domain.repositories import RoleBindingRepository, TenantRepository

DEFAULT_OWNER_ROLE = "owner"


class CreateTenantHandler:
    """Provision tenant + default owner role + cell placement fields (LLD §2.3)."""

    def __init__(
        self,
        tenants: TenantRepository,
        memberships: MembershipService,
        role_bindings: RoleBindingRepository,
    ) -> None:
        self._tenants = tenants
        self._memberships = memberships
        self._role_bindings = role_bindings

    async def handle(self, command: CreateTenantCommand) -> Tenant:
        slug = command.slug.strip().lower()
        if not slug or not command.name.strip():
            raise ValidationError("slug and name are required")

        existing = await self._tenants.get_by_slug(slug)
        if existing is not None:
            raise ConflictError("Tenant slug already exists", details={"slug": slug})

        tenant = Tenant.create(
            slug=slug,
            name=command.name.strip(),
            home_region=command.home_region,
            home_cell=command.home_cell,
            isolation_tier=command.isolation_tier,
            plan=command.plan,
            data_residency=command.data_residency,
        )
        await self._tenants.save(tenant)

        owner = await self._memberships.add_subject(
            tenant_id=tenant.id,
            external_idp_sub=command.owner_external_idp_sub,
            email=command.owner_email,
            display_name=command.owner_display_name,
        )

        binding = RoleBinding.for_subject(
            tenant_id=tenant.id,
            subject_id=owner.id,
            role=DEFAULT_OWNER_ROLE,
        )
        await self._role_bindings.save(binding)
        return tenant
