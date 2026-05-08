"""Integration-style tests for the PRD10 response envelope helpers.

These tests exercise the FastAPI-facing wrappers (``*_json_response``) and the
``RequestIdMiddleware`` so the contract pieces work together. The plain dict
helpers are covered by ``test_response.py`` next to this file.

Notes:
- We avoid `fastapi.testclient.TestClient` because the pinned starlette in
  this repo doesn't compose cleanly with newer httpx versions. Instead we use
  ``httpx.AsyncClient`` with ``ASGITransport`` directly, which works on every
  supported FastAPI 0.104+ install in this repo.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request

from agent_os.common import (
    ApiError,
    ApiErrorCode,
    RequestIdMiddleware,
    error_json_response,
    http_exception_to_envelope,
    paginated_json_response,
    success_json_response,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ok")
    async def _ok(request: Request):
        return success_json_response({"x": 1}, request=request)

    @app.get("/page")
    async def _page(request: Request):
        items = [{"id": i} for i in range(3)]
        return paginated_json_response(
            items,
            page=1,
            page_size=20,
            total=3,
            request=request,
        )

    @app.get("/page-extra")
    async def _page_extra(request: Request):
        return paginated_json_response(
            [],
            page=1,
            page_size=20,
            total=0,
            extra={"facets": {"types": []}},
            request=request,
        )

    @app.get("/err-code")
    async def _err_code(request: Request):
        return error_json_response(
            ApiErrorCode.NOT_FOUND,
            "Missing thing",
            details={"field": "id"},
            request=request,
        )

    @app.get("/err-from")
    async def _err_from(request: Request):
        err = ApiError(
            ApiErrorCode.VALIDATION_ERROR,
            "Bad payload",
            details={"field": "title"},
        )
        return error_json_response(err, request=request)

    @app.get("/err-http")
    async def _err_http(request: Request):
        try:
            raise HTTPException(status_code=403, detail="No way")
        except HTTPException as exc:
            return http_exception_to_envelope(exc, request=request)

    return app


def _async_get(app: FastAPI, path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    """Run a single GET against the ASGI app via httpx.AsyncClient."""

    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get(path, headers=headers or {})

    return asyncio.run(_run())


def test_success_json_envelope_uses_request_id_header() -> None:
    res = _async_get(_build_app(), "/ok", headers={"X-Request-ID": "req_abc"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"] == {"x": 1}
    assert body["request_id"] == "req_abc"
    assert res.headers["X-Request-ID"] == "req_abc"


def test_success_json_envelope_generates_id_when_missing() -> None:
    res = _async_get(_build_app(), "/ok")
    body = res.json()
    assert body["request_id"].startswith("req_")
    assert res.headers["X-Request-ID"] == body["request_id"]


def test_paginated_json_envelope_shape() -> None:
    res = _async_get(_build_app(), "/page")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["items"] == [{"id": 0}, {"id": 1}, {"id": 2}]
    assert body["data"]["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 3,
        "has_more": False,
    }


def test_paginated_json_envelope_supports_extra_facets() -> None:
    res = _async_get(_build_app(), "/page-extra")
    body = res.json()
    assert body["data"]["facets"] == {"types": []}
    assert body["data"]["pagination"]["total"] == 0
    assert body["data"]["items"] == []


def test_error_json_envelope_uses_default_status_code() -> None:
    res = _async_get(_build_app(), "/err-code")
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Missing thing"
    assert body["error"]["details"] == {"field": "id"}
    assert body["request_id"]


def test_error_json_response_accepts_existing_api_error() -> None:
    res = _async_get(_build_app(), "/err-from")
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {"field": "title"}


def test_http_exception_translation_uses_correct_code() -> None:
    res = _async_get(_build_app(), "/err-http")
    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["error"]["message"] == "No way"


def test_api_error_default_status_mapping() -> None:
    err = ApiError(ApiErrorCode.UNAUTHORIZED, "bye")
    assert err.status_code == 401
    err2 = ApiError(ApiErrorCode.RATE_LIMITED, "slow")
    assert err2.status_code == 429
    err3 = ApiError(ApiErrorCode.AI_PROVIDER_ERROR, "upstream")
    assert err3.status_code == 502
    payload = err.to_error_dict()
    assert payload == {
        "code": "UNAUTHORIZED",
        "message": "bye",
        "details": {},
    }


def test_dummy_pytest_marker() -> None:
    """Ensure pytest collects this module even if all envelope tests are skipped."""

    assert pytest is not None
