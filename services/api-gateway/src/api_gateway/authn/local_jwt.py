from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from alama_common.auth import Principal
from alama_common.errors import AuthenticationError
from alama_common.ids import new_uuid7


class LocalJwtTokenValidator:
    """HS256 JWT validator for local/dev; production plugs OIDC JWKS (LLD §13.2)."""

    def __init__(
        self,
        *,
        secret: str,
        audience: str,
        issuer: str,
        session_store: dict[str, Principal] | None = None,
    ) -> None:
        self._secret = secret
        self._audience = audience
        self._issuer = issuer
        self._sessions = session_store if session_store is not None else {}

    def mint(
        self,
        *,
        subject_id: UUID,
        tenant_ids: tuple[UUID, ...],
        scopes: frozenset[str],
        session_id: UUID | None = None,
        ttl_seconds: int = 3600,
    ) -> str:
        now = datetime.now(UTC)
        sid = session_id or new_uuid7()
        payload: dict[str, Any] = {
            "sub": str(subject_id),
            "tenant_ids": [str(t) for t in tenant_ids],
            "scopes": sorted(scopes),
            "sid": str(sid),
            "iss": self._issuer,
            "aud": self._audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def mint_session(
        self,
        *,
        subject_id: UUID,
        tenant_ids: tuple[UUID, ...],
        scopes: frozenset[str],
    ) -> str:
        session_id = new_uuid7()
        principal = Principal(
            subject_id=subject_id,
            tenant_ids=tenant_ids,
            scopes=scopes,
            session_id=session_id,
        )
        cookie = str(session_id)
        self._sessions[cookie] = principal
        return cookie

    async def validate_bearer(self, token: str) -> Principal:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired access token") from exc
        return self._principal_from_claims(payload)

    async def validate_session_cookie(self, cookie_value: str) -> Principal:
        principal = self._sessions.get(cookie_value)
        if principal is None:
            raise AuthenticationError("Invalid or expired session")
        return principal

    def _principal_from_claims(self, payload: dict[str, Any]) -> Principal:
        try:
            subject_id = UUID(str(payload["sub"]))
            tenant_ids = tuple(UUID(str(t)) for t in payload.get("tenant_ids", []))
            scopes = frozenset(str(s) for s in payload.get("scopes", []))
            sid_raw = payload.get("sid")
            session_id = UUID(str(sid_raw)) if sid_raw else None
        except (KeyError, ValueError, TypeError) as exc:
            raise AuthenticationError("Malformed token claims") from exc
        if not tenant_ids:
            raise AuthenticationError("Token missing tenant memberships")
        return Principal(
            subject_id=subject_id,
            tenant_ids=tenant_ids,
            scopes=scopes,
            session_id=session_id,
        )
