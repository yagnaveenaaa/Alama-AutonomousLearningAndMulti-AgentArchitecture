from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.stdlib import BoundLogger

from alama_common.context.request import get_request_context


def _add_request_context(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    context = get_request_context()
    if context is not None:
        event_dict["request_id"] = str(context.request_id)
        if context.trace_id is not None:
            event_dict["trace_id"] = context.trace_id
        if context.tenant_id is not None:
            event_dict["tenant_id"] = str(context.tenant_id)
    return event_dict


def configure_logging(*, service_name: str, environment: str, log_level: str = "INFO") -> None:
    """Configure structured JSON logging for Alama services (LLD §24)."""

    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_request_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service=service_name, environment=environment)


def get_logger(name: str) -> BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
