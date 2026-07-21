from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from audit_service.application.dto import ExportAuditCommand, IngestAuditCommand, LegalHoldCommand
from audit_service.config import AuditSettings
from audit_service.container import build_container
from audit_service.domain.models import ActorType, AuditDecision
from audit_service.main import create_app


@pytest.fixture
def container():
    return build_container(AuditSettings(use_in_memory_store=True))


@pytest.fixture
async def client():
    app = create_app(AuditSettings(use_in_memory_store=True))
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as http,
        app.router.lifespan_context(app),
    ):
        yield http


def _headers(tenant_id=None, subject_id=None) -> dict[str, str]:
    return {
        "X-Tenant-Id": str(tenant_id or uuid4()),
        "X-Subject-Id": str(subject_id or uuid4()),
    }


@pytest.mark.asyncio
async def test_ingest_builds_hash_chain(container) -> None:
    tenant_id = uuid4()
    first = await container.ingestor.ingest(
        IngestAuditCommand(
            tenant_id=tenant_id,
            actor_type=ActorType.USER,
            actor_id=str(uuid4()),
            action="task.create",
            resource_type="task",
            resource_id=str(uuid4()),
            decision=AuditDecision.RECORDED,
        )
    )
    second = await container.ingestor.ingest(
        IngestAuditCommand(
            tenant_id=tenant_id,
            actor_type=ActorType.SYSTEM,
            actor_id="policy-service",
            action="policy.activate",
            resource_type="policy_bundle",
            resource_id="policy.v1",
            decision=AuditDecision.ALLOW,
            policy_version="policy.v1",
        )
    )
    assert first.prev_hash == container.hasher.GENESIS
    assert second.prev_hash == first.integrity_hash
    assert await container.query.verify_integrity(tenant_id) is True
    assert len(container.store.outbox.messages) == 2


@pytest.mark.asyncio
async def test_legal_hold_and_export(container) -> None:
    tenant_id = uuid4()
    actor = str(uuid4())
    await container.ingestor.ingest(
        IngestAuditCommand(
            tenant_id=tenant_id,
            actor_type=ActorType.USER,
            actor_id=actor,
            action="repo.connect",
            resource_type="repository",
            resource_id=str(uuid4()),
        )
    )
    hold = await container.legal_hold.activate(
        LegalHoldCommand(tenant_id=tenant_id, reason="litigation", actor_id=actor)
    )
    assert hold.active is True
    exported = await container.exporter.export(
        ExportAuditCommand(
            tenant_id=tenant_id,
            region="us-east-1",
            requested_by=actor,
        )
    )
    assert exported.event_count >= 2
    assert await container.store.objects.get(exported.object_ref) is not None


@pytest.mark.asyncio
async def test_http_ingest_list_integrity(client) -> None:
    headers = _headers()
    health = await client.get("/health")
    assert health.status_code == 200

    created = await client.post(
        "/v1/audit/events",
        headers=headers,
        json={
            "actor_type": "user",
            "actor_id": headers["X-Subject-Id"],
            "action": "memory.export",
            "resource_type": "memory",
            "resource_id": str(uuid4()),
            "decision": "recorded",
            "payload": {"format": "json"},
        },
    )
    assert created.status_code == 201
    assert created.json()["integrity_hash"]

    listed = await client.get("/v1/audit/events", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    integrity = await client.get("/v1/audit/integrity", headers=headers)
    assert integrity.status_code == 200
    assert integrity.json()["valid"] is True

    exported = await client.post(
        "/v1/audit/exports",
        headers=headers,
        json={"region": "local"},
    )
    assert exported.status_code == 201
    assert exported.json()["event_count"] == 1
