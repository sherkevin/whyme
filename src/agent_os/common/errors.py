"""Shared PRD10 API error definitions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ApiErrorCode(StrEnum):
    """Canonical PRD10 error codes."""

    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AI_PROVIDER_ERROR = "AI_PROVIDER_ERROR"
    JOB_FAILED = "JOB_FAILED"


DEFAULT_STATUS_BY_CODE: dict[ApiErrorCode, int] = {
    ApiErrorCode.UNAUTHORIZED: 401,
    ApiErrorCode.FORBIDDEN: 403,
    ApiErrorCode.NOT_FOUND: 404,
    ApiErrorCode.VALIDATION_ERROR: 400,
    ApiErrorCode.RATE_LIMITED: 429,
    ApiErrorCode.INTERNAL_ERROR: 500,
    ApiErrorCode.AI_PROVIDER_ERROR: 502,
    ApiErrorCode.JOB_FAILED: 500,
}


class ApiError(Exception):
    """Exception carrying a PRD10 error payload."""

    def __init__(
        self,
        code: ApiErrorCode | str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        self.code = ApiErrorCode(code)
        self.message = message
        self.details = details or {}
        self.status_code = status_code or DEFAULT_STATUS_BY_CODE[self.code]
        super().__init__(message)

    def to_error_dict(self) -> dict[str, Any]:
        """Return the inner `error` object from the PRD10 envelope."""
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }

