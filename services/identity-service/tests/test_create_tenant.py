from __future__ import annotations

import pytest

from identity_service.application.dto import CreateTenantCommand
from identity_service.container import build_container
from identity_service.domain.models import IsolationTier


@pytest.mark.asyncio
async def test_create_tenant_provisions_owner_and_role() -> None:
    container = build_container()
    tenant = await container.create_tenant.handle(
        CreateTenantCommand(
            slug="acme",
            name="Acme Corp",
            home_region="us-east-1",
            home_cell="cell-use1-a",
            isolation_tier=IsolationTier.SHARED,
            plan="enterprise",
            data_residency="us",
            owner_external_idp_sub="idp|owner-1",
            owner_email="owner@acme.test",
            owner_display_name="Owner",
        )
    )

    assert tenant.slug == "acme"
    assert tenant.home_cell == "cell-use1-a"

    subjects, _ = await container.subjects.list_by_tenant(tenant.id, limit=10, cursor=None)
    assert len(subjects) == 1
    assert subjects[0].external_idp_sub == "idp|owner-1"

    roles = await container.role_bindings.list_roles_for_subject(tenant.id, subjects[0].id)
    assert roles == ["owner"]


@pytest.mark.asyncio
async def test_create_tenant_rejects_duplicate_slug() -> None:
    from alama_common.errors import ConflictError

    container = build_container()
    command = CreateTenantCommand(
        slug="dup",
        name="One",
        home_region="us-east-1",
        home_cell="cell-use1-a",
        isolation_tier=IsolationTier.SHARED,
        plan="free",
        data_residency="us",
        owner_external_idp_sub="idp|a",
    )
    await container.create_tenant.handle(command)
    with pytest.raises(ConflictError):
        await container.create_tenant.handle(
            CreateTenantCommand(
                slug="dup",
                name="Two",
                home_region="us-east-1",
                home_cell="cell-use1-a",
                isolation_tier=IsolationTier.SHARED,
                plan="free",
                data_residency="us",
                owner_external_idp_sub="idp|b",
            )
        )
