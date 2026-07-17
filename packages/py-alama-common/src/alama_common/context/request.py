from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID

from alama_common.auth.principal import Principal

_request_context: ContextVar[RequestContext | None] = ContextVar(
    "alama_request_context",
    default=None,
)


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Per-request metadata propagated through call stacks (LLD cross-cutting contracts)."""

    request_id: UUID
    trace_id: str | None = None
    tenant_id: UUID | None = None
    principal: Principal | None = None
    schema_version: str = "v1"


def bind_request_context(context: RequestContext) -> Token[RequestContext | None]:
    return _request_context.set(context)


def reset_request_context(token: Token[RequestContext | None]) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestContext | None:
    return _request_context.get()
