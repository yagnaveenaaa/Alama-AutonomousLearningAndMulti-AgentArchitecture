from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from bff_web.config import BffSettings
from bff_web.main import create_app


@pytest.fixture
async def client():
    app = create_app(BffSettings(use_in_memory_clients=True))
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as http,
        app.router.lifespan_context(app),
    ):
        yield http


def _headers() -> dict[str, str]:
    return {
        "X-Subject-Id": str(uuid4()),
        "X-Tenant-Id": str(uuid4()),
    }


@pytest.mark.asyncio
async def test_health(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "bff-web"


@pytest.mark.asyncio
async def test_graphql_requires_identity(client) -> None:
    response = await client.post("/graphql", json={"query": "{ tasks { id } }"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_query(client) -> None:
    query = """
    query {
      tasks { id title state repositoryName paused }
      repositories { id fullName indexState }
      usage { tokensUsed tokensBudget }
      memories { id title status }
    }
    """
    response = await client.post(
        "/graphql",
        headers=_headers(),
        json={"query": query},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload
    data = payload["data"]
    assert len(data["tasks"]) >= 2
    assert data["tasks"][0]["repositoryName"]
    assert len(data["repositories"]) == 2
    assert data["usage"]["tokensBudget"] == 1_000_000
    assert data["memories"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_task_detail_and_approvals(client) -> None:
    list_resp = await client.post(
        "/graphql",
        headers=_headers(),
        json={"query": "{ tasks { id state } }"},
    )
    tasks = list_resp.json()["data"]["tasks"]
    awaiting = next(t for t in tasks if t["state"] == "awaiting_approval")
    task_id = awaiting["id"]

    detail = await client.post(
        "/graphql",
        headers=_headers(),
        json={
            "query": """
            query($id: UUID!) {
              task(id: $id) { id title state }
              taskEvents(taskId: $id) { sequence eventType summary }
              taskApprovals(taskId: $id) { id gate status }
            }
            """,
            "variables": {"id": task_id},
        },
    )
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["task"]["id"] == task_id
    assert body["taskEvents"]
    assert body["taskApprovals"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_decide_approval_mutation(client) -> None:
    headers = _headers()
    tasks = (
        await client.post(
            "/graphql",
            headers=headers,
            json={"query": "{ tasks { id state } }"},
        )
    ).json()["data"]["tasks"]
    task_id = next(t["id"] for t in tasks if t["state"] == "awaiting_approval")
    approvals = (
        await client.post(
            "/graphql",
            headers=headers,
            json={
                "query": "query($id: UUID!) { taskApprovals(taskId: $id) { id status } }",
                "variables": {"id": task_id},
            },
        )
    ).json()["data"]["taskApprovals"]
    approval_id = approvals[0]["id"]

    mutated = await client.post(
        "/graphql",
        headers=headers,
        json={
            "query": """
            mutation($taskId: UUID!, $approvalId: UUID!) {
              decideApproval(taskId: $taskId, approvalId: $approvalId, decision: "approved") {
                id status
              }
            }
            """,
            "variables": {"taskId": task_id, "approvalId": approval_id},
        },
    )
    assert mutated.status_code == 200
    assert mutated.json()["data"]["decideApproval"]["status"] == "approved"


@pytest.mark.asyncio
async def test_send_chat_returns_handshake(client) -> None:
    response = await client.post(
        "/graphql",
        headers=_headers(),
        json={
            "query": """
            mutation {
              sendChat(content: "Add health endpoint") {
                messages { role content taskId }
                handshake { streamUrl taskId conversationId }
                task { id state title }
              }
            }
            """
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload, payload
    data = payload["data"]["sendChat"]
    assert data["task"]["state"] == "planning"
    assert "/events/stream" in data["handshake"]["streamUrl"]
    assert any(m["role"] == "user" for m in data["messages"])
    assert UUID(data["handshake"]["taskId"])
