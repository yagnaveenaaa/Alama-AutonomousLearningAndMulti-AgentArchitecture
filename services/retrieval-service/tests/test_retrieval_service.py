from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from retrieval_service.domain.models import Candidate, RetrievalQuery, TrustLabel
from retrieval_service.domain.ports import GenerationRef
from retrieval_service.main import create_app

COMMIT = "a" * 40


def seed(app: object) -> tuple[object, object, object]:
    tenant_id = uuid4()
    repository_id = uuid4()
    generation = GenerationRef(id=uuid4(), repository_id=repository_id, commit_sha=COMMIT)
    public = Candidate(
        evidence_id=uuid4(),
        tenant_id=tenant_id,
        repository_id=repository_id,
        generation_id=generation.id,
        commit_sha=COMMIT,
        path="src/auth.py",
        start_line=10,
        end_line=14,
        content_sha="1" * 64,
        text="class TokenVerifier: verify JWT token signatures",
        symbol="auth.TokenVerifier",
        language="python",
        acl_labels=frozenset({"engineering"}),
        trust_label=TrustLabel.REPOSITORY,
        score=0,
    )
    forbidden = Candidate(
        evidence_id=uuid4(),
        tenant_id=tenant_id,
        repository_id=repository_id,
        generation_id=generation.id,
        commit_sha=COMMIT,
        path="secrets/admin.py",
        start_line=1,
        end_line=2,
        content_sha="2" * 64,
        text="TokenVerifier root override",
        symbol="admin.TokenVerifier",
        language="python",
        acl_labels=frozenset({"admin"}),
        trust_label=TrustLabel.UNTRUSTED,
        score=0,
    )
    app.state.container.index.add_generation(generation, [public, forbidden])
    return tenant_id, repository_id, public


@pytest.mark.asyncio
async def test_hybrid_retrieval_is_commit_consistent_and_acl_filtered() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        tenant_id, repository_id, public = seed(app)
        pack = await app.state.container.retriever.retrieve(
            RetrievalQuery(
                tenant_id=tenant_id,
                repository_id=repository_id,
                commit_sha=COMMIT,
                text="find TokenVerifier JWT verification",
                acl_labels=frozenset({"engineering"}),
            )
        )
        assert pack.stale is False
        assert [item.id for item in pack.evidence] == [public.evidence_id]
        assert pack.citations[0].path == "src/auth.py"


def test_http_retrieve_contract() -> None:
    app = create_app()
    with TestClient(app) as client:
        tenant_id, repository_id, _ = seed(app)
        response = client.post(
            "/v1/retrieve",
            headers={"X-Tenant-Id": str(tenant_id)},
            json={
                "repository_id": str(repository_id),
                "commit_sha": COMMIT,
                "query": "TokenVerifier JWT",
                "acl_labels": ["engineering"],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["stale"] is False
        assert body["citations"][0]["commit"] == COMMIT


@pytest.mark.asyncio
async def test_ancestor_fallback_is_explicitly_marked_stale() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        tenant_id, repository_id, _ = seed(app)
        pack = await app.state.container.retriever.retrieve(
            RetrievalQuery(
                tenant_id=tenant_id,
                repository_id=repository_id,
                commit_sha="b" * 40,
                text="TokenVerifier",
                acl_labels=frozenset({"engineering"}),
                allow_ancestor_fallback=True,
            )
        )
        assert pack.stale is True
        assert pack.indexed_commit_sha == COMMIT
