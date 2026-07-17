from __future__ import annotations

import pytest

from identity_service.application.dto import CreateTenantCommand, ScimUserUpsertCommand
from identity_service.container import build_container
from identity_service.domain.models import IsolationTier, SubjectStatus


@pytest.mark.asyncio
async def test_scim_upsert_creates_and_disables() -> None:
    container = build_container()
    tenant = await container.create_tenant.handle(
        CreateTenantCommand(
            slug="scim",
            name="SCIM Co",
            home_region="us-east-1",
            home_cell="cell-use1-a",
            isolation_tier=IsolationTier.SHARED,
            plan="free",
            data_residency="us",
            owner_external_idp_sub="idp|owner",
        )
    )

    user = await container.scim_sync.upsert_user(
        ScimUserUpsertCommand(
            tenant_id=tenant.id,
            external_idp_sub="idp|alice",
            email="alice@scim.test",
            display_name="Alice",
            active=True,
        )
    )
    assert user.status == SubjectStatus.ACTIVE

    disabled = await container.scim_sync.upsert_user(
        ScimUserUpsertCommand(
            tenant_id=tenant.id,
            external_idp_sub="idp|alice",
            email="alice@scim.test",
            display_name="Alice",
            active=False,
        )
    )
    assert disabled.status == SubjectStatus.DISABLED
