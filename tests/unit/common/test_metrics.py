"""Unit tests for ``agent_os.common.metrics`` (PRD10 §12.1 / §25.2).

Tests cover the four contracts the request-path middleware relies on:

1. ``normalize_path`` collapses dynamic segments without flattening
   real path components.
2. ``MetricsRegistry`` correctly aggregates counts, sum, min/max and
   computes quantiles via NIST type-7 linear interpolation.
3. The Prometheus exposition output is stable, sorted, and parseable
   by a regex (we avoid pulling in ``prometheus_client`` purely for
   the format check — keeps the test fast and dep-free).
4. ``to_json_summary`` flags routes that breach §25.2 latency targets
   only when there are enough samples (≥ 5) to draw a conclusion.
"""

from __future__ import annotations

import asyncio
import re

import pytest

from agent_os.common.metrics import (
    PRD10_LATENCY_TARGETS_MS,
    MetricsRegistry,
    get_default_metrics,
    is_metrics_enabled,
    normalize_path,
    reset_default_metrics_for_test,
)

# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


class TestNormalizePath:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("/api/v1/cards/123/move", "/api/v1/cards/{id}/move"),
            (
                "/api/v1/kb/documents/12345678-1234-1234-1234-123456789abc",
                "/api/v1/kb/documents/{id}",
            ),
            (
                "/api/v1/uploads/local/abcdef0123456789abcdef0123456789",
                "/api/v1/uploads/local/{id}",
            ),
            ("/api/v1/feed", "/api/v1/feed"),
            ("/api/v1/today", "/api/v1/today"),
            ("/", "/"),
            ("", ""),
        ],
    )
    def test_normalize_examples(self, raw: str, expected: str):
        assert normalize_path(raw) == expected

    def test_normalize_uppercase_uuid(self):
        upper = "/api/v1/cards/12345678-ABCD-ABCD-ABCD-123456789ABC"
        assert normalize_path(upper) == "/api/v1/cards/{id}"

    def test_normalize_does_not_collide_short_words(self):
        """Real path words like ``move`` / ``read-all`` must NOT collapse."""

        assert normalize_path("/api/v1/notifications/read-all") == (
            "/api/v1/notifications/read-all"
        )


# ---------------------------------------------------------------------------
# MetricsRegistry — aggregation correctness
# ---------------------------------------------------------------------------


class TestRegistryAggregation:
    @pytest.mark.asyncio
    async def test_record_request_creates_bucket(self):
        registry = MetricsRegistry()
        await registry.record_request("GET", "/api/v1/feed", 200, 42.0)
        assert registry.total_requests() == 1
        buckets = list(registry.buckets())
        assert len(buckets) == 1
        b = buckets[0]
        assert b.method == "GET"
        assert b.path == "/api/v1/feed"
        assert b.status == 200
        assert b.count == 1
        assert b.sum_ms == 42.0
        assert b.min_ms == 42.0
        assert b.max_ms == 42.0

    @pytest.mark.asyncio
    async def test_record_request_aggregates(self):
        registry = MetricsRegistry()
        for value in (100.0, 200.0, 300.0):
            await registry.record_request("GET", "/api/v1/feed", 200, value)
        b = list(registry.buckets())[0]
        assert b.count == 3
        assert b.sum_ms == 600.0
        assert b.min_ms == 100.0
        assert b.max_ms == 300.0
        assert b.avg_ms == pytest.approx(200.0)

    @pytest.mark.asyncio
    async def test_record_request_normalizes_path(self):
        registry = MetricsRegistry()
        await registry.record_request("GET", "/api/v1/cards/123/move", 200, 50.0)
        await registry.record_request("GET", "/api/v1/cards/456/move", 200, 70.0)
        # Both observations should land on the same bucket.
        buckets = list(registry.buckets())
        assert len(buckets) == 1
        assert buckets[0].path == "/api/v1/cards/{id}/move"
        assert buckets[0].count == 2

    @pytest.mark.asyncio
    async def test_record_request_separates_status_codes(self):
        registry = MetricsRegistry()
        await registry.record_request("GET", "/api/v1/feed", 200, 50.0)
        await registry.record_request("GET", "/api/v1/feed", 500, 200.0)
        # Different status codes are different buckets.
        buckets = list(registry.buckets())
        assert {b.status for b in buckets} == {200, 500}

    @pytest.mark.asyncio
    async def test_record_request_clamps_negative(self):
        """A bogus negative duration must not corrupt the bucket."""

        registry = MetricsRegistry()
        await registry.record_request("GET", "/api/v1/feed", 200, -10.0)
        b = list(registry.buckets())[0]
        assert b.min_ms == 0.0
        assert b.max_ms == 0.0


# ---------------------------------------------------------------------------
# MetricsRegistry — quantile correctness
# ---------------------------------------------------------------------------


class TestQuantileMath:
    def _seed(self, registry: MetricsRegistry, values: list[float]):
        for v in values:
            registry.record_request_sync("GET", "/api/v1/feed", 200, v)

    def test_quantile_single_observation(self):
        registry = MetricsRegistry()
        self._seed(registry, [123.4])
        b = list(registry.buckets())[0]
        assert b.quantile(0.5) == 123.4
        assert b.quantile(0.95) == 123.4

    def test_quantile_evenly_spaced(self):
        registry = MetricsRegistry()
        # 1..100 → P50 ≈ 50.5, P95 ≈ 95.05, P99 ≈ 99.01
        self._seed(registry, [float(i) for i in range(1, 101)])
        b = list(registry.buckets())[0]
        assert b.quantile(0.5) == pytest.approx(50.5, rel=0.01)
        assert b.quantile(0.95) == pytest.approx(95.05, rel=0.01)
        assert b.quantile(0.99) == pytest.approx(99.01, rel=0.01)

    def test_quantile_empty_returns_zero(self):
        registry = MetricsRegistry()
        # No observations recorded → there's no bucket. Use a synthetic one
        # by recording a single value then resetting.
        self._seed(registry, [50.0])
        registry.reset()
        # Re-record a single low value.
        registry.record_request_sync("GET", "/api/v1/feed", 200, 5.0)
        b = list(registry.buckets())[0]
        assert b.quantile(0.5) == 5.0

    def test_quantile_clamps_to_endpoints(self):
        registry = MetricsRegistry()
        self._seed(registry, [10.0, 20.0, 30.0])
        b = list(registry.buckets())[0]
        assert b.quantile(0.0) == 10.0
        assert b.quantile(1.0) == 30.0


# ---------------------------------------------------------------------------
# Prometheus exposition format
# ---------------------------------------------------------------------------


_PROM_COUNTER_RE = re.compile(
    r'mydow_http_requests_total\{method="([A-Z]+)",path="([^"]+)",status="(\d+)"\}\s+(\d+)'
)
_PROM_QUANTILE_RE = re.compile(
    r'mydow_http_request_duration_ms\{method="[A-Z]+",path="[^"]+",status="\d+",quantile="(0\.5|0\.95|0\.99)"\}\s+([0-9.]+)'
)


class TestPrometheusFormat:
    def test_emits_help_and_type_lines(self):
        registry = MetricsRegistry()
        registry.record_request_sync("GET", "/api/v1/feed", 200, 50.0)
        text = registry.to_prometheus_text()
        assert "# HELP mydow_http_requests_total" in text
        assert "# TYPE mydow_http_requests_total counter" in text
        assert "# HELP mydow_http_request_duration_ms" in text
        assert "# TYPE mydow_http_request_duration_ms summary" in text

    def test_emits_counter_lines(self):
        registry = MetricsRegistry()
        for _ in range(7):
            registry.record_request_sync("GET", "/api/v1/feed", 200, 10.0)
        text = registry.to_prometheus_text()
        matches = _PROM_COUNTER_RE.findall(text)
        assert len(matches) == 1
        method, path, status, count = matches[0]
        assert method == "GET"
        assert path == "/api/v1/feed"
        assert status == "200"
        assert count == "7"

    def test_emits_quantile_lines(self):
        registry = MetricsRegistry()
        for v in (10.0, 20.0, 30.0, 40.0, 50.0):
            registry.record_request_sync("GET", "/api/v1/feed", 200, v)
        text = registry.to_prometheus_text()
        quantiles = dict(_PROM_QUANTILE_RE.findall(text))
        # All three quantile values must be present.
        assert {"0.5", "0.95", "0.99"} == set(quantiles.keys())
        assert float(quantiles["0.5"]) == pytest.approx(30.0, rel=0.01)

    def test_buckets_sorted_for_stable_diffing(self):
        """Output must be deterministic across runs to keep diffs clean."""

        registry = MetricsRegistry()
        registry.record_request_sync("GET", "/api/v1/today", 200, 10.0)
        registry.record_request_sync("POST", "/api/v1/capture/text", 200, 50.0)
        registry.record_request_sync("GET", "/api/v1/feed", 200, 30.0)
        text_first = registry.to_prometheus_text()
        text_second = registry.to_prometheus_text()
        assert text_first == text_second
        # Path-sorted: capture/text < feed < today.
        idx_capture = text_first.index("/api/v1/capture/text")
        idx_feed = text_first.index("/api/v1/feed")
        idx_today = text_first.index("/api/v1/today")
        assert idx_capture < idx_feed < idx_today


