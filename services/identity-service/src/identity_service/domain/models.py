from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from alama_common.ids import new_uuid7


class IsolationTier(StrEnum):
    SHARED = "shared"
    DEDICATED = "dedicated"


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_DELETE = "pending_delete"


class SubjectStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class Tenant:
    """Aggregate root for an organization (LLD §4.3 tenants)."""

    def __init__(
        self,
        *,
        id: UUID,
        slug: str,
        name: str,
        home_region: str,
        home_cell: str,
        isolation_tier: IsolationTier,
        plan: str,
        status: TenantStatus,
        data_residency: str,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
    ) -> None:
        self.id = id
        self.slug = slug.lower()
        self.name = name
        self.home_region = home_region
        self.home_cell = home_cell
        self.isolation_tier = isolation_tier
        self.plan = plan
        self.status = status
        self.data_residency = data_residency
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version

    @classmethod
    def create(
        cls,
        *,
        slug: str,
        name: str,
        home_region: str,
        home_cell: str,
        isolation_tier: IsolationTier,
        plan: str,
        data_residency: str,
    ) -> Tenant:
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            slug=slug,
            name=name,
            home_region=home_region,
            home_cell=home_cell,
            isolation_tier=isolation_tier,
            plan=plan,
            status=TenantStatus.ACTIVE,
            data_residency=data_residency,
            created_at=now,
            updated_at=now,
            version=1,
        )

    def suspend(self) -> None:
        if self.status == TenantStatus.PENDING_DELETE:
            from alama_common.errors import DomainInvariantError

            raise DomainInvariantError("Cannot suspend a tenant pending deletion")
        self.status = TenantStatus.SUSPENDED
        self.updated_at = datetime.now(UTC)
        self.version += 1


class Subject:
    """Authenticated user projection within a tenant (LLD §4.3 subjects)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        external_idp_sub: str,
        email: str | None,
        display_name: str | None,
        status: SubjectStatus,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.external_idp_sub = external_idp_sub
        self.email = email.lower() if email else None
        self.display_name = display_name
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version

    @classmethod
    def create(
        cls,
        *,
        tenant_id: UUID,
        external_idp_sub: str,
        email: str | None = None,
        display_name: str | None = None,
    ) -> Subject:
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            external_idp_sub=external_idp_sub,
            email=email,
            display_name=display_name,
            status=SubjectStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            version=1,
        )

    def disable(self) -> None:
        self.status = SubjectStatus.DISABLED
        self.updated_at = datetime.now(UTC)
        self.version += 1


class RoleBinding:
    """RBAC binding to a subject or group (LLD §4.3 role_bindings)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        role: str,
        subject_id: UUID | None,
        group_id: UUID | None,
        resource_scope: dict[str, object],
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
    ) -> None:
        if (subject_id is None) == (group_id is None):
            from alama_common.errors import DomainInvariantError

            raise DomainInvariantError("Exactly one of subject_id or group_id must be set")
        self.id = id
        self.tenant_id = tenant_id
        self.role = role
        self.subject_id = subject_id
        self.group_id = group_id
        self.resource_scope = resource_scope
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version

    @classmethod
    def for_subject(
        cls,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        role: str,
        resource_scope: dict[str, object] | None = None,
    ) -> RoleBinding:
        now = datetime.now(UTC)
        return cls(
            id=new_uuid7(),
            tenant_id=tenant_id,
            role=role,
            subject_id=subject_id,
            group_id=None,
            resource_scope=resource_scope or {},
            created_at=now,
            updated_at=now,
            version=1,
        )


class ApiKey:
    """Hashed personal/service API key metadata (LLD §4.3 api_keys)."""

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        subject_id: UUID,
        name: str,
        key_prefix: str,
        key_hash: bytes,
        scopes: tuple[str, ...],
        expires_at: datetime | None,
        revoked_at: datetime | None,
        last_used_at: datetime | None,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.subject_id = subject_id
        self.name = name
        self.key_prefix = key_prefix
        self.key_hash = key_hash
        self.scopes = scopes
        self.expires_at = expires_at
        self.revoked_at = revoked_at
        self.last_used_at = last_used_at
        self.created_at = created_at
        self.updated_at = updated_at
        self.version = version

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return not (self.expires_at is not None and self.expires_at <= datetime.now(UTC))

    def revoke(self) -> None:
        if self.revoked_at is not None:
            from alama_common.errors import ConflictError

            raise ConflictError("API key already revoked")
        self.revoked_at = datetime.now(UTC)
        self.updated_at = self.revoked_at
        self.version += 1
