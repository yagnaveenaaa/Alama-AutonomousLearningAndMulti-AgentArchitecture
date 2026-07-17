from __future__ import annotations

from alama_common.errors import ValidationError

from identity_service.application.dto import ScimUserUpsertCommand
from identity_service.domain.membership import MembershipService
from identity_service.domain.models import Subject, SubjectStatus
from identity_service.domain.repositories import SubjectRepository


class ScimSyncHandler:
    """Upsert users from IdP SCIM projections (LLD §2.3)."""

    def __init__(
        self,
        subjects: SubjectRepository,
        memberships: MembershipService,
    ) -> None:
        self._subjects = subjects
        self._memberships = memberships

    async def upsert_user(self, command: ScimUserUpsertCommand) -> Subject:
        if not command.external_idp_sub.strip():
            raise ValidationError("external_idp_sub is required")

        await self._memberships.ensure_tenant_active(command.tenant_id)

        existing = await self._subjects.get_by_external_sub(
            command.tenant_id,
            command.external_idp_sub,
        )
        if existing is None:
            if not command.active:
                # Creating inactive users is a no-op for MVP projections.
                raise ValidationError("Cannot create inactive SCIM user")
            return await self._memberships.add_subject(
                tenant_id=command.tenant_id,
                external_idp_sub=command.external_idp_sub,
                email=command.email,
                display_name=command.display_name,
            )

        existing.email = command.email.lower() if command.email else existing.email
        existing.display_name = command.display_name or existing.display_name
        if command.active:
            existing.status = SubjectStatus.ACTIVE
        else:
            existing.disable()
        await self._subjects.save(existing)
        return existing
