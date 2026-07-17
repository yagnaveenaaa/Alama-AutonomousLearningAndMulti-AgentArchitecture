from __future__ import annotations

from uuid import UUID

import pytest

from alama_common.auth.principal import Principal
from alama_common.ids.uuid7 import new_uuid7


def test_principal_scope_and_tenant_access() -> None:
    tenant_a = new_uuid7()
    tenant_b = new_uuid7()
    subject_id = new_uuid7()

    principal = Principal(
        subject_id=subject_id,
        tenant_ids=(tenant_a, tenant_b),
        scopes=frozenset({"tasks:read", "tasks:write"}),
        session_id=new_uuid7(),
    )

    assert principal.has_scope("tasks:read")
    assert not principal.has_scope("admin")
    assert principal.can_access_tenant(tenant_a)
    assert principal.primary_tenant_id() == tenant_a


def test_principal_requires_tenant_for_primary() -> None:
    principal = Principal(
        subject_id=new_uuid7(),
        tenant_ids=(),
        scopes=frozenset(),
    )
    with pytest.raises(ValueError, match="no tenant"):
        principal.primary_tenant_id()


def test_principal_is_immutable() -> None:
    principal = Principal(
        subject_id=new_uuid7(),
        tenant_ids=(new_uuid7(),),
        scopes=frozenset({"x"}),
    )
    with pytest.raises((AttributeError, TypeError)):
        principal.subject_id = UUID(int=0)  # type: ignore[misc]
