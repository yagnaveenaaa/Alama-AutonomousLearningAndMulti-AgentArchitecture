from __future__ import annotations

import hashlib
import hmac
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from repository_service.adapters.scm import SHARED_SCM_CATALOG
from repository_service.application.dto import (
    ConnectRepositoryCommand,
    IngestWebhookCommand,
    RegisterInstallationCommand,
    ReindexCommand,
)
from repository_service.container import build_container
from repository_service.domain.models import ScmProviderName
from repository_service.main import create_app


@pytest.fixture
def container():
    SHARED_SCM_CATALOG.repos.clear()
    SHARED_SCM_CATALOG.webhook_secrets.clear()
    SHARED_SCM_CATALOG.ref_commits.clear()
    SHARED_SCM_CATALOG.seed_repo(
        provider="github",
        installation_external_id="inst-1",
        external_repo_id="42",
        full_name="acme/demo",
        default_commit_sha="b" * 40,
        webhook_secret="whsec",
    )
    return build_container()


@pytest.mark.asyncio
async def test_connect_and_reindex(container) -> None:
    tenant_id = uuid4()
    installation = await container.connect.register_installation(
        RegisterInstallationCommand(
            tenant_id=tenant_id,
            provider=ScmProviderName.GITHUB,
            external_installation_id="inst-1",
            account_login="acme",
            secret_ref_path="secrets/github/inst-1",
        )
    )
    repo = await container.connect.connect(
        ConnectRepositoryCommand(
            tenant_id=tenant_id,
            provider=ScmProviderName.GITHUB,
            installation_id=installation.id,
            external_repo_id="42",
        )
    )
    assert repo.full_name == "acme/demo"

    snapshot = await container.snapshots_service.request_reindex(
        ReindexCommand(tenant_id=tenant_id, repository_id=repo.id)
    )
    assert snapshot.commit_sha == "b" * 40
    assert snapshot.state.value == "pending"
    assert len(container.store.outbox.events) == 1


@pytest.mark.asyncio
async def test_webhook_verify_dedupe(container) -> None:
    tenant_id = uuid4()
    body = b'{"ref":"refs/heads/main"}'
    secret = "whsec"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    signature = f"sha256={digest}"
    secret_ref = "github:inst-1"

    first = await container.webhook_ingestor.ingest(
        IngestWebhookCommand(
            tenant_id=tenant_id,
            provider=ScmProviderName.GITHUB,
            delivery_id="deliv-1",
            event_type="push",
            body=body,
            signature_header=signature,
            secret_ref_path=secret_ref,
        )
    )
    second = await container.webhook_ingestor.ingest(
        IngestWebhookCommand(
            tenant_id=tenant_id,
            provider=ScmProviderName.GITHUB,
            delivery_id="deliv-1",
            event_type="push",
            body=body,
            signature_header=signature,
            secret_ref_path=secret_ref,
        )
    )
    assert first.id == second.id
    assert first.status.value == "processed"


@pytest.fixture
def client():
    SHARED_SCM_CATALOG.repos.clear()
    SHARED_SCM_CATALOG.webhook_secrets.clear()
    SHARED_SCM_CATALOG.ref_commits.clear()
    SHARED_SCM_CATALOG.seed_repo(
        provider="github",
        installation_external_id="inst-http",
        external_repo_id="99",
        full_name="acme/http",
        default_commit_sha="c" * 40,
        webhook_secret="http-secret",
    )
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_http_connect_reindex_flow(client: TestClient) -> None:
    tenant_id = str(uuid4())
    subject_id = str(uuid4())
    headers = {"X-Subject-Id": subject_id, "X-Tenant-Id": tenant_id}

    inst = client.post(
        "/v1/installations",
        headers=headers,
        json={
            "provider": "github",
            "external_installation_id": "inst-http",
            "account_login": "acme",
            "secret_ref_path": "secrets/github/inst-http",
        },
    )
    assert inst.status_code == 201
    installation_id = inst.json()["id"]

    connected = client.post(
        "/v1/repositories/connect",
        headers=headers,
        json={
            "provider": "github",
            "installation_id": installation_id,
            "external_repo_id": "99",
        },
    )
    assert connected.status_code == 201
    repo_id = connected.json()["id"]
    assert connected.json()["full_name"] == "acme/http"

    listed = client.get("/v1/repositories", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    reindex = client.post(
        f"/v1/repositories/{repo_id}/reindex",
        headers=headers,
        json={},
    )
    assert reindex.status_code == 202
    assert "snapshot_id" in reindex.json()

    status = client.get(f"/v1/repositories/{repo_id}/index/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["latest_commit_sha"] == "c" * 40
    assert status.json()["state"] == "pending"

    body = b'{"ok":true}'
    digest = hmac.new(b"http-secret", body, hashlib.sha256).hexdigest()
    wh = client.post(
        "/webhooks/github",
        headers={
            "X-Tenant-Id": tenant_id,
            "X-Alama-Secret-Ref": "github:inst-http",
            "X-Hub-Signature-256": f"sha256={digest}",
            "X-GitHub-Delivery": "d-1",
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        },
        content=body,
    )
    assert wh.status_code == 202

    deleted = client.delete(f"/v1/repositories/{repo_id}", headers=headers)
    assert deleted.status_code == 204


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["service"] == "repository-service"
