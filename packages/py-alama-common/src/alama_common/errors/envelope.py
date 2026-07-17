from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    """Standard API error envelope (LLD §3.2)."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    trace_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorEnvelope
