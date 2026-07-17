from __future__ import annotations

from alama_common.errors import AuthenticationError, ConflictError
from alama_common.ids import new_uuid7

from repository_service.application.dto import IngestWebhookCommand
from repository_service.domain.models import SecretRef, WebhookDelivery
from repository_service.domain.repositories import OutboxRepository, WebhookDeliveryRepository
from repository_service.domain.scm import ScmProvider


class WebhookIngestor:
    """Verify → dedupe → outbox event (LLD §2.4)."""

    def __init__(
        self,
        deliveries: WebhookDeliveryRepository,
        outbox: OutboxRepository,
        providers: dict[str, ScmProvider],
    ) -> None:
        self._deliveries = deliveries
        self._outbox = outbox
        self._providers = providers

    async def ingest(self, command: IngestWebhookCommand) -> WebhookDelivery:
        provider = self._providers.get(command.provider.value)
        if provider is None:
            raise ConflictError(f"Unsupported provider: {command.provider.value}")

        secret_ref = SecretRef(command.secret_ref_path)
        if not provider.verify_webhook_signature(
            body=command.body,
            signature_header=command.signature_header,
            secret_ref=secret_ref,
        ):
            raise AuthenticationError("Invalid webhook signature")

        existing = await self._deliveries.get_by_delivery(command.provider, command.delivery_id)
        if existing is not None:
            return existing

        payload_ref = (
            f"webhooks/{command.provider.value}/{command.delivery_id}/{new_uuid7()}.json"
        )
        delivery = WebhookDelivery.receive(
            tenant_id=command.tenant_id,
            provider=command.provider,
            delivery_id=command.delivery_id,
            event_type=command.event_type,
            payload_ref=payload_ref,
        )
        await self._deliveries.save(delivery)
        await self._outbox.enqueue(
            aggregate_type="webhook_delivery",
            aggregate_id=delivery.id,
            event_type="com.alama.repository.webhook.received.v1",
            payload={
                "delivery_id": delivery.delivery_id,
                "provider": command.provider.value,
                "event_type": command.event_type,
                "tenant_id": str(command.tenant_id),
                "payload_ref": payload_ref,
            },
        )
        delivery.mark_processed()
        await self._deliveries.save(delivery)
        return delivery
