from __future__ import annotations

from uuid import UUID

from alama_common.pagination import decode_cursor, encode_cursor

from identity_service.domain.models import ApiKey, RoleBinding, Subject, Tenant


class InMemoryIdentityStore:
    """In-memory persistence for unit tests and local bootstrapping."""

    def __init__(self) -> None:
        self.tenants: dict[UUID, Tenant] = {}
        self.subjects: dict[UUID, Subject] = {}
        self.role_bindings: dict[UUID, RoleBinding] = {}
        self.api_keys: dict[UUID, ApiKey] = {}

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return self.tenants.get(tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        lowered = slug.lower()
        for tenant in self.tenants.values():
            if tenant.slug == lowered:
                return tenant
        return None

    async def save_tenant(self, tenant: Tenant) -> None:
        self.tenants[tenant.id] = tenant

    async def get_subject_by_id(self, subject_id: UUID) -> Subject | None:
        return self.subjects.get(subject_id)

    async def get_by_external_sub(self, tenant_id: UUID, external_idp_sub: str) -> Subject | None:
        for subject in self.subjects.values():
            if subject.tenant_id == tenant_id and subject.external_idp_sub == external_idp_sub:
                return subject
        return None

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Subject], str | None]:
        items = sorted(
            [s for s in self.subjects.values() if s.tenant_id == tenant_id],
            key=lambda s: s.created_at,
        )
        start = 0
        if cursor:
            payload = decode_cursor(cursor)
            cursor_id = str(payload["id"])
            for idx, subject in enumerate(items):
                if str(subject.id) == cursor_id:
                    start = idx + 1
                    break
        page = items[start : start + limit]
        next_cursor = None
        if start + limit < len(items):
            next_cursor = encode_cursor({"id": str(page[-1].id)})
        return page, next_cursor

    async def save_subject(self, subject: Subject) -> None:
        self.subjects[subject.id] = subject

    async def list_roles_for_subject(self, tenant_id: UUID, subject_id: UUID) -> list[str]:
        return [
            b.role
            for b in self.role_bindings.values()
            if b.tenant_id == tenant_id and b.subject_id == subject_id
        ]

    async def save_role_binding(self, binding: RoleBinding) -> None:
        self.role_bindings[binding.id] = binding

    async def get_api_key_by_id(self, tenant_id: UUID, api_key_id: UUID) -> ApiKey | None:
        key = self.api_keys.get(api_key_id)
        if key is None or key.tenant_id != tenant_id:
            return None
        return key

    async def save_api_key(self, api_key: ApiKey) -> None:
        self.api_keys[api_key.id] = api_key


class InMemoryTenantRepository:
    def __init__(self, store: InMemoryIdentityStore) -> None:
        self._store = store

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return await self._store.get_by_id(tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        return await self._store.get_by_slug(slug)

    async def save(self, tenant: Tenant) -> None:
        await self._store.save_tenant(tenant)


class InMemorySubjectRepository:
    def __init__(self, store: InMemoryIdentityStore) -> None:
        self._store = store

    async def get_by_id(self, subject_id: UUID) -> Subject | None:
        return await self._store.get_subject_by_id(subject_id)

    async def get_by_external_sub(self, tenant_id: UUID, external_idp_sub: str) -> Subject | None:
        return await self._store.get_by_external_sub(tenant_id, external_idp_sub)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[Subject], str | None]:
        return await self._store.list_by_tenant(tenant_id, limit=limit, cursor=cursor)

    async def save(self, subject: Subject) -> None:
        await self._store.save_subject(subject)


class InMemoryRoleBindingRepository:
    def __init__(self, store: InMemoryIdentityStore) -> None:
        self._store = store

    async def list_roles_for_subject(self, tenant_id: UUID, subject_id: UUID) -> list[str]:
        return await self._store.list_roles_for_subject(tenant_id, subject_id)

    async def save(self, binding: RoleBinding) -> None:
        await self._store.save_role_binding(binding)


class InMemoryApiKeyRepository:
    def __init__(self, store: InMemoryIdentityStore) -> None:
        self._store = store

    async def get_by_id(self, tenant_id: UUID, api_key_id: UUID) -> ApiKey | None:
        return await self._store.get_api_key_by_id(tenant_id, api_key_id)

    async def save(self, api_key: ApiKey) -> None:
        await self._store.save_api_key(api_key)
