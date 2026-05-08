"""Integration tests for PRD10 §12.1 API metrics endpoints.

These tests drive the real FastAPI app via httpx + ASGITransport so we
exercise the same middleware stack uvicorn would in production:
``RequestIdMiddleware`` → ``RateLimitMiddleware`` → ``Prd10AccessLogMiddleware``.

What we assert (per scenario):

* ``GET /metrics``
    1. 200 + ``Content-Type: text/plain; version=0.0.4`` (Prometheus
       exposition format).
    2. Body contains both metric families (``mydow_http_requests_total``
       and ``mydow_http_request_duration_ms``) once at least one PRD10
       request has been recorded.

* ``GET /api/v1/__metrics__/json``
    1. 200 + JSON with ``total_requests`` >= 1 after a PRD10 hit.
    2. ``routes`` list has at least one entry with the expected keys.
    3. Path normalisation: a request to a UUID-keyed path collapses
       into a single ``{id}`` bucket.

* Middleware integration
    1. A ``GET /api/v1/today`` request (which goes through
       ``Prd10AccessLogMiddleware``) appears in the registry.
    2. ``AGENTOS_METRICS=off`` short-circuits the recorder so the
       registry stays empty.
"""

from __future__ import annotations

import re

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agent_os.common.metrics import (
    get_default_metrics,
    reset_default_metrics_for_test,
)
from agent_os.server.app import app as prd_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Hit the live FastAPI app via httpx."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _isolate_metrics_state():
    """Reset the process-wide registry between tests."""

    reset_default_metrics_for_test()
    yield
    reset_default_metrics_for_test()


# ---------------------------------------------------------------------------
# /metrics — Prometheus exposition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPrometheusEndpoint:
    async def test_metrics_endpoint_serves_prometheus_text(self, client):
        """Endpoint must be reachable + correct content type, even empty."""

        resp = await client.get("/metrics")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/plain" in ct, f"Bad content-type: {ct!r}"
        assert "version=0.0.4" in ct
        # HELP/TYPE lines should always appear (the registry emits
        # both metric families' headers even when empty).
        assert "# HELP mydow_http_requests_total" in resp.text
        assert "# TYPE mydow_http_requests_total counter" in resp.text
        assert "# HELP mydow_http_request_duration_ms" in resp.text

    async def test_metrics_endpoint_excluded_from_openapi(self, client):
        """``/metrics`` should not pollute /openapi.json."""

        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "/metrics" not in spec.get("paths", {})

    async def test_seeded_observations_show_up(self, client):
        """Pre-seeding the registry must surface in the next /metrics scrape."""

        registry = get_default_metrics()
        # Seed three distinct latencies on a single bucket.
        for v in (10.0, 30.0, 50.0):
            registry.record_request_sync("GET", "/api/v1/feed", 200, v)

        resp = await client.get("/metrics")
        assert resp.status_code == 200
        body = resp.text

        # Counter line must show count=3.
        counter = re.search(
            r'mydow_http_requests_total\{[^}]*path="/api/v1/feed"[^}]*\}\s+(\d+)',
            body,
        )
        assert counter is not None, body
        assert counter.group(1) == "3"

        # Quantile lines for the same bucket must be present.
        assert re.search(
            r'mydow_http_request_duration_ms\{[^}]*quantile="0\.95"[^}]*\}',
            body,
        )

    async def test_metrics_endpoint_does_not_record_itself(self, client):
        """Scraping must not pollute the registry with /metrics traffic."""

        # /metrics is NOT a PRD10 prefix, so it bypasses the access log
        # middleware entirely. Hit it 3 times — registry stays empty.
        for _ in range(3):
            await client.get("/metrics")
        assert get_default_metrics().total_requests() == 0


# ---------------------------------------------------------------------------
# /api/v1/__metrics__/json — operator-facing summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestJsonMetricsEndpoint:
    async def test_json_endpoint_envelope_shape(self, client):
        resp = await client.get("/api/v1/__metrics__/json")
        assert resp.status_code == 200
        body = resp.json()
        assert "generated_at" in body
        assert "uptime_seconds" in body
        assert "total_requests" in body
        assert isinstance(body["routes"], list)

    async def test_json_endpoint_excluded_from_openapi(self, client):
        resp = await client.get("/openapi.json")
        spec = resp.json()
        assert "/api/v1/__metrics__/json" not in spec.get("paths", {})

    async def test_json_endpoint_bypasses_request_id_envelope(self, client):
        """The metrics summary is plain JSON, not a PRD10 envelope.

        We expose it under ``__metrics__`` so it does not get wrapped
        in ``{success, data, request_id}``. That keeps the format
        Prometheus-compatible (callers parse a flat object).
        """

        resp = await client.get("/api/v1/__metrics__/json")
        body = resp.json()
        assert "success" not in body
        assert "data" not in body
        assert "routes" in body  # flat shape

    async def test_seeded_routes_round_trip(self, client):
        registry = get_default_metrics()
        for v in (12.0, 24.0, 48.0, 96.0, 144.0):
            registry.record_request_sync("GET", "/api/v1/feed", 200, v)

        resp = await client.get("/api/v1/__metrics__/json")
        body = resp.json()
        assert body["total_requests"] == 5
        feed = next((r for r in body["routes"] if r["path"] == "/api/v1/feed"), None)
        assert feed is not None
        assert feed["count"] == 5
        # P50 of (12,24,48,96,144) — type 7 quantile interpolation.
        assert feed["p50_ms"] == pytest.approx(48.0, rel=0.05)


# ---------------------------------------------------------------------------
# Middleware integration — real PRD10 traffic flows into the registry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMiddlewareIntegration:
    async def test_today_request_records_into_registry(
        self, client, monkeypatch
    ):
        """A real request through ``Prd10AccessLogMiddleware`` must record."""

        monkeypatch.setenv("AGENTOS_METRICS", "on")
        # /api/v1/today requires auth, so it'll 401 — that's fine, the
        # observation is still recorded with status=401.
        resp = await client.get("/api/v1/today")
        assert resp.status_code in (401, 403)

        registry = get_default_metrics()
        assert registry.total_requests() >= 1
        # The bucket should be present and tagged with the right method.
        buckets = list(registry.buckets())
        today_bucket = next(
            (b for b in buckets if b.path == "/api/v1/today"), None
        )
        assert today_bucket is not None, [
            (b.method, b.path, b.status) for b in buckets
        ]
        assert today_bucket.method == "GET"
        assert today_bucket.status in (401, 403)
        assert today_bucket.count >= 1

    async def test_path_normalization_collapses_uuid_segments(
        self, client, monkeypatch
    ):
        """Two requests to UUID-keyed routes land on the same bucket."""

        monkeypatch.setenv("AGENTOS_METRICS", "on")
        for _ in range(2):
            await client.get(
                "/api/v1/cards/12345678-1234-1234-1234-123456789abc"
            )

        registry = get_default_metrics()
        cards_buckets = [
            b for b in registry.buckets() if b.path.startswith("/api/v1/cards")
        ]
        assert len(cards_buckets) == 1, [(b.path, b.count) for b in cards_buckets]
        assert cards_buckets[0].path == "/api/v1/cards/{id}"
        assert cards_buckets[0].count == 2

    async def test_metrics_off_skips_recording(self, client, monkeypatch):
        """``AGENTOS_METRICS=off`` short-circuits the recorder."""

        monkeypatch.setenv("AGENTOS_METRICS", "off")
        await client.get("/api/v1/today")
        # Nothing recorded.
        assert get_default_metrics().total_requests() == 0
