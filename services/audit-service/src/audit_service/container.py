from __future__ import annotations

from dataclasses import dataclass

from audit_service.adapters.memory import (
    InMemoryAuditEventRepository,
    InMemoryAuditStore,
    InMemoryLegalHoldRepository,
)
from audit_service.application.export import AuditExporter, LegalHoldService
from audit_service.application.ingest import AuditIngestor
from audit_service.application.query import AuditQueryService
from audit_service.config import AuditSettings
from audit_service.domain.integrity import IntegrityHasher


@dataclass
class AuditContainer:
    store: InMemoryAuditStore
    ingestor: AuditIngestor
    query: AuditQueryService
    exporter: AuditExporter
    legal_hold: LegalHoldService
    hasher: IntegrityHasher


def build_container(settings: AuditSettings | None = None) -> AuditContainer:
    settings = settings or AuditSettings()
    store = InMemoryAuditStore()
    events = InMemoryAuditEventRepository(store)
    holds = InMemoryLegalHoldRepository(store)
    hasher = IntegrityHasher()
    ingestor = AuditIngestor(events, store.objects, store.outbox, hasher, holds)
    return AuditContainer(
        store=store,
        ingestor=ingestor,
        query=AuditQueryService(events, hasher),
        exporter=AuditExporter(
            events, store.objects, export_prefix=settings.export_object_prefix
        ),
        legal_hold=LegalHoldService(holds, ingestor),
        hasher=hasher,
    )
