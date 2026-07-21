from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from policy_service.application.dto import (
    ActivateBundleCommand,
    EvaluatePolicyCommand,
    UpsertDraftBundleCommand,
)
from policy_service.config import PolicySettings
from policy_service.container import build_container
from policy_service.domain.models import PolicyAction, PolicyEffect
from policy_service.main import create_app


@pytest.fixture
def container():
    return build_container(PolicySettings(use_in_memory_store=True))


@pytest.fixture
async def client():
    app = create_app(PolicySettings(use_in_memory_store=True))
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
async def test_evaluate_allows_create_task(container) -> None:
    tenant_id = uuid4()
    decision = await container.evaluate.handle(
        EvaluatePolicyCommand(
            tenant_id=tenant_id,
            subject_id=uuid4(),
            action=PolicyAction.CREATE_TASK,
            attributes={"budget_usd_micros": 1_000_000},
        )
    )
    assert decision.effect == PolicyEffect.ALLOW
    assert decision.policy_version == "policy.v1"
    assert "task_create_allowed" in decision.reasons


@pytest.mark.asyncio
async def test_evaluate_denies_forbidden_tool(container) -> None:
    tenant_id = uuid4()
    decision = await container.evaluate.handle(
        EvaluatePolicyCommand(
            tenant_id=tenant_id,
            subject_id=uuid4(),
            action=PolicyAction.INVOKE_TOOL,
            attributes={"tool": "exfiltrate", "high_risk": True},
        )
    )
    assert decision.effect == PolicyEffect.DENY
    assert "forbidden_tool" in decision.reasons


@pytest.mark.asyncio
async def test_evaluate_requires_approval_for_high_risk_tool(container) -> None:
    tenant_id = uuid4()
    decision = await container.evaluate.handle(
        EvaluatePolicyCommand(
            tenant_id=tenant_id,
            subject_id=uuid4(),
            action=PolicyAction.INVOKE_TOOL,
            attributes={"tool": "open_pr", "high_risk": True},
        )
    )
    assert decision.effect == PolicyEffect.APPROVAL_REQUIRED
    assert "high_risk_tool" in decision.required_approvals


@pytest.mark.asyncio
async def test_evaluate_high_budget_requires_approval(container) -> None:
    tenant_id = uuid4()
    decision = await container.evaluate.handle(
        EvaluatePolicyCommand(
            tenant_id=tenant_id,
            subject_id=uuid4(),
            action=PolicyAction.CREATE_TASK,
            attributes={"budget_usd_micros": 75_000_000},
        )
    )
    assert decision.effect == PolicyEffect.APPROVAL_REQUIRED
    assert "budget_owner" in decision.required_approvals


@pytest.mark.asyncio
async def test_activate_switches_active_bundle(container) -> None:
    tenant_id = uuid4()
    subject_id = uuid4()
    # Seed default v1
    await container.evaluate.handle(
        EvaluatePolicyCommand(
            tenant_id=tenant_id,
            subject_id=subject_id,
            action=PolicyAction.CREATE_TASK,
            attributes={},
        )
    )
    await container.upsert_draft.handle(
        UpsertDraftBundleCommand(
            tenant_id=tenant_id,
            version="policy.v2",
            rules_payload={
                "schema_version": 1,
                "rules": [
                    {
                        "id": "deny-all-tasks",
                        "action": "create_task",
                        "effect": "deny",
                        "when": {},
                        "required_approvals": [],
                        "constraints": {},
                        "reason": "deny_all",
                    }
                ],
            },
            subject_id=subject_id,
        )
    )
    activated = await container.activate.handle(
        ActivateBundleCommand(
            tenant_id=tenant_id,
            version="policy.v2",
            subject_id=subject_id,
        )
    )
    assert activated.status.value == "active"
    decision = await container.evaluate.handle(
        EvaluatePolicyCommand(
            tenant_id=tenant_id,
            subject_id=subject_id,
            action=PolicyAction.CREATE_TASK,
            attributes={},
        )
    )
    assert decision.effect == PolicyEffect.DENY
    assert decision.policy_version == "policy.v2"


@pytest.mark.asyncio
async def test_http_evaluate_and_list_bundles(client) -> None:
    headers = _headers()
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "policy-service"

    evaluate = await client.post(
        "/v1/policy/evaluate",
        headers=headers,
        json={
            "action": "complete_model",
            "attributes": {"purpose": "training"},
            "dry_run": True,
        },
    )
    assert evaluate.status_code == 200
    body = evaluate.json()
    assert body["effect"] == "deny"
    assert "training_use_forbidden" in body["reasons"]

    bundles = await client.get("/v1/policy/bundles", headers=headers)
    assert bundles.status_code == 200
    items = bundles.json()["items"]
    assert len(items) == 1
    assert items[0]["version"] == "policy.v1"
    assert items[0]["status"] == "active"
