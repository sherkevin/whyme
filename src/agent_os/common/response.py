"""PRD10 response envelope helpers.

All PRD10 endpoints should use these helpers so success/error/paginated
shapes stay aligned with `agent-1-backend-contract.md`.

Two flavors are exposed because the codebase has both pre-existing tests
(which expect plain ``dict`` envelopes for direct return from FastAPI handlers)
and richer use cases (which need ``JSONResponse`` for header/status control):

* ``success_response`` / ``paginated_response`` / ``error_response`` return a
  plain ``dict`` body. FastAPI will serialize it. They accept a ``Request`` or
  an explicit ``request_id``.
* ``success_json_response`` / ``paginated_json_response`` /
  ``error_json_response`` return ``JSONResponse`` instances and set the
  ``X-Request-ID`` header / status code (useful for error paths or when the
  caller wants the framework to honor a specific status code).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from agent_os.common.errors import ApiError, ApiErrorCode
from agent_os.common.pagination import build_pagination

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def get_request_id(request: Request | None = None) -> str:
    """Return the request id for the current request.

    Resolution order:
      1. Already attached `request.state.request_id` (set by middleware).
      2. Inbound `X-Request-ID` header.
      3. Newly generated `req_<uuid4-hex-12>`.
    """

    if request is not None:
        existing = getattr(request.state, REQUEST_ID_STATE_KEY, None)
        if isinstance(existing, str) and existing:
            return existing

        header_value = request.headers.get(REQUEST_ID_HEADER)
        if header_value:
            try:
                request.state.request_id = header_value
            except Exception:
                pass
            return header_value

    new_id = _new_request_id()
    if request is not None:
        try:
            request.state.request_id = new_id
        except Exception:
            pass
    return new_id


def _resolve_request_id(
    request: Request | None,
    request_id: str | None,
) -> str:
    if request_id:
        return request_id
    if request is not None:
        return get_request_id(request)
    return _new_request_id()


def success_response(
    data: Any = None,
    *,
    request: Request | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a PRD10 success envelope as a plain dict.

    ``data`` defaults to an empty object so the contract is never empty.
    """

    rid = _resolve_request_id(request, request_id)
    payload = data if data is not None else {}
    return {
        "success": True,
        "data": payload,
        "request_id": rid,
    }


def paginated_response(
    items: Iterable[Any],
    *,
    page: int,
    page_size: int,
    total: int,
    extra: dict[str, Any] | None = None,
    request: Request | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a PRD10 paginated success envelope as a plain dict.

    ``extra`` is merged into the inner ``data`` object next to ``items`` and
    ``pagination`` (e.g. ``facets`` for search results). Reserved keys (`items`,
    `pagination`) cannot be overridden via ``extra``.
    """

    pagination = build_pagination(page=page, page_size=page_size, total=total)

    data: dict[str, Any] = {
        "items": list(items),
        "pagination": pagination.to_dict(),
    }
    if extra:
        for key, value in extra.items():
            if key in data:
                raise ValueError(f"extra key '{key}' conflicts with reserved field")
            data[key] = value

    return success_response(data, request=request, request_id=request_id)


def error_response(
    code: ApiErrorCode | str | ApiError,
    message: str | None = None,
    *,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a PRD10 error envelope as a plain dict.

    Accepts either a code/message pair (preferred) or an existing ``ApiError``
    instance. The latter is convenient when the calling layer already raised
    a domain error and wants to translate it to an envelope.
    """

    if isinstance(code, ApiError):
        err = code
    else:
        if message is None:
            raise ValueError("message is required when code is not an ApiError")
        err = ApiError(code, message, details=details)

    rid = _resolve_request_id(request, request_id)
    return {
        "success": False,
        "error": err.to_error_dict(),
        "request_id": rid,
    }


def success_json_response(
    data: Any = None,
    *,
    request: Request | None = None,
    request_id: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    """``success_response`` wrapped in a ``JSONResponse`` with header echo."""

    body = success_response(data, request=request, request_id=request_id)
    headers = {REQUEST_ID_HEADER: body["request_id"]}
    return JSONResponse(content=body, status_code=status_code, headers=headers)


def paginated_json_response(
    items: Iterable[Any],
    *,
    page: int,
    page_size: int,
    total: int,
    extra: dict[str, Any] | None = None,
    request: Request | None = None,
    request_id: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    """``paginated_response`` wrapped in a ``JSONResponse``."""

    body = paginated_response(
        items,
        page=page,
        page_size=page_size,
        total=total,
        extra=extra,
        request=request,
        request_id=request_id,
    )
    headers = {REQUEST_ID_HEADER: body["request_id"]}
    return JSONResponse(content=body, status_code=status_code, headers=headers)


def error_json_response(
    code: ApiErrorCode | str | ApiError,
    message: str | None = None,
    *,
    details: dict[str, Any] | None = None,
    status_code: int | None = None,
    request: Request | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """``error_response`` wrapped in a ``JSONResponse`` with status code."""

    if isinstance(code, ApiError):
        err = code
    else:
        if message is None:
            raise ValueError("message is required when code is not an ApiError")
        err = ApiError(code, message, details=details, status_code=status_code)

    rid = _resolve_request_id(request, request_id)
    body = {
        "success": False,
        "error": err.to_error_dict(),
        "request_id": rid,
    }
    headers = {REQUEST_ID_HEADER: rid}
    return JSONResponse(content=body, status_code=err.status_code, headers=headers)


def error_response_from(
    error: ApiError,
    *,
    request: Request | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a PRD10 error envelope dict from an existing ``ApiError``."""

    return error_response(error, request=request, request_id=request_id)


def http_exception_to_envelope(
    exc: HTTPException,
    request: Request | None = None,
) -> JSONResponse:
    """Translate a FastAPI ``HTTPException`` to a PRD10 envelope.

    Resolution order for the ``error.code``:

    1. ``exc.detail["code"]`` if present and a recognised ``ApiErrorCode``.
       Routes that need a specific PRD10 code can raise
       ``HTTPException(status_code=..., detail={"code": "FORBIDDEN", ...})``
       and the envelope will surface that code regardless of the HTTP
       status (useful for ``410 GONE`` mapping to ``FORBIDDEN`` etc.).
    2. Default mapping by HTTP status (legacy behaviour).
    """

    status = exc.status_code
    detail = exc.detail

    detail_code: ApiErrorCode | None = None
    if isinstance(detail, dict):
        raw_code = detail.get("code")
        if isinstance(raw_code, str):
            try:
                detail_code = ApiErrorCode(raw_code)
            except ValueError:
                detail_code = None

    if detail_code is not None:
        code = detail_code
    elif status == 401:
        code = ApiErrorCode.UNAUTHORIZED
    elif status == 403:
        code = ApiErrorCode.FORBIDDEN
    elif status == 404:
        code = ApiErrorCode.NOT_FOUND
    elif status in (400, 422):
        code = ApiErrorCode.VALIDATION_ERROR
    elif status == 410:
        # GDPR right-to-erasure / "resource gone" — semantically a
        # FORBIDDEN access for the now-deleted account holder.
        code = ApiErrorCode.FORBIDDEN
    elif status == 429:
        code = ApiErrorCode.RATE_LIMITED
    else:
        code = ApiErrorCode.INTERNAL_ERROR

    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("detail") or str(detail)
        details_payload = {
            k: v for k, v in detail.items()
            if k not in {"message", "detail", "code"}
        }
    else:
        message = str(detail) if detail is not None else "Request failed"
        details_payload = {}

    return error_json_response(
        code,
        message,
        details=details_payload or None,
        status_code=status,
        request=request,
    )
