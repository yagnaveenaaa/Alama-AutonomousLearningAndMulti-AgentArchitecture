from __future__ import annotations

import pytest

from alama_common.pagination.cursor import decode_cursor, encode_cursor


def test_cursor_round_trip() -> None:
    payload = {"id": "abc", "created_at": 123}
    cursor = encode_cursor(payload)
    assert decode_cursor(cursor) == payload


def test_cursor_decode_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        decode_cursor("not-a-valid-cursor")
