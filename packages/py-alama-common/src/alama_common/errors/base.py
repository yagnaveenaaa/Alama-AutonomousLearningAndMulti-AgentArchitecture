from __future__ import annotations

from typing import Any


class AlamaError(Exception):
    """Base typed error for all Alama services (LLD §3.2)."""

    code: str = "internal_error"
    http_status: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}
        self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
