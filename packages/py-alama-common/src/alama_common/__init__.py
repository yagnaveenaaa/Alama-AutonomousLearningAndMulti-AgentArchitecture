"""Alama shared platform primitives used by all Python services and workers."""

from alama_common.auth.principal import Principal
from alama_common.config.base import BaseServiceSettings
from alama_common.context.request import RequestContext
from alama_common.errors.base import AlamaError
from alama_common.errors.types import (
    AuthenticationError,
    AuthorizationError,
    BudgetExceededError,
    ConflictError,
    DependencyFatalError,
    DependencyTransientError,
    DomainInvariantError,
    NotFoundError,
    PreconditionFailedError,
    RateLimitedError,
    SandboxError,
    ValidationError,
)
from alama_common.ids.uuid7 import new_uuid7
from alama_common.logging.setup import configure_logging
from alama_common.otel.setup import configure_opentelemetry, shutdown_opentelemetry
from alama_common.pagination.cursor import CursorPage, decode_cursor, encode_cursor
from alama_common.retry.policy import RetryPolicy, retry_with_policy

__all__ = [
    "AlamaError",
    "AuthenticationError",
    "AuthorizationError",
    "BaseServiceSettings",
    "BudgetExceededError",
    "ConflictError",
    "CursorPage",
    "DependencyFatalError",
    "DependencyTransientError",
    "DomainInvariantError",
    "NotFoundError",
    "PreconditionFailedError",
    "Principal",
    "RateLimitedError",
    "RequestContext",
    "RetryPolicy",
    "SandboxError",
    "ValidationError",
    "configure_logging",
    "configure_opentelemetry",
    "decode_cursor",
    "encode_cursor",
    "new_uuid7",
    "retry_with_policy",
    "shutdown_opentelemetry",
]

__version__ = "0.1.0"
