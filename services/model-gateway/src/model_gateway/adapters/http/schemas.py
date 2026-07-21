from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class ChatMessageRequest(BaseModel):
    role: str
    content: str = Field(min_length=1)


class CompleteRequest(BaseModel):
    purpose: str = Field(min_length=1)
    task_id: UUID | None = None
    preferred_tier: str = "strong"
    residency: str = "any"
    messages: list[ChatMessageRequest] = Field(default_factory=list)
    template_name: str | None = None
    template_version: str | None = None
    template_inputs: dict[str, Any] = Field(default_factory=dict)
    json_schema_name: str | None = None
    max_tokens: int = Field(default=2048, ge=1, le=100_000)


class CompleteResponse(BaseModel):
    request_id: UUID
    model: str
    provider: str
    content: str
    parsed_json: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    fallback_used: bool


class EmbedRequest(BaseModel):
    purpose: str = Field(min_length=1)
    task_id: UUID | None = None
    residency: str = "any"
    texts: list[str] = Field(min_length=1)


class EmbedResponse(BaseModel):
    request_id: UUID
    model: str
    provider: str
    vectors: list[list[float]]
    input_tokens: int
    dimension: int


class RerankRequest(BaseModel):
    purpose: str = Field(min_length=1)
    task_id: UUID | None = None
    residency: str = "any"
    query: str = Field(min_length=1)
    documents: list[str] = Field(min_length=1)


class RerankResponse(BaseModel):
    request_id: UUID
    model: str
    provider: str
    ranked_indices: list[int]
    scores: list[float]
    input_tokens: int
