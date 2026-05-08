"""PRD10 §12.1 / §25.2 — API metrics & P95 monitoring.

A lightweight, dependency-free metrics collector that lets us answer
investor-facing questions like "are we hitting our P95 latency targets?"
without standing up a Prometheus server. The registry exposes both:

* **Prometheus exposition format** (``/metrics``) — drop-in scrape
  target for production monitoring stacks.
* **JSON summary** (``/api/v1/__metrics__/json``) — human-readable
  per-route P50/P95/P99 + counts, with a side-by-side comparison
  against the PRD10 §25.2 latency targets.

Design constraints:

1. **Zero new dependencies.** ``prometheus_client`` would be the
   obvious choice but pulling it in just for this would bloat the
   image. We instead export the wire format directly.
2. **Bounded memory.** Naively keeping every observation per route
   blows up under load. We sample into a fixed-size ring buffer per
   bucket (default 1024 observations) and compute quantiles on the
   sampled data.
3. **Stable label cardinality.** Path templates with UUIDs or numeric
   IDs would explode the label space; ``_normalize_path`` collapses
   them back to ``{id}`` segments so dashboards stay readable.
4. **asyncio-safe.** Multiple concurrent requests must not corrupt
   the counters; we use a single ``asyncio.Lock`` per bucket.
5. **Off by default in tests.** Set ``AGENTOS_METRICS=off`` to keep
   imports cheap; in production keep the default ``on``.
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

# Public API exposed via ``agent_os.common`` (see __init__.py edit below).
__all__ = [
    "MetricsRegistry",
    "PRD10_LATENCY_TARGETS_MS",
    "is_metrics_enabled",
    "get_default_metrics",
    "reset_default_metrics_for_test",
    "normalize_path",
]


# ---------------------------------------------------------------------------
# §25.2 latency targets (P95, in milliseconds).
#
# These mirror the PRD10 performance budget. Each entry maps a path prefix
# to a P95 budget so the JSON summary can flag regressions visually
# (``"target_ms": 200, "p95_ms": 312`` → ``"breaching": true``).
# ---------------------------------------------------------------------------

PRD10_LATENCY_TARGETS_MS: dict[str, int] = {
    # Hot read paths must feel instant.
    "GET /api/v1/today": 200,
    "GET /api/v1/feed": 250,
    "GET /api/v1/kb/overview": 200,
    "GET /api/v1/notifications": 250,
    "GET /api/v1/search": 400,
    # Capture / commit can do work but should still be sub-second.
    "POST /api/v1/capture/text": 500,
    "POST /api/v1/capture/link": 600,
    "POST /api/v1/capture/file/commit": 800,
    # AI conversation orchestration (excluding LLM stream itself).
    "POST /api/v1/ai/conversations": 400,
    "POST /api/v1/ai/conversations/{id}/messages": 600,
    # Skill execution kickoff (queue-only, not the actual run).
    "POST /api/v1/skills/{id}/run": 400,
    # Auth surface.
    "POST /api/v1/auth/login": 600,
    "POST /api/v1/auth/register": 800,
    # Health probes — these are expected to be near-instant.
    "GET /health": 50,
    "GET /ready": 100,
}


# ---------------------------------------------------------------------------
# Path normalization
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"^\d+$")
# Long opaque identifiers (e.g. capture inbox tokens) come as 16+ hex chars.
_OPAQUE_HEX_RE = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)


def normalize_path(path: str) -> str:
    """Collapse path segments that look like dynamic IDs into ``{id}``.

    Examples
    --------
    >>> normalize_path("/api/v1/cards/123/move")
    '/api/v1/cards/{id}/move'
    >>> normalize_path(
    ...     "/api/v1/kb/documents/12345678-1234-1234-1234-123456789abc"
    ... )
    '/api/v1/kb/documents/{id}'
    >>> normalize_path("/api/v1/feed")
    '/api/v1/feed'
    """

    if not path:
        return path

    parts = path.split("/")
    out: list[str] = []
    for segment in parts:
        if not segment:
            out.append(segment)
            continue
        if (
            _UUID_RE.match(segment)
            or _NUMERIC_RE.match(segment)
            or _OPAQUE_HEX_RE.match(segment)
        ):
            out.append("{id}")
        else:
            out.append(segment)
    return "/".join(out)


# ---------------------------------------------------------------------------
# Bucket model
# ---------------------------------------------------------------------------


@dataclass
class _RouteBucket:
    """In-memory aggregation for one (method, path_template, status) triplet."""

    method: str
    path: str
    status: int
    count: int = 0
    sum_ms: float = 0.0
    min_ms: float = math.inf
    max_ms: float = 0.0
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=1024))

    def observe(self, duration_ms: float) -> None:
        self.count += 1
        self.sum_ms += duration_ms
        if duration_ms < self.min_ms:
            self.min_ms = duration_ms
        if duration_ms > self.max_ms:
            self.max_ms = duration_ms
        self.samples.append(duration_ms)

    @property
    def avg_ms(self) -> float:
        return self.sum_ms / self.count if self.count else 0.0

    def quantile(self, q: float) -> float:
        """Return the q-th quantile of the sampled observations.

        ``q`` is in [0, 1]. Linear interpolation between adjacent
        ranks (NIST type 7 — same flavour as numpy default).
        """

        n = len(self.samples)
        if n == 0:
            return 0.0
        if n == 1:
            return float(self.samples[0])
        ordered = sorted(self.samples)
        # Clamp into [0, 1] so callers can't index out of range.
        if q <= 0:
            return float(ordered[0])
        if q >= 1:
            return float(ordered[-1])
        rank = q * (n - 1)
        lo = int(math.floor(rank))
        hi = int(math.ceil(rank))
        if lo == hi:
            return float(ordered[lo])
        weight = rank - lo
        return float(ordered[lo] * (1 - weight) + ordered[hi] * weight)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class MetricsRegistry:
    """A single-process, asyncio-safe metrics registry.

    Holds one ``_RouteBucket`` per (method, path_template, status) triple.
    ``record_request`` is non-blocking from the request path: it serializes
    on a single ``asyncio.Lock`` but each call is O(1).

    Use ``get_default_metrics()`` for the process-wide singleton; tests
    use ``MetricsRegistry()`` directly + ``reset_default_metrics_for_test``
    to keep state isolated.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str, int], _RouteBucket] = {}
        self._lock = asyncio.Lock()
        self._created_at = time.time()

    # ---- write path -----------------------------------------------------

    async def record_request(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
    ) -> None:
        """Record a single request observation.

        The ``path`` is normalized before storage so dynamic segments
        (UUIDs, numeric IDs) collapse to ``{id}`` and don't blow up the
        label space.
        """

        if duration_ms < 0:
            duration_ms = 0.0
        path_template = normalize_path(path or "/")
        key = (method or "GET", path_template, int(status))
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _RouteBucket(method=key[0], path=key[1], status=key[2])
                self._buckets[key] = bucket
            bucket.observe(float(duration_ms))

    def record_request_sync(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
    ) -> None:
        """Synchronous variant — useful for non-async callers.

        Skips the lock (single-thread assumption inside async server). The
        request middleware uses the async variant; this helper exists so
        offline scripts (smoke probes, seed runners) can also feed the
        registry without spinning up an event loop.
        """

        if duration_ms < 0:
            duration_ms = 0.0
        path_template = normalize_path(path or "/")
        key = (method or "GET", path_template, int(status))
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _RouteBucket(method=key[0], path=key[1], status=key[2])
            self._buckets[key] = bucket
        bucket.observe(float(duration_ms))

    # ---- read path ------------------------------------------------------

    def buckets(self) -> Iterable[_RouteBucket]:
        # Stable ordering for deterministic Prometheus output.
        return sorted(
            self._buckets.values(),
            key=lambda b: (b.path, b.method, b.status),
        )

    def total_requests(self) -> int:
        return sum(b.count for b in self._buckets.values())

    def reset(self) -> None:
        self._buckets.clear()
        self._created_at = time.time()

    # ---- exposition formats --------------------------------------------

    def to_prometheus_text(self) -> str:
        """Return a Prometheus exposition text payload.

        Two metrics are emitted:

        * ``mydow_http_requests_total`` (counter) — request count per
          method/path/status combination.
        * ``mydow_http_request_duration_ms`` (summary) — per-bucket sum +
          count + min + max + p50/p95/p99 quantile labels.
        """

        out: list[str] = []

        # ----- counter -----
        out.append("# HELP mydow_http_requests_total Total number of HTTP requests.")
        out.append("# TYPE mydow_http_requests_total counter")
        for bucket in self.buckets():
            out.append(
                f'mydow_http_requests_total{{method="{bucket.method}",'
                f'path="{_escape_label(bucket.path)}",status="{bucket.status}"}} '
                f"{bucket.count}"
            )

        # ----- summary -----
        out.append(
            "# HELP mydow_http_request_duration_ms HTTP request duration in milliseconds."
        )
        out.append("# TYPE mydow_http_request_duration_ms summary")
        for bucket in self.buckets():
            base = (
                f'method="{bucket.method}",path="{_escape_label(bucket.path)}"'
                f',status="{bucket.status}"'
            )
            for q, value in (
                (0.5, bucket.quantile(0.5)),
                (0.95, bucket.quantile(0.95)),
                (0.99, bucket.quantile(0.99)),
            ):
                out.append(
                    f'mydow_http_request_duration_ms{{{base},quantile="{q}"}} '
                    f"{_format_float(value)}"
                )
            out.append(
                f"mydow_http_request_duration_ms_count{{{base}}} {bucket.count}"
            )
            out.append(
                f"mydow_http_request_duration_ms_sum{{{base}}} "
                f"{_format_float(bucket.sum_ms)}"
            )

        # Trailing newline so ``curl /metrics`` ends cleanly.
        out.append("")
        return "\n".join(out)

    def to_json_summary(
        self,
        *,
        targets: dict[str, int] | None = None,
    ) -> dict:
        """Return a structured JSON summary suitable for human consumption.

        The optional ``targets`` argument lets callers pass a custom
        budget table; ``PRD10_LATENCY_TARGETS_MS`` is used by default.
        Each route entry includes the targeted P95 (when known) and a
        ``breaching`` flag flipped on when the observed P95 exceeds the
        target with at least 5 samples (avoids alarming on cold starts).
        """

        targets_to_use = targets if targets is not None else PRD10_LATENCY_TARGETS_MS
        items: list[dict] = []
        for bucket in self.buckets():
            target_key = f"{bucket.method} {bucket.path}"
            target = targets_to_use.get(target_key)
            p95 = bucket.quantile(0.95)
            breaching = False
            if target is not None and bucket.count >= 5 and p95 > target:
                breaching = True
            items.append(
                {
                    "method": bucket.method,
                    "path": bucket.path,
                    "status": bucket.status,
                    "count": bucket.count,
                    "min_ms": _round(bucket.min_ms),
                    "avg_ms": _round(bucket.avg_ms),
                    "max_ms": _round(bucket.max_ms),
                    "p50_ms": _round(bucket.quantile(0.5)),
                    "p95_ms": _round(p95),
                    "p99_ms": _round(bucket.quantile(0.99)),
                    "target_p95_ms": target,
                    "breaching": breaching,
                }
            )
        return {
            "generated_at": time.time(),
            "uptime_seconds": time.time() - self._created_at,
            "total_requests": self.total_requests(),
            "routes": items,
        }


