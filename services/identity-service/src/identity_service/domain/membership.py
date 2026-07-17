from __future__ import annotations

from uuid import UUID

from alama_common.errors import ConflictError, NotFoundError, ValidationError

from identity_service.domain.models import Subject, Tenant, TenantStatus
from identity_service.domain.repositories import SubjectRepository, TenantRepository


class MembershipService:
    """Enforce single-home-cell membership rules (LLD §2.3)."""

    def __init__(
        self,
        tenants: TenantRepository,
        subjects: SubjectRepository,
    ) -> None:
        self._tenants = tenants
        self._subjects = subjects

    async def ensure_tenant_active(self, tenant_id: UUID) -> Tenant:
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError("Tenant not found", details={"tenant_id": str(tenant_id)})
        if tenant.status != TenantStatus.ACTIVE:
            raise ConflictError(
                "Tenant is not active",
                details={"tenant_id": str(tenant_id), "status": tenant.status.value},
            )
        return tenant

    async def add_subject(
        self,
        *,
        tenant_id: UUID,
        external_idp_sub: str,
        email: str | None = None,
        display_name: str | None = None,
    ) -> Subject:
        if not external_idp_sub.strip():
            raise ValidationError("external_idp_sub is required")

        await self.ensure_tenant_active(tenant_id)

        existing = await self._subjects.get_by_external_sub(tenant_id, external_idp_sub)
        if existing is not None:
            raise ConflictError(
                "Subject already exists for IdP subject",
                details={"external_idp_sub": external_idp_sub},
            )

        subject = Subject.create(
            tenant_id=tenant_id,
            external_idp_sub=external_idp_sub,
            email=email,
            display_name=display_name,
        )
        await self._subjects.save(subject)
        return subject
