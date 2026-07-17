from __future__ import annotations

import base64
import json
from dataclasses import dataclass

DEFAULT_PAGE_LIMIT = 25
MAX_PAGE_LIMIT = 100


@dataclass(frozen=True, slots=True)
class CursorPage[T]:
    """Cursor pagination response shape (LLD §5.1)."""

    items: list[T]
    next_cursor: str | None


def encode_cursor(payload: dict[str, str | int]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> dict[str, str | int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        msg = "Invalid pagination cursor"
        raise ValueError(msg) from exc
    if not isinstance(data, dict):
        msg = "Invalid pagination cursor payload"
        raise TypeError(msg)
    return data