# ---------------------------------------------------------------------------
# Default registry + env gate
# ---------------------------------------------------------------------------


_default_registry: MetricsRegistry | None = None


def get_default_metrics() -> MetricsRegistry:
    """Return the process-wide singleton metrics registry.

    Created lazily on first use so module import stays cheap. Tests
    should call ``reset_default_metrics_for_test`` between runs to
    keep state from leaking between cases.
    """

    global _default_registry
    if _default_registry is None:
        _default_registry = MetricsRegistry()
    return _default_registry


def reset_default_metrics_for_test() -> None:
    """Drop the process-wide registry so the next access rebuilds it."""

    global _default_registry
    if _default_registry is not None:
        _default_registry.reset()
    _default_registry = None


def is_metrics_enabled() -> bool:
    """Return ``True`` when ``AGENTOS_METRICS`` is truthy (default ``on``).

    PRD10 §25.2 expects metrics to be available in production by default;
    the off-switch exists so test runners that import the app for
    OpenAPI generation don't spin up a registry they won't use.
    """

    raw = os.getenv("AGENTOS_METRICS", "on").strip().lower()
    return raw in ("1", "on", "true", "yes", "enabled")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape_label(value: str) -> str:
    """Escape characters that aren't safe inside a Prometheus label value."""

    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _format_float(value: float) -> str:
    """Format a float in a way Prometheus parsers accept (no trailing zeros)."""

    if value == 0:
        return "0"
    if math.isnan(value) or math.isinf(value):
        return "0"
    if abs(value) < 1:
        return f"{value:.6f}"
    return f"{value:.3f}"


def _round(value: float) -> float:
    """Return the value rounded to 2 decimal places (or ``0`` for inf)."""

    if value is None or math.isinf(value) or math.isnan(value):
        return 0.0
    return round(float(value), 2)
