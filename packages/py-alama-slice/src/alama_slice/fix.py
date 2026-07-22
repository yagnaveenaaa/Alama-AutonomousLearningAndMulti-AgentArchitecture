"""Fixed auth.py content emitted by the slice model for the demo fixture."""

FIXED_AUTH_PY = '''\
"""Tiny auth helper — fixed token verification."""

from __future__ import annotations


def authenticate(token: str | None) -> dict[str, object]:
    """Return a principal for a bearer token."""
    if token is None or not str(token).strip():
        raise ValueError("missing token")
    if token == "invalid":
        raise ValueError("invalid token")
    return {"sub": "user", "ok": True}


def require_auth(token: str | None) -> dict[str, object]:
    principal = authenticate(token)
    if not principal.get("ok"):
        raise PermissionError("unauthorized")
    return principal
'''
