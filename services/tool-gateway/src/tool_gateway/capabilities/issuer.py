from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from alama_common.errors import AuthenticationError, AuthorizationError, ValidationError
from alama_common.ids import new_uuid7

from tool_gateway.domain.models import FORBIDDEN_TOOLS, CapabilityToken


class HmacCapabilityIssuer:
    """Mint/verify short-lived capability tokens (LLD §2.10 / §13.2)."""

    AUDIENCE = "tool-gateway"

    def __init__(self, *, signing_key: str, ttl_seconds: int) -> None:
        if not signing_key.strip():
            raise ValidationError("capability signing key is required")
        self._key = signing_key.encode("utf-8")
        self._ttl = ttl_seconds

    async def mint(
        self,
        *,
        tenant_id: UUID,
        task_id: UUID,
        subject_id: UUID,
        tool: str,
        paths: list[str],
        policy_version: str,
    ) -> CapabilityToken:
        if tool in FORBIDDEN_TOOLS:
            raise AuthorizationError(f"Cannot mint capability for forbidden tool: {tool}")
        token_id = new_uuid7()
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=self._ttl)
        payload = {
            "jti": str(token_id),
            "aud": self.AUDIENCE,
            "tenant_id": str(tenant_id),
            "task_id": str(task_id),
            "sub": str(subject_id),
            "tool": tool,
            "paths": list(paths),
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "policy_version": policy_version,
        }
        raw = self._encode(payload)
        return CapabilityToken(
            token_id=token_id,
            audience=self.AUDIENCE,
            tenant_id=tenant_id,
            task_id=task_id,
            subject_id=subject_id,
            tool=tool,
            paths=tuple(paths),
            issued_at=now,
            expires_at=expires,
            policy_version=policy_version,
            raw=raw,
        )

    async def verify(self, raw: str) -> CapabilityToken:
        try:
            payload = self._decode(raw)
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            raise AuthenticationError("Invalid capability token") from exc
        if payload.get("aud") != self.AUDIENCE:
            raise AuthenticationError("Invalid capability audience")
        exp_raw = payload.get("exp")
        iat_raw = payload.get("iat")
        if not isinstance(exp_raw, int) or not isinstance(iat_raw, int):
            raise AuthenticationError("Invalid capability timestamps")
        exp = datetime.fromtimestamp(exp_raw, tz=UTC)
        if datetime.now(UTC) >= exp:
            raise AuthenticationError("Capability token expired")
        raw_paths = payload.get("paths", [])
        if not isinstance(raw_paths, list):
            raise AuthenticationError("Invalid capability paths")
        return CapabilityToken(
            token_id=UUID(str(payload["jti"])),
            audience=str(payload["aud"]),
            tenant_id=UUID(str(payload["tenant_id"])),
            task_id=UUID(str(payload["task_id"])),
            subject_id=UUID(str(payload["sub"])),
            tool=str(payload["tool"]),
            paths=tuple(str(p) for p in raw_paths),
            issued_at=datetime.fromtimestamp(iat_raw, tz=UTC),
            expires_at=exp,
            policy_version=str(payload.get("policy_version", "")),
            raw=raw,
        )

    def _encode(self, payload: dict[str, object]) -> str:
        body = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).decode("ascii")
        sig = hmac.new(self._key, body.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def _decode(self, raw: str) -> dict[str, object]:
        body, sig = raw.split(".", 1)
        expected = hmac.new(self._key, body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        data = json.loads(base64.urlsafe_b64decode(body.encode("ascii")))
        if not isinstance(data, dict):
            raise ValueError("bad payload")
        return {str(k): v for k, v in data.items()}
