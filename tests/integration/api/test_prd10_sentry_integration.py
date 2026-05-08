"""PRD10 §11.5 — integration tests for Sentry wiring on the live FastAPI app.

These tests verify end-to-end:

1. The FastAPI app boots cleanly when ``SENTRY_DSN`` is unset (default).
   No `sentry_sdk.init` is invoked.
2. The ``/ready`` endpoint exposes ``observability.sentry`` with the
   correct ``enabled`` flag and ``environment`` / ``release`` echo.
3. When ``SENTRY_DSN`` is present (mocked SDK), the app initializes
   Sentry exactly once and ``/ready`` reflects ``enabled=True``.

The Sentry SDK itself is mocked to avoid any real network traffic.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from agent_os.common.sentry_setup import (
    init_sentry,
    is_sentry_enabled,
    reset_sentry_state_for_test,
)


@pytest.fixture(autouse=True)
def _reset_sentry_state():
    reset_sentry_state_for_test()
    yield
    reset_sentry_state_for_test()


@pytest.mark.asyncio
async def test_ready_reports_sentry_disabled_by_default(monkeypatch):
    """No DSN env → ``observability.sentry.enabled = False`` and `dependencies.sentry == "disabled"`."""

    monkeypatch.delenv("SENTRY_DSN", raising=False)

    # Re-init under cleared env so state is current.
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry(force=True)
        mock_sdk.init.assert_not_called()

    from agent_os.server.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get("/ready")
    # /ready may return 200 (DB ok) or 503 (DB down in some env). Both
    # carry the observability payload.
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "observability" in body
    sentry_block = body["observability"]["sentry"]
    assert sentry_block["enabled"] is False
    assert body["dependencies"]["sentry"] == "disabled"


@pytest.mark.asyncio
async def test_ready_reports_sentry_active_when_dsn_set(monkeypatch):
    """With DSN set + mocked SDK, ``/ready`` shows ``enabled=True`` and reports env."""

    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_RELEASE", "v0.0.1")

    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry(force=True)
        mock_sdk.init.assert_called_once()

    assert is_sentry_enabled() is True

    from agent_os.server.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get("/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    sentry_block = body["observability"]["sentry"]
    assert sentry_block["enabled"] is True
    assert sentry_block["environment"] == "staging"
    assert sentry_block["release"] == "v0.0.1"
    assert body["dependencies"]["sentry"] == "active"


@pytest.mark.asyncio
async def test_health_endpoint_unchanged():
    """``/health`` is the liveness probe; it must stay minimal and never depend on Sentry."""

    from agent_os.server.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "healthy"}