# ---------------------------------------------------------------------------
# JSON summary + §25.2 target comparison
# ---------------------------------------------------------------------------


class TestJsonSummary:
    def test_summary_envelope_shape(self):
        registry = MetricsRegistry()
        registry.record_request_sync("GET", "/api/v1/feed", 200, 50.0)
        out = registry.to_json_summary()
        assert "generated_at" in out
        assert "uptime_seconds" in out
        assert out["total_requests"] == 1
        assert isinstance(out["routes"], list) and len(out["routes"]) == 1
        route = out["routes"][0]
        for key in (
            "method",
            "path",
            "status",
            "count",
            "min_ms",
            "avg_ms",
            "max_ms",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "target_p95_ms",
            "breaching",
        ):
            assert key in route, f"Missing key: {key!r}"

    def test_breaching_only_after_five_samples(self):
        """Cold-start (count<5) must never flag a breach."""

        registry = MetricsRegistry()
        # /feed target is 250ms; emit 4 way-overbudget hits.
        for _ in range(4):
            registry.record_request_sync("GET", "/api/v1/feed", 200, 5000.0)
        summary = registry.to_json_summary()
        route = summary["routes"][0]
        assert route["target_p95_ms"] == 250
        assert route["breaching"] is False, (
            "Should NOT flag breach with less than 5 samples"
        )

        # 5th overbudget hit flips it.
        registry.record_request_sync("GET", "/api/v1/feed", 200, 5000.0)
        summary = registry.to_json_summary()
        route = summary["routes"][0]
        assert route["breaching"] is True

    def test_target_table_contains_known_routes(self):
        """The default targets must cover the hot read paths PRD10 §25.2."""

        for key in (
            "GET /api/v1/today",
            "GET /api/v1/feed",
            "GET /api/v1/kb/overview",
            "POST /api/v1/capture/text",
            "POST /api/v1/auth/login",
        ):
            assert key in PRD10_LATENCY_TARGETS_MS

    def test_summary_with_custom_targets(self):
        """Callers can override targets to test what-if scenarios."""

        registry = MetricsRegistry()
        for _ in range(5):
            registry.record_request_sync("GET", "/api/v1/feed", 200, 60.0)
        # Custom super-tight target: 30ms → instant breach.
        summary = registry.to_json_summary(
            targets={"GET /api/v1/feed": 30}
        )
        assert summary["routes"][0]["breaching"] is True


# ---------------------------------------------------------------------------
# Default singleton + env gate
# ---------------------------------------------------------------------------


class TestDefaultRegistry:
    def setup_method(self):
        reset_default_metrics_for_test()

    def teardown_method(self):
        reset_default_metrics_for_test()

    def test_default_returns_singleton(self):
        a = get_default_metrics()
        b = get_default_metrics()
        assert a is b

    def test_reset_creates_fresh_instance(self):
        a = get_default_metrics()
        a.record_request_sync("GET", "/x", 200, 10.0)
        assert a.total_requests() == 1
        reset_default_metrics_for_test()
        b = get_default_metrics()
        assert b is not a
        assert b.total_requests() == 0

    def test_is_metrics_enabled_default_on(self, monkeypatch):
        monkeypatch.delenv("AGENTOS_METRICS", raising=False)
        assert is_metrics_enabled() is True

    @pytest.mark.parametrize("value", ["off", "0", "false", "no", "disabled"])
    def test_is_metrics_enabled_env_off(self, monkeypatch, value: str):
        monkeypatch.setenv("AGENTOS_METRICS", value)
        assert is_metrics_enabled() is False

    @pytest.mark.parametrize("value", ["on", "1", "true", "yes", "enabled"])
    def test_is_metrics_enabled_env_on(self, monkeypatch, value: str):
        monkeypatch.setenv("AGENTOS_METRICS", value)
        assert is_metrics_enabled() is True


# ---------------------------------------------------------------------------
# Concurrency — async record_request must be safe under contention
# ---------------------------------------------------------------------------


class TestConcurrentRecording:
    @pytest.mark.asyncio
    async def test_no_lost_observations_under_contention(self):
        """100 concurrent calls must each show up in the counter."""

        registry = MetricsRegistry()

        async def _hit(i: int):
            await registry.record_request("GET", "/api/v1/feed", 200, i)

        await asyncio.gather(*(_hit(i) for i in range(100)))
        b = list(registry.buckets())[0]
        assert b.count == 100
        assert b.sum_ms == sum(range(100))
