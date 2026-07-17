"""SCIM/OIDC admin hook adapters (LLD §2.3 adapters.idp).

External IdP remains authentication source of truth. This adapter translates
SCIM payloads into application commands handled by ScimSyncHandler.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from identity_service.application.dto import ScimUserUpsertCommand
from identity_service.application.scim_sync import ScimSyncHandler
from identity_service.domain.models import Subject


class ScimIdpAdapter:
    def __init__(self, scim_sync: ScimSyncHandler) -> None:
        self._scim_sync = scim_sync

    async def upsert_user_from_scim(
        self,
        *,
        tenant_id: UUID,
        payload: dict[str, Any],
    ) -> Subject:
        external_idp_sub = str(payload.get("id") or payload.get("externalId") or "")
        emails = payload.get("emails") or []
        email = None
        if isinstance(emails, list) and emails:
            primary = next((e for e in emails if e.get("primary")), emails[0])
            email = primary.get("value")
        name = payload.get("displayName") or payload.get("userName")
        active = bool(payload.get("active", True))
        return await self._scim_sync.upsert_user(
            ScimUserUpsertCommand(
                tenant_id=tenant_id,
                external_idp_sub=external_idp_sub,
                email=email,
                display_name=name,
                active=active,
            )
        )
