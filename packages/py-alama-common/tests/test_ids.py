from __future__ import annotations

from uuid import UUID

from alama_common.ids.uuid7 import new_uuid7


def test_new_uuid7_returns_uuid() -> None:
    value = new_uuid7()
    assert isinstance(value, UUID)
    assert value.version == 7
