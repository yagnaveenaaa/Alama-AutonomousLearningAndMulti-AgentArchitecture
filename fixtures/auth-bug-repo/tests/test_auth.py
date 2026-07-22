"""Expected auth behavior — currently fails against the buggy implementation."""

from __future__ import annotations

import pytest

from auth import authenticate, require_auth


def test_valid_token_authenticates() -> None:
    principal = authenticate("tok_live_abc")
    assert principal["ok"] is True
    assert principal["sub"] == "user"


def test_none_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing token"):
        authenticate(None)


def test_empty_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing token"):
        authenticate("")


def test_whitespace_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing token"):
        authenticate("   ")


def test_invalid_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid token"):
        authenticate("invalid")


def test_require_auth_rejects_empty() -> None:
    with pytest.raises(ValueError, match="missing token"):
        require_auth("")
