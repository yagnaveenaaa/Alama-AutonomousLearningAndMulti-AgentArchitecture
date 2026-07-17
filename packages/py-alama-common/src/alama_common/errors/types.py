from __future__ import annotations

from typing import Any

from alama_common.errors.base import AlamaError


class ValidationError(AlamaError):
    code = "validation_error"
    http_status = 400
    retryable = False


class AuthenticationError(AlamaError):
    code = "authentication_error"
    http_status = 401
    retryable = False


class AuthorizationError(AlamaError):
    code = "authorization_error"
    http_status = 403
    retryable = False


class NotFoundError(AlamaError):
    code = "not_found"
    http_status = 404
    retryable = False


class ConflictError(AlamaError):
    code = "conflict"
    http_status = 409
    retryable = False


class PreconditionFailedError(AlamaError):
    code = "precondition_failed"
    http_status = 412
    retryable = False


class RateLimitedError(AlamaError):
    code = "rate_limited"
    http_status = 429
    retryable = True

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if retry_after_seconds is not None:
            merged_details["retry_after_seconds"] = retry_after_seconds
        super().__init__(message, details=merged_details)

    @property
    def retry_after_seconds(self) -> int | None:
        value = self.details.get("retry_after_seconds")
        return int(value) if value is not None else None


class BudgetExceededError(AlamaError):
    code = "budget_exceeded"
    http_status = 429
    retryable = False


class DependencyTransientError(AlamaError):
    code = "dependency_transient"
    http_status = 503
    retryable = True


class DependencyFatalError(AlamaError):
    code = "dependency_fatal"
    http_status = 502
    retryable = False


class SandboxError(AlamaError):
    code = "sandbox_error"
    http_status = 500
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)
        self.retryable = retryable


class DomainInvariantError(AlamaError):
    code = "domain_invariant_violation"
    http_status = 422
    retryable = False
