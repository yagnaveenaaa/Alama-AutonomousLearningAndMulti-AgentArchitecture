from __future__ import annotations

import pytest

from identity_service.application.dto import CreateApiKeyCommand, CreateTenantCommand
from identity_service.container import build_container
from identity_service.domain.models import IsolationTier


@pytest.mark.asyncio
async def test_issue_and_verify_api_key() -> None:
    container = build_container()
    tenant = await container.create_tenant.handle(
        CreateTenantCommand(
            slug="keys",
            name="Keys Co",
            home_region="eu-west-1",
            home_cell="cell-euw1-a",
            isolation_tier=IsolationTier.SHARED,
            plan="pro",
            data_residency="eu",
            owner_external_idp_sub="idp|key-owner",
        )
    )
    subjects, _ = await container.subjects.list_by_tenant(tenant.id, limit=1, cursor=None)
    subject = subjects[0]

    issued = await container.api_key_service.issue(
        CreateApiKeyCommand(
            tenant_id=tenant.id,
            subject_id=subject.id,
            name="ci",
            scopes=("repos:read", "tasks:write"),
        )
    )
    assert issued.plaintext_key.startswith(issued.key_prefix + ".")
    assert "repos:read" in issued.scopes

    stored = await container.api_keys.get_by_id(tenant.id, issued.id)
    assert stored is not None
    assert stored.is_active
    assert container.api_key_service.verify_plaintext(stored, issued.plaintext_key)
    assert not container.api_key_service.verify_plaintext(stored, "wrong")


@pytest.mark.asyncio
async def test_revoke_api_key() -> None:
    container = build_container()
    tenant = await container.create_tenant.handle(
        CreateTenantCommand(
            slug="revoke",
            name="Revoke Co",
            home_region="us-east-1",
            home_cell="cell-use1-a",
            isolation_tier=IsolationTier.SHARED,
            plan="free",
            data_residency="us",
            owner_external_idp_sub="idp|rev",
        )
    )
    subjects, _ = await container.subjects.list_by_tenant(tenant.id, limit=1, cursor=None)
    subject = subjects[0]
    issued = await container.api_key_service.issue(
        CreateApiKeyCommand(
            tenant_id=tenant.id,
            subject_id=subject.id,
            name="tmp",
            scopes=("identity:read",),
        )
    )
    await container.api_key_service.revoke(
        tenant_id=tenant.id,
        api_key_id=issued.id,
        actor_subject_id=subject.id,
    )
    stored = await container.api_keys.get_by_id(tenant.id, issued.id)
    assert stored is not None
    assert not stored.is_active
