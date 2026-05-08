"""PRD10 §29 — global / per-route rate limiting.

Provides an ASGI-friendly token-bucket limiter wired by
``RateLimitMiddleware`` (see ``agent_os/common/middleware.py``).

Design highlights:

* **Default OFF.** The middleware is mounted unconditionally but stays
  inert unless ``AGENTOS_RATE_LIMIT=on`` is set. This keeps the existing
  PRD10 test matrix and the test client happy without per-test toggles.
* **Policy-driven.** Each route prefix maps to a :class:`RateLimitPolicy`
  carrying capacity / refill / scope. The first matching policy (in
  declaration order) wins so specific routes (`auth_login`, `ai_messages`,
  `search`, ...) override the catch-all ``global`` bucket.
* **Pluggable store.** Default is :class:`InMemoryRateLimitStore` — single
  process, asyncio-safe via ``asyncio.Lock``. Multi-instance deployments
  can swap in a Redis-backed store later (PRD10 §29) without touching
  callers; the public ``consume`` contract is the same.
* **PRD10 envelope on 429.** The middleware returns the canonical
  ``{success: false, error: {code: "RATE_LIMITED", ...}}`` body + the
  ``Retry-After`` header so callers (FE / SDK / curl) can back off in a
  uniform way.

Public surface (also exported via ``agent_os.common``):

* :class:`RateLimitPolicy`
* :data:`DEFAULT_POLICIES`
* :class:`InMemoryRateLimitStore`
* :func:`is_rate_limit_enabled`
* :func:`select_policy`
* :func:`derive_key`
* :func:`get_default_store`
* :func:`reset_default_store_for_test`
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass

from starlette.requests import Request

# ---------------------------------------------------------------------------
# Feature toggle
# ---------------------------------------------------------------------------


def is_rate_limit_enabled(env_name: str = "AGENTOS_RATE_LIMIT") -> bool:
    """Return ``True`` if the rate-limit middleware should actively block.

    Off by default — the production deploy explicitly opts in via
    ``AGENTOS_RATE_LIMIT=on``. Accepts the usual truthy aliases (`1`, `on`,
    `true`, `yes`, `enabled`) case-insensitively.
    """

    raw = os.getenv(env_name, "").strip().lower()
    return raw in ("1", "on", "true", "yes", "enabled")


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateLimitPolicy:
    """A token-bucket policy bound to one or more route prefixes."""

    name: str
    path_prefixes: tuple[str, ...]
    methods: tuple[str, ...]
    capacity: int
    refill_per_second: float
    scope: str = "ip"

    def matches(self, path: str, method: str) -> bool:
        if not path.startswith(self.path_prefixes):
            return False
        if self.methods and method.upper() not in self.methods:
            return False
        return True


# PRD10 §29 default policy table. Specific policies must come BEFORE the
# catch-all ``global`` so they win the ``select_policy`` first-match. The
# numbers below are intentionally generous so legitimate traffic from a
# single tab never trips them; aggressive throttling should be configured
# operationally rather than baked into defaults.
DEFAULT_POLICIES: tuple[RateLimitPolicy, ...] = (
    # Auth surface — strictest, IP-scoped (no token yet at login/register).
    RateLimitPolicy(
        name="auth_login",
        path_prefixes=("/api/v1/auth/login",),
        methods=("POST",),
        capacity=10,
        refill_per_second=10 / 60.0,  # 10 req / minute
        scope="ip",
    ),
    RateLimitPolicy(
        name="auth_register",
        path_prefixes=("/api/v1/auth/register",),
        methods=("POST",),
        capacity=5,
        refill_per_second=5 / 60.0,  # 5 req / minute
        scope="ip",
    ),
    RateLimitPolicy(
        name="auth_send_code",
        path_prefixes=(
            "/api/v1/auth/send-code",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/resend-verification",
        ),
        methods=("POST",),
        capacity=5,
        refill_per_second=5 / 60.0,
        scope="ip",
    ),
    # AI is per-user (or per-IP for unauthenticated edge cases) — guards
    # cost runaway from a single account hammering the LLM provider.
    RateLimitPolicy(
        name="ai_messages",
        path_prefixes=(
            "/api/v1/ai/conversations/",
            "/api/v1/ai/messages/",
        ),
        methods=("POST",),
        capacity=30,
        refill_per_second=30 / 60.0,  # 30 req / minute / user
        scope="user_or_ip",
    ),
    # Search — read-heavy but cheaper than AI; user/IP scoped.
    RateLimitPolicy(
        name="search",
        path_prefixes=("/api/v1/search",),
        methods=(),
        capacity=120,
        refill_per_second=120 / 60.0,  # 120 req / minute / user
        scope="user_or_ip",
    ),
    # Capture / upload — user-scoped to keep one account from flooding.
    RateLimitPolicy(
        name="capture",
        path_prefixes=("/api/v1/capture", "/api/v1/uploads"),
        methods=("POST", "PUT"),
        capacity=120,
        refill_per_second=120 / 60.0,
        scope="user_or_ip",
    ),
    # Catch-all global per-IP cap (above the per-user buckets).
    RateLimitPolicy(
        name="global",
        path_prefixes=("/api/v1/",),
        methods=(),
        capacity=600,
        refill_per_second=600 / 60.0,  # 600 req / minute / IP
        scope="ip",
    ),
)


def select_policy(
    path: str,
    method: str,
    *,
    policies: Iterable[RateLimitPolicy] | None = None,
) -> RateLimitPolicy | None:
    """Return the first policy whose path/method matches, else ``None``."""

    for policy in policies or DEFAULT_POLICIES:
        if policy.matches(path, method):
            return policy
    return None


def derive_key(request: Request, policy: RateLimitPolicy) -> str:
    """Build the bucket key for ``request`` under ``policy``.

    Scope semantics:

    * ``global`` — single shared bucket for every caller. Useful when you
      want a hard cap regardless of identity (e.g. a feature flag tap).
    * ``ip`` — per remote IP.
    * ``user`` — per Authorization bearer token (treated as user proxy).
      Falls back to anonymous IP when no token is present so the bucket
      always has a stable key.
    * ``user_or_ip`` — prefer token; else fall back to per-IP.
    """

    if policy.scope == "global":
        return f"global:{policy.name}"

    auth_token: str | None = None
    if policy.scope in ("user", "user_or_ip"):
        auth_header = (
            request.headers.get("authorization")
            or request.headers.get("Authorization")
        )
        if auth_header:
            parts = auth_header.split(None, 1)
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1].strip()
                if token:
                    auth_token = token

    if auth_token:
        # Truncate so the dictionary key isn't unbounded; collisions inside
        # this prefix would only matter for adversarial inputs and the
        # bucket's worst-case behavior is "shared too aggressively"
        # (i.e. fail closed) which is acceptable for a security control.
        return f"token:{auth_token[:48]}:{policy.name}"

    client = request.client
    ip = client.host if client else "unknown"
    if policy.scope == "user":
        return f"anon:{ip}:{policy.name}"
    return f"ip:{ip}:{policy.name}"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class InMemoryRateLimitStore:
    """Single-process token-bucket store guarded by an asyncio.Lock.

    Suitable for single-instance deployments and the test client. For
    multi-instance / multi-region deployments swap with a Redis backed
    store; the public method ``consume`` is the only contract callers
    rely on.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    async def consume(
        self,
        key: str,
        capacity: int,
        refill_per_second: float,
        cost: int = 1,
    ) -> tuple[bool, float, float]:
        """Try to take ``cost`` tokens.

        Returns ``(allowed, remaining, retry_after_seconds)``. When
        ``allowed`` is ``False``, ``retry_after_seconds`` is how long the
        caller should wait before the bucket has enough tokens for the
        same cost (always ``> 0``). When allowed it is ``0.0``.
        """

        if capacity <= 0 or cost <= 0:
            # Defensive — a misconfigured policy should not crash the
            # request path; fall through as "allowed" so we don't punish
            # users for ops mistakes.
            return True, 0.0, 0.0

        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(capacity), last_refill=now)
                self._buckets[key] = bucket
            else:
                elapsed = max(0.0, now - bucket.last_refill)
                bucket.tokens = min(
                    float(capacity),
                    bucket.tokens + elapsed * refill_per_second,
                )
                bucket.last_refill = now

            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True, bucket.tokens, 0.0

            deficit = cost - bucket.tokens
            if refill_per_second > 0:
                retry_after = deficit / refill_per_second
            else:
                retry_after = 60.0
            # Always surface a positive retry hint so clients back off
            # instead of busy-looping when the bucket is on a millisecond
            # boundary of refilling.
            return False, max(bucket.tokens, 0.0), max(retry_after, 0.001)

    async def reset(self) -> None:
        """Clear every bucket (test helper)."""

        async with self._lock:
            self._buckets.clear()

    def size(self) -> int:
        return len(self._buckets)


_default_store: InMemoryRateLimitStore | None = None


def get_default_store() -> InMemoryRateLimitStore:
    """Return the process-global store, creating it lazily."""

    global _default_store
    if _default_store is None:
        _default_store = InMemoryRateLimitStore()
    return _default_store


async def reset_default_store_for_test() -> None:
    """Wipe the singleton store. Used by unit/integration tests only."""

    store = get_default_store()
    await store.reset()
