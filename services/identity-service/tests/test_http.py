from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from identity_service.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "identity-service"


def test_tenant_lifecycle_and_api_key_http(client: TestClient) -> None:
    create = client.post(
        "/v1/tenants",
        json={
            "slug": "http-acme",
            "name": "HTTP Acme",
            "home_region": "us-east-1",
            "home_cell": "cell-use1-a",
            "isolation_tier": "shared",
            "plan": "free",
            "data_residency": "us",
            "owner_external_idp_sub": "idp|http-owner",
            "owner_email": "owner@http.test",
        },
    )
    assert create.status_code == 201
    tenant = create.json()
    tenant_id = tenant["id"]

    # Resolve owner subject from list after creating a principal via store inspection
    container = client.app.state.container
    subjects = list(container.store.subjects.values())
    assert len(subjects) == 1
    subject_id = str(subjects[0].id)

    headers = {"X-Subject-Id": subject_id, "X-Tenant-Id": tenant_id}

    me_tenant = client.get("/v1/tenants/me", headers=headers)
    assert me_tenant.status_code == 200
    assert me_tenant.json()["slug"] == "http-acme"

    me_subject = client.get("/v1/subjects/me", headers=headers)
    assert me_subject.status_code == 200
    assert me_subject.json()["roles"] == ["owner"]

    listed = client.get(f"/v1/tenants/{tenant_id}/subjects", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    key_resp = client.post(
        f"/v1/tenants/{tenant_id}/api-keys",
        headers=headers,
        json={"name": "cli", "scopes": ["identity:read"]},
    )
    assert key_resp.status_code == 201
    body = key_resp.json()
    assert "key_once" in body
    assert body["key_prefix"].startswith("alama_")

    revoke = client.delete(
        f"/v1/tenants/{tenant_id}/api-keys/{body['id']}",
        headers=headers,
    )
    assert revoke.status_code == 204


def test_missing_identity_headers(client: TestClient) -> None:
    response = client.get("/v1/tenants/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"
