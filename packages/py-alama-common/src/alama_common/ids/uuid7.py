from __future__ import annotations

from uuid import UUID

from uuid6 import uuid7


def new_uuid7() -> UUID:
    """Generate a time-sortable UUIDv7 identifier (LLD §4.1)."""
    return uuid7()
