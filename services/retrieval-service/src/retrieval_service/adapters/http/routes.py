from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request

from retrieval_service.adapters.http.schemas import (
    CitationResponse,
    EvidenceResponse,
    RetrievalPackResponse,
    RetrieveRequest,
)
from retrieval_service.domain.models import RetrievalQuery

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/retrieve", response_model=RetrievalPackResponse)
async def retrieve(
    payload: RetrieveRequest,
    request: Request,
    tenant_id: Annotated[UUID, Header(alias="X-Tenant-Id")],
) -> RetrievalPackResponse:
    pack = await request.app.state.container.retriever.retrieve(
        RetrievalQuery(
            tenant_id=tenant_id,
            repository_id=payload.repository_id,
            commit_sha=payload.commit_sha,
            text=payload.query,
            acl_labels=frozenset(payload.acl_labels),
            token_budget=payload.token_budget,
            allow_ancestor_fallback=payload.allow_ancestor_fallback,
        )
    )
    return RetrievalPackResponse(
        repository_id=pack.repository_id,
        requested_commit_sha=pack.requested_commit_sha,
        indexed_commit_sha=pack.indexed_commit_sha,
        generation_id=pack.generation_id,
        stale=pack.stale,
        evidence=[EvidenceResponse(**asdict(item)) for item in pack.evidence],
        citations=[CitationResponse(**asdict(item)) for item in pack.citations],
        estimated_tokens=pack.estimated_tokens,
    )
