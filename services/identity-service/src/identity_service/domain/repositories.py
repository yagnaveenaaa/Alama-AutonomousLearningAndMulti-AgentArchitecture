from __future__ import annotations

from typing import Protocol
from uuid import UUID

from identity_service.domain.models import ApiKey, RoleBinding, Subject, Tenant


class TenantRepository(Protocol):
    async def get_by_id(self, tenant_id: UUID) -> Tenant | None: ...

    async def get_by_slug(self, slug: str) -> Tenant | None: ...

    async def save(self, tenant: Tenant) -> None: ...


class SubjectRepository(Protocol):
    async def get_by_id(self, subject_id: UUID) -> Subject | None: ...

    async def get_by_external_sub(
        self,
        tenant_id: UUID,
        external_idp_sub: str,
    ) -> Subject | None: ...

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Subject], str | None]: ...

    async def save(self, subject: Subject) -> None: ...


class RoleBindingRepository(Protocol):
    async def list_roles_for_subject(self, tenant_id: UUID, subject_id: UUID) -> list[str]: ...

    async def save(self, binding: RoleBinding) -> None: ...


class ApiKeyRepository(Protocol):
    async def get_by_id(self, tenant_id: UUID, api_key_id: UUID) -> ApiKey | None: ...

    async def save(self, api_key: ApiKey) -> None: ...
