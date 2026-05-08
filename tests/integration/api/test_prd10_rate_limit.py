"""PRD10 §29 — integration tests for ``RateLimitMiddleware``.

These exercises run the middleware end-to-end through a small FastAPI app
with explicit policies so we can assert:

1. **Default-OFF.** With ``AGENTOS_RATE_LIMIT`` unset the middleware lets
   every request through and never adds 429s, even after thousands of hits.
2. **429 envelope.** When triggered the middleware returns the canonical
   PRD10 ``{success: false, error: {code: "RATE_LIMITED", ...}}`` body
   with ``Retry-After`` and ``X-RateLimit-*`` headers.
3. **Per-key buckets.** Different IPs / different bearer tokens have
   independent quotas.
4. **Refill.** Buckets refill over wall time so legitimate traffic
   recovers.
5. **Inert path is safe.** Disabling the middleware (``enabled=False``)
   leaves response headers untouched and never returns 429.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agent_os.common import (
    InMemoryRateLimitStore,
    RateLimitMiddleware,
    RateLimitPolicy,
    RequestIdMiddleware,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(
    *,
    policies: tuple[RateLimitPolicy, ...],
    enabled: bool = True,
    store: InMemoryRateLimitStore | None = None,
) -> FastAPI:
    """Construct a minimal app with the rate-limit middleware mounted.

    The ``ping`` route returns a stable PRD10-shaped envelope so callers
    can assert against it; ``echo`` accepts any path so different
    prefixes can hit different policies.
    """

    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        policies=policies,
        store=store or InMemoryRateLimitStore(),
        enabled=enabled,
    )
    app.add_middleware(RequestIdMiddleware)

    @app.get("/api/v1/feed")
    async def feed():
        return {"success": True, "data": {"items": []}, "request_id": "fixed"}

    @app.post("/api/v1/auth/login")
    async def login():
        return {"success": True, "data": {"token": "t"}, "request_id": "fixed"}

    @app.get("/legacy/anything")
    async def legacy():
        return {"ok": True}

    return app


@pytest_asyncio.fixture
async def disabled_client():
    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="strict",
                path_prefixes=("/api/v1/",),
                methods=(),
                capacity=2,
                refill_per_second=0.001,
            ),
        ),
        enabled=False,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def strict_client():
    """Tiny capacity (2) + slow refill so two requests pass and the third 429s."""

    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="strict_global",
                path_prefixes=("/api/v1/",),
                methods=(),
                capacity=2,
                refill_per_second=0.001,
                scope="ip",
            ),
        ),
        enabled=True,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# Default OFF — no 429, no headers added
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_middleware_lets_traffic_through(disabled_client):
    for _ in range(20):
        resp = await disabled_client.get("/api/v1/feed")
        assert resp.status_code == 200
        # When inactive the middleware MUST NOT mutate headers.
        assert "X-RateLimit-Policy" not in resp.headers
        assert "Retry-After" not in resp.headers


# ---------------------------------------------------------------------------
# 429 envelope shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strict_policy_produces_prd10_envelope_after_burst(strict_client):
    # First two requests fit in the bucket.
    for _ in range(2):
        resp = await strict_client.get("/api/v1/feed")
        assert resp.status_code == 200
        assert resp.headers.get("X-RateLimit-Policy") == "strict_global"
        assert resp.headers.get("X-RateLimit-Limit") == "2"

    # Third request is over capacity → 429 with PRD10 envelope.
    resp = await strict_client.get("/api/v1/feed")
    assert resp.status_code == 429
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["details"]["policy"] == "strict_global"
    assert body["error"]["details"]["scope"] == "ip"
    assert body["error"]["details"]["limit"] == 2
    assert body["error"]["details"]["retry_after_seconds"] >= 1
    assert "request_id" in body and body["request_id"]


@pytest.mark.asyncio
async def test_strict_policy_sets_retry_after_and_rate_limit_headers(strict_client):
    for _ in range(2):
        await strict_client.get("/api/v1/feed")
    resp = await strict_client.get("/api/v1/feed")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") is not None
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.headers.get("X-RateLimit-Limit") == "2"
    assert resp.headers.get("X-RateLimit-Remaining") == "0"
    assert resp.headers.get("X-RateLimit-Policy") == "strict_global"
    # Request-id middleware still echoes the id even on 429.
    assert resp.headers.get("X-Request-ID")


# ---------------------------------------------------------------------------
# Independent buckets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_separate_tokens_get_separate_buckets():
    store = InMemoryRateLimitStore()
    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="user_strict",
                path_prefixes=("/api/v1/",),
                methods=(),
                capacity=2,
                refill_per_second=0.001,
                scope="user_or_ip",
            ),
        ),
        enabled=True,
        store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        for _ in range(2):
            r = await c.get("/api/v1/feed", headers={"Authorization": "Bearer alice"})
            assert r.status_code == 200
        # Alice exhausts her bucket.
        r = await c.get("/api/v1/feed", headers={"Authorization": "Bearer alice"})
        assert r.status_code == 429

        # Bob still has full capacity.
        for _ in range(2):
            r = await c.get("/api/v1/feed", headers={"Authorization": "Bearer bob"})
            assert r.status_code == 200
        # Now Bob also exhausts.
        r = await c.get("/api/v1/feed", headers={"Authorization": "Bearer bob"})
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# Refill / recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bucket_refills_after_waiting():
    store = InMemoryRateLimitStore()
    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="quick_refill",
                path_prefixes=("/api/v1/",),
                methods=(),
                capacity=2,
                refill_per_second=20.0,  # ~50ms per token
                scope="ip",
            ),
        ),
        enabled=True,
        store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        for _ in range(2):
            assert (await c.get("/api/v1/feed")).status_code == 200
        assert (await c.get("/api/v1/feed")).status_code == 429
        await asyncio.sleep(0.15)
        # >= 1 token should have refilled by now.
        assert (await c.get("/api/v1/feed")).status_code == 200


# ---------------------------------------------------------------------------
# Method-scoped policies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_only_policy_does_not_throttle_get():
    store = InMemoryRateLimitStore()
    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="login",
                path_prefixes=("/api/v1/auth/login",),
                methods=("POST",),
                capacity=1,
                refill_per_second=0.001,
                scope="ip",
            ),
        ),
        enabled=True,
        store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        # First POST succeeds; second is over capacity.
        assert (await c.post("/api/v1/auth/login")).status_code == 200
        resp = await c.post("/api/v1/auth/login")
        assert resp.status_code == 429
        assert resp.json()["error"]["details"]["policy"] == "login"

        # GET requests against any path don't count against the login bucket.
        for _ in range(5):
            r = await c.get("/api/v1/feed")
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Out-of-scope paths bypass entirely
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paths_outside_policy_prefixes_are_not_throttled():
    store = InMemoryRateLimitStore()
    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="api_only",
                path_prefixes=("/api/v1/",),
                methods=(),
                capacity=1,
                refill_per_second=0.001,
                scope="ip",
            ),
        ),
        enabled=True,
        store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        for _ in range(20):
            r = await c.get("/legacy/anything")
            assert r.status_code == 200
            assert "X-RateLimit-Policy" not in r.headers


# ---------------------------------------------------------------------------
# Default policy table sanity (matches real PRD10 routes)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_policy_blocks_after_login_burst(monkeypatch):
    """Real-world style: hammer login → 429 within configured capacity."""

    monkeypatch.setenv("AGENTOS_RATE_LIMIT", "on")

    # Use a fresh store so this test is independent of any prior state.
    store = InMemoryRateLimitStore()
    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="auth_login",
                path_prefixes=("/api/v1/auth/login",),
                methods=("POST",),
                capacity=10,
                refill_per_second=10 / 60.0,
                scope="ip",
            ),
        ),
        enabled=None,  # delegate to env var
        store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        # 10 fit
        for i in range(10):
            r = await c.post("/api/v1/auth/login")
            assert r.status_code == 200, f"hit {i}: {r.status_code} {r.text}"
        # 11th over capacity -> 429
        r = await c.post("/api/v1/auth/login")
        assert r.status_code == 429
        assert r.headers.get("Retry-After") is not None


@pytest.mark.asyncio
async def test_env_disabled_overrides_module_default(monkeypatch):
    """``AGENTOS_RATE_LIMIT`` unset => ``enabled=None`` middleware is OFF."""

    monkeypatch.delenv("AGENTOS_RATE_LIMIT", raising=False)
    store = InMemoryRateLimitStore()
    app = _build_app(
        policies=(
            RateLimitPolicy(
                name="strict",
                path_prefixes=("/api/v1/",),
                methods=(),
                capacity=1,
                refill_per_second=0.001,
                scope="ip",
            ),
        ),
        enabled=None,
        store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        for _ in range(5):
            r = await c.get("/api/v1/feed")
            assert r.status_code == 200
            assert "X-RateLimit-Policy" not in r.headers
