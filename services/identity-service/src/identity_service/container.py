from __future__ import annotations

from dataclasses import dataclass

from identity_service.adapters.persistence.memory import (
    InMemoryApiKeyRepository,
    InMemoryIdentityStore,
    InMemoryRoleBindingRepository,
    InMemorySubjectRepository,
    InMemoryTenantRepository,
)
from identity_service.application.api_keys import ApiKeyService
from identity_service.application.create_tenant import CreateTenantHandler
from identity_service.application.scim_sync import ScimSyncHandler
from identity_service.domain.membership import MembershipService


@dataclass
class IdentityContainer:
    store: InMemoryIdentityStore
    tenants: InMemoryTenantRepository
    subjects: InMemorySubjectRepository
    role_bindings: InMemoryRoleBindingRepository
    api_keys: InMemoryApiKeyRepository
    memberships: MembershipService
    create_tenant: CreateTenantHandler
    api_key_service: ApiKeyService
    scim_sync: ScimSyncHandler


def build_container() -> IdentityContainer:
    store = InMemoryIdentityStore()
    tenants = InMemoryTenantRepository(store)
    subjects = InMemorySubjectRepository(store)
    role_bindings = InMemoryRoleBindingRepository(store)
    api_keys = InMemoryApiKeyRepository(store)
    memberships = MembershipService(tenants, subjects)
    return IdentityContainer(
        store=store,
        tenants=tenants,
        subjects=subjects,
        role_bindings=role_bindings,
        api_keys=api_keys,
        memberships=memberships,
        create_tenant=CreateTenantHandler(tenants, memberships, role_bindings),
        api_key_service=ApiKeyService(api_keys, subjects, memberships),
        scim_sync=ScimSyncHandler(subjects, memberships),
    )
