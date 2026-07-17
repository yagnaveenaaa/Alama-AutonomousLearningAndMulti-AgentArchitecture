from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

from alama_common.errors import AuthorizationError, NotFoundError, ValidationError
from alama_common.ids import new_uuid7
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from identity_service.application.dto import CreateApiKeyCommand, IssuedApiKeyResult
from identity_service.domain.membership import MembershipService
from identity_service.domain.models import ApiKey
from identity_service.domain.repositories import ApiKeyRepository, SubjectRepository

_hasher = PasswordHasher()
_KEY_PREFIX = "alama_"


class ApiKeyService:
    """Issue, rotate, and revoke hashed API keys (LLD §2.3)."""

    def __init__(
        self,
        api_keys: ApiKeyRepository,
        subjects: SubjectRepository,
        memberships: MembershipService,
    ) -> None:
        self._api_keys = api_keys
        self._subjects = subjects
        self._memberships = memberships

    async def issue(self, command: CreateApiKeyCommand) -> IssuedApiKeyResult:
        if not command.name.strip():
            raise ValidationError("name is required")
        if not command.scopes:
            raise ValidationError("scopes must not be empty")

        await self._memberships.ensure_tenant_active(command.tenant_id)

        subject = await self._subjects.get_by_id(command.subject_id)
        if subject is None or subject.tenant_id != command.tenant_id:
            raise NotFoundError("Subject not found in tenant")

        raw_secret = secrets.token_urlsafe(32)
        key_id = new_uuid7()
        key_prefix = f"{_KEY_PREFIX}{str(key_id).replace('-', '')[:8]}"
        plaintext = f"{key_prefix}.{raw_secret}"
        key_hash = _hasher.hash(plaintext).encode("utf-8")
        now = datetime.now(UTC)

        api_key = ApiKey(
            id=key_id,
            tenant_id=command.tenant_id,
            subject_id=command.subject_id,
            name=command.name.strip(),
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=tuple(command.scopes),
            expires_at=command.expires_at,
            revoked_at=None,
            last_used_at=None,
            created_at=now,
            updated_at=now,
            version=1,
        )
        await self._api_keys.save(api_key)

        return IssuedApiKeyResult(
            id=api_key.id,
            key_prefix=api_key.key_prefix,
            plaintext_key=plaintext,
            name=api_key.name,
            scopes=api_key.scopes,
            expires_at=api_key.expires_at,
        )

    async def revoke(self, *, tenant_id: UUID, api_key_id: UUID, actor_subject_id: UUID) -> None:
        await self._memberships.ensure_tenant_active(tenant_id)
        api_key = await self._api_keys.get_by_id(tenant_id, api_key_id)
        if api_key is None:
            raise NotFoundError("API key not found")
        if api_key.subject_id != actor_subject_id:
            # Owners/admins would be allowed via policy later; MVP: owner of key or same subject.
            raise AuthorizationError("Not allowed to revoke this API key")
        api_key.revoke()
        await self._api_keys.save(api_key)

    def verify_plaintext(self, api_key: ApiKey, plaintext: str) -> bool:
        try:
            return _hasher.verify(api_key.key_hash.decode("utf-8"), plaintext)
        except VerifyMismatchError:
            return False
