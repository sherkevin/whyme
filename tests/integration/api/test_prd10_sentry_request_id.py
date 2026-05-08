"""PRD10 §11.5b — RequestIdMiddleware ↔ Sentry scope binding + smoke endpoint.

Two contracts under test:

1. **request_id propagation into Sentry scope.** When Sentry is enabled,
   ``RequestIdMiddleware`` MUST tag the active scope with ``request_id``
   so any ``capture_exception`` inside that request is correlated back to
   the same id we already log. When Sentry is OFF the middleware MUST NOT
   touch the SDK at all.

2. **Smoke endpoint gating.** ``POST /api/v1/__sentry_test__`` must:
   - Be unmounted (404) when ``AGENTOS_SENTRY_TEST`` is unset, even if
     ``SENTRY_DSN`` is set.
   - Be unmounted (404) when ``AGENTOS_SENTRY_TEST=on`` but Sentry is OFF.
   - Be reachable (500 PRD10 envelope) only when both are on.

These rules together prevent accidental data leakage in production while
still giving operators a one-shot smoke check after a deploy.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agent_os.common.middleware import RequestIdMiddleware
from agent_os.common.sentry_setup import (
    init_sentry,
    is_sentry_enabled,
    reset_sentry_state_for_test,
)


@pytest.fixture(autouse=True)
def _clean_sentry_state(monkeypatch):
    reset_sentry_state_for_test()
    for key in (
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_RELEASE",
        "AGENTOS_SENTRY_TEST",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    reset_sentry_state_for_test()


# ---------------------------------------------------------------------------
# RequestIdMiddleware ↔ Sentry scope
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    async def echo():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_request_id_middleware_does_not_touch_sentry_when_disabled():
    """Default (DSN unset, Sentry off) — middleware must not call sentry_sdk."""

    assert is_sentry_enabled() is False

    app = _make_app()
    transport = ASGITransport(app=app)

    with patch("sentry_sdk.set_tag") as mock_set_tag, patch(
        "sentry_sdk.set_context"
    ) as mock_set_context:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            resp = await c.get("/echo")
        assert resp.status_code == 200
        # We must not have touched the SDK at all.
        mock_set_tag.assert_not_called()
        mock_set_context.assert_not_called()
        # Request id is still echoed.
        assert resp.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_request_id_middleware_tags_sentry_scope_when_enabled(monkeypatch):
    """With Sentry enabled, set_tag('request_id', ...) and set_context are called once per request."""

    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")

    with patch("agent_os.common.sentry_setup.sentry_sdk"):
        init_sentry(force=True)
    assert is_sentry_enabled() is True

    app = _make_app()
    transport = ASGITransport(app=app)

    with patch("sentry_sdk.set_tag") as mock_set_tag, patch(
        "sentry_sdk.set_context"
    ) as mock_set_context:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            resp = await c.get("/echo", headers={"X-Request-ID": "req_unit_test_123"})
        assert resp.status_code == 200

        # set_tag called for both request_id and http.method.
        tag_calls = {call.args[0]: call.args[1] for call in mock_set_tag.call_args_list}
        assert tag_calls.get("request_id") == "req_unit_test_123"
        assert tag_calls.get("http.method") == "GET"

        # set_context for the request meta dict.
        ctx_calls = {call.args[0]: call.args[1] for call in mock_set_context.call_args_list}
        assert "request_meta" in ctx_calls
        assert ctx_calls["request_meta"]["request_id"] == "req_unit_test_123"
        assert ctx_calls["request_meta"]["path"] == "/echo"


@pytest.mark.asyncio
async def test_request_id_middleware_resilient_against_sdk_errors(monkeypatch):
    """If Sentry SDK raises, the request must still succeed."""

    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk"):
        init_sentry(force=True)

    app = _make_app()
    transport = ASGITransport(app=app)

    with patch("sentry_sdk.set_tag", side_effect=RuntimeError("sentry boom")):
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            resp = await c.get("/echo")
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID")


# ---------------------------------------------------------------------------
# Smoke endpoint gating
# ---------------------------------------------------------------------------


def test_smoke_endpoint_gated_off_by_default(monkeypatch):
    """No env opt-in + no DSN = endpoint must not mount."""

    monkeypatch.delenv("AGENTOS_SENTRY_TEST", raising=False)
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    from agent_os.common.sentry_test_router import is_sentry_test_endpoint_enabled

    assert is_sentry_test_endpoint_enabled() is False


def test_smoke_endpoint_gated_off_when_only_env_set(monkeypatch):
    """Opt-in env without Sentry init → still off."""

    monkeypatch.setenv("AGENTOS_SENTRY_TEST", "on")
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    reset_sentry_state_for_test()

    from agent_os.common.sentry_test_router import is_sentry_test_endpoint_enabled

    # init_sentry not called -> Sentry remains disabled.
    assert is_sentry_test_endpoint_enabled() is False


def test_smoke_endpoint_gated_off_when_only_sentry_on(monkeypatch):
    """Sentry on but env opt-in not set → still off (must NOT auto-mount)."""

    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.delenv("AGENTOS_SENTRY_TEST", raising=False)
    with patch("agent_os.common.sentry_setup.sentry_sdk"):
        init_sentry(force=True)

    from agent_os.common.sentry_test_router import is_sentry_test_endpoint_enabled

    assert is_sentry_test_endpoint_enabled() is False


def test_smoke_endpoint_active_when_both_set(monkeypatch):
    """Opt-in + Sentry enabled = endpoint mounted."""

    monkeypatch.setenv("AGENTOS_SENTRY_TEST", "on")
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk"):
        init_sentry(force=True)

    from agent_os.common.sentry_test_router import is_sentry_test_endpoint_enabled

    assert is_sentry_test_endpoint_enabled() is True


@pytest.mark.asyncio
async def test_smoke_endpoint_returns_prd10_envelope(monkeypatch):
    """When mounted manually for tests, the endpoint returns a PRD10 envelope."""

    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("AGENTOS_SENTRY_TEST", "on")
    with patch("agent_os.common.sentry_setup.sentry_sdk"):
        init_sentry(force=True)

    from agent_os.common.sentry_test_router import router as sentry_test_router

    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.include_router(sentry_test_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.post("/api/v1/__sentry_test__")

    # FastAPI honors status_code=500 from the route decorator.
    assert resp.status_code == 500
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["details"]["synthetic"] is True
    assert "request_id" in body and body["request_id"]
