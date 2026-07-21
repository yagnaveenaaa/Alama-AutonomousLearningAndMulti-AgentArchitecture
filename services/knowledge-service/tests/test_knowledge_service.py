from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from knowledge_service.application.dto import (
    CreateConversationCommand,
    CreateMemoryCommand,
    DeleteMemoryCommand,
    PostMessageCommand,
)
from knowledge_service.config import KnowledgeSettings
from knowledge_service.container import build_container
from knowledge_service.domain.models import MemoryScope, MemoryStatus, MemoryType
from knowledge_service.main import create_app


@pytest.fixture
def container():
    return build_container(KnowledgeSettings(use_in_memory_store=True, min_confidence=0.5))


@pytest.fixture
async def client():
    app = create_app(KnowledgeSettings(use_in_memory_store=True))
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
async def test_create_and_promote_memory(container) -> None:
    tenant_id = uuid4()
    subject_id = uuid4()
    item = await container.memories.create(
        CreateMemoryCommand(
            tenant_id=tenant_id,
            subject_id=subject_id,
            scope=MemoryScope.ORG,
            memory_type=MemoryType.ORG_SEMANTIC,
            title="Prefer pytest over unittest",
            content="Team convention: use pytest for new tests.",
            confidence=0.9,
            promote=True,
        )
    )
    assert item.status == MemoryStatus.ACTIVE
    listed, _ = await container.memories.list(tenant_id, limit=10, cursor=None)
    assert len(listed) == 1
    assert listed[0].id == item.id


@pytest.mark.asyncio
async def test_write_gate_rejects_secret(container) -> None:
    with pytest.raises(Exception) as exc:
        await container.memories.create(
            CreateMemoryCommand(
                tenant_id=uuid4(),
                subject_id=uuid4(),
                scope=MemoryScope.USER,
                memory_type=MemoryType.USER_FACT,
                title="Credential",
                content='api_key="sk-supersecrettokenvalue123"',
                confidence=0.9,
            )
        )
    assert "write gate" in str(exc.value).lower() or "secret" in str(exc.value).lower()
    assert getattr(exc.value, "details", {}).get("reasons")


@pytest.mark.asyncio
async def test_write_gate_rejects_low_confidence(container) -> None:
    with pytest.raises(Exception) as exc:
        await container.memories.create(
            CreateMemoryCommand(
                tenant_id=uuid4(),
                subject_id=uuid4(),
                scope=MemoryScope.ORG,
                memory_type=MemoryType.ORG_SEMANTIC,
                title="Weak",
                content="Maybe use tabs?",
                confidence=0.1,
            )
        )
    assert "confidence_below_threshold" in getattr(exc.value, "details", {}).get("reasons", [])


@pytest.mark.asyncio
async def test_delete_propagates_to_content_store(container) -> None:
    tenant_id = uuid4()
    item = await container.memories.create(
        CreateMemoryCommand(
            tenant_id=tenant_id,
            subject_id=uuid4(),
            scope=MemoryScope.REPO,
            memory_type=MemoryType.REPO_CONVENTION,
            title="Lint",
            content="Run ruff before commit.",
            confidence=0.8,
            repository_id=uuid4(),
        )
    )
    await container.memories.delete(
        DeleteMemoryCommand(tenant_id=tenant_id, subject_id=uuid4(), memory_id=item.id)
    )
    assert item.content_ref in container.store.content.deleted


@pytest.mark.asyncio
async def test_conversation_and_message_flow(container) -> None:
    tenant_id = uuid4()
    subject_id = uuid4()
    conversation = await container.conversations.create(
        CreateConversationCommand(
            tenant_id=tenant_id,
            subject_id=subject_id,
            title="Fix auth bug",
        )
    )
    result = await container.conversations.post_message(
        PostMessageCommand(
            tenant_id=tenant_id,
            subject_id=subject_id,
            conversation_id=conversation.id,
            content="Please fix the login redirect",
            start_task=True,
        )
    )
    assert result.message.sequence == 1
    assert result.task_accepted is True


@pytest.mark.asyncio
async def test_http_memories_and_conversations(client) -> None:
    headers = _headers()
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "knowledge-service"

    created = await client.post(
        "/v1/memories",
        headers=headers,
        json={
            "scope": "org",
            "memory_type": "org_semantic",
            "title": "Style",
            "content": "Prefer explicit types in public APIs.",
            "confidence": 0.85,
            "promote": True,
        },
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]

    listed = await client.get("/v1/memories", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    patched = await client.patch(
        f"/v1/memories/{memory_id}",
        headers=headers,
        json={"status": "archived"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "archived"

    conv = await client.post(
        "/v1/conversations",
        headers=headers,
        json={"title": "Chat"},
    )
    assert conv.status_code == 201
    conversation_id = conv.json()["id"]

    msg = await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Hello Alama", "start_task": True},
    )
    assert msg.status_code == 202
    assert msg.json()["task_accepted"] is True

    denied = await client.post(
        "/v1/memories",
        headers=headers,
        json={
            "scope": "user",
            "memory_type": "user_fact",
            "title": "Secret",
            "content": "password=hunter2hunter2",
            "confidence": 0.9,
        },
    )
    assert denied.status_code == 422
