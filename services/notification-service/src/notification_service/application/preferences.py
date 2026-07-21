from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from notification_service.application.dto import UpsertPreferenceCommand
from notification_service.domain.models import ChannelPreference, NotificationChannel
from notification_service.domain.repositories import PreferenceRepository


class PreferenceService:
    """Recipient channel preferences for dispatcher routing."""

    def __init__(self, preferences: PreferenceRepository) -> None:
        self._preferences = preferences

    async def list(
        self, tenant_id: UUID, recipient_id: UUID
    ) -> list[ChannelPreference]:
        existing = await self._preferences.list_for_recipient(tenant_id, recipient_id)
        by_channel = {p.channel: p for p in existing}
        result: list[ChannelPreference] = []
        for channel in NotificationChannel:
            if channel in by_channel:
                result.append(by_channel[channel])
            else:
                result.append(
                    ChannelPreference(
                        tenant_id=tenant_id,
                        recipient_id=recipient_id,
                        channel=channel,
                        enabled=True,
                    )
                )
        return result

    async def upsert(self, command: UpsertPreferenceCommand) -> ChannelPreference:
        preference = ChannelPreference(
            tenant_id=command.tenant_id,
            recipient_id=command.recipient_id,
            channel=command.channel,
            enabled=command.enabled,
            destination=command.destination,
            updated_at=datetime.now(UTC),
        )
        await self._preferences.save(preference)
        return preference
