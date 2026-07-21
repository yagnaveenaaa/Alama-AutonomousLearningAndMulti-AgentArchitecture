from __future__ import annotations

from uuid import uuid4

import pytest
from alama_common.errors import AuthorizationError, ValidationError
from fastapi.testclient import TestClient

from tool_gateway.domain.models import ToolCallRequest
from tool_gateway.main import create_app


@pytest.mark.asyncio
async def test_mint_and_invoke_get_file() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        container = app.state.container
        tenant_id = uuid4()
        subject_id = uuid4()
        task_id = uuid4()
        token = await container.gateway.mint_capability(
            tenant_id=tenant_id,
            task_id=task_id,
            subject_id=subject_id,
            tool="get_file",
            paths=["src/main.py"],
        )
        result = await container.gateway.invoke(
            ToolCallRequest(
                tenant_id=tenant_id,
                task_id=task_id,
                tool="get_file",
                args={"path": "src/main.py"},
                capability_raw=token.raw,
            )
        )
        assert result.ok is True
        assert "def main" in result.output
        assert container.audit.receipts
        assert container.audit.receipts[0].tool == "get_file"


@pytest.mark.asyncio
async def test_capability_tool_mismatch_is_denied() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        container = app.state.container
        tenant_id = uuid4()
        task_id = uuid4()
        token = await container.gateway.mint_capability(
            tenant_id=tenant_id,
            task_id=task_id,
            subject_id=uuid4(),
            tool="get_file",
            paths=["."],
        )
        with pytest.raises(AuthorizationError):
            await container.gateway.invoke(
                ToolCallRequest(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    tool="apply_patch",
                    args={"path": "src/main.py", "diff": "+x"},
                    capability_raw=token.raw,
                )
            )


@pytest.mark.asyncio
async def test_path_escape_and_forbidden_tool() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        container = app.state.container
        with pytest.raises(ValidationError):
            await container.gateway.mint_capability(
                tenant_id=uuid4(),
                task_id=uuid4(),
                subject_id=uuid4(),
                tool="raw_shell",
                paths=["."],
            )
        # ValidationError from ToolCallRequest for forbidden tools
        with pytest.raises(ValidationError):
            ToolCallRequest(
                tenant_id=uuid4(),
                task_id=uuid4(),
                tool="secret_read",
                args={},
                capability_raw="x",
            )


@pytest.mark.asyncio
async def test_high_risk_tool_requires_approval() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        container = app.state.container
        tenant_id = uuid4()
        task_id = uuid4()
        token = await container.gateway.mint_capability(
            tenant_id=tenant_id,
            task_id=task_id,
            subject_id=uuid4(),
            tool="open_pr",
            paths=["."],
        )
        with pytest.raises(AuthorizationError, match="approval"):
            await container.gateway.invoke(
                ToolCallRequest(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    tool="open_pr",
                    args={"title": "Change"},
                    capability_raw=token.raw,
                )
            )


def test_http_mint_and_invoke_contract() -> None:
    app = create_app()
    tenant_id = uuid4()
    subject_id = uuid4()
    task_id = uuid4()
    headers = {
        "X-Tenant-Id": str(tenant_id),
        "X-Subject-Id": str(subject_id),
    }
    with TestClient(app) as client:
        minted = client.post(
            "/v1/capabilities/mint",
            headers=headers,
            json={"task_id": str(task_id), "tool": "list_dir", "paths": ["."]},
        )
        assert minted.status_code == 200, minted.text
        token = minted.json()["token"]

        invoked = client.post(
            "/v1/invoke",
            headers=headers,
            json={
                "task_id": str(task_id),
                "tool": "list_dir",
                "args": {"path": "."},
                "capability": token,
            },
        )
        assert invoked.status_code == 200, invoked.text
        body = invoked.json()
        assert body["ok"] is True
        assert "src" in body["output"] or "README.md" in body["output"]
        assert body["receipt"]["ok"] is True
