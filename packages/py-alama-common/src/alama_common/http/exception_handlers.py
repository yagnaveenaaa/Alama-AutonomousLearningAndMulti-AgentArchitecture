from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from alama_common.context.request import get_request_context
from alama_common.errors.base import AlamaError
from alama_common.errors.envelope import ErrorEnvelope, ErrorResponse
from alama_common.errors.types import RateLimitedError, ValidationError
from alama_common.logging.setup import get_logger

logger = get_logger(__name__)


def _build_error_response(exc: AlamaError, request: Request) -> JSONResponse:
    context = get_request_context()
    request_id: str | None
    trace_id: str | None
    if context is not None:
        request_id = str(context.request_id)
        trace_id = context.trace_id
    else:
        request_id = request.headers.get("X-Request-Id")
        trace_id = None

    body = ErrorResponse(
        error=ErrorEnvelope(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
            trace_id=trace_id,
        )
    )

    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitedError) and exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)

    return JSONResponse(
        status_code=exc.http_status,
        content=body.model_dump(),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register Alama-standard exception handlers on a FastAPI application."""

    @app.exception_handler(AlamaError)
    async def handle_alama_error(request: Request, exc: AlamaError) -> JSONResponse:
        logger.warning(
            "request_failed",
            event_name="request_failed",
            error_code=exc.code,
            http_status=exc.http_status,
            path=str(request.url.path),
        )
        return _build_error_response(exc, request)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        validation_error = ValidationError(
            "Request validation failed",
            details={"errors": exc.errors()},
        )
        return _build_error_response(validation_error, request)

    @app.exception_handler(PydanticValidationError)
    async def handle_pydantic_validation_error(
        request: Request,
        exc: PydanticValidationError,
    ) -> JSONResponse:
        validation_error = ValidationError(
            "Validation failed",
            details={"errors": exc.errors()},
        )
        return _build_error_response(validation_error, request)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            event_name="unhandled_exception",
            path=str(request.url.path),
        )
        internal = AlamaError("An unexpected error occurred")
        return _build_error_response(internal, request)
