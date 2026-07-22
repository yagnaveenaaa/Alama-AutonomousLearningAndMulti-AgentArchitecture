"""Tiny auth helper with an intentional verification bug (vertical-slice demo)."""

from __future__ import annotations


def authenticate(token: str | None) -> dict[str, object]:
    """Return a principal for a bearer token.

    BUG: empty / whitespace tokens are treated as authenticated anonymous users.
    """
    if token is None:
        return {"sub": "anonymous", "ok": True}
    # Missing strip + empty check — "" and "   " incorrectly succeed.
    if token == "invalid":
        raise ValueError("invalid token")
    return {"sub": "user", "ok": True}


def require_auth(token: str | None) -> dict[str, object]:
    principal = authenticate(token)
    if not principal.get("ok"):
        raise PermissionError("unauthorized")
    return principal
