"""Unit tests for ``agent_os.common.rate_limit``.

Covers the building blocks the ``RateLimitMiddleware`` composes:

* :class:`InMemoryRateLimitStore` — refill, deplete, retry-after math.
* :func:`select_policy` — first-match by path prefix and method.
* :func:`derive_key` — IP / token / user_or_ip scope semantics.
* :func:`is_rate_limit_enabled` — env-var truthy parsing.
* Default policy table — sanity checks (no overlap surprises, sane numbers).
"""

from __future__ import annotations

import asyncio

import pytest

from agent_os.common.rate_limit import (
    DEFAULT_POLICIES,
    InMemoryRateLimitStore,
    RateLimitPolicy,
    derive_key,
    is_rate_limit_enabled,
    select_policy,
)

# ---------------------------------------------------------------------------
# is_rate_limit_enabled
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("on", True),
        ("ON", True),
        ("1", True),
        ("true", True),
        ("YES", True),
        ("enabled", True),
        ("off", False),
        ("0", False),
        ("false", False),
        ("", False),
        ("placeholder", False),
    ],
)
def test_is_rate_limit_enabled_parses_truthy_values(monkeypatch, value, expected):
    monkeypatch.setenv("AGENTOS_RATE_LIMIT", value)
    assert is_rate_limit_enabled() is expected


def test_is_rate_limit_enabled_defaults_off(monkeypatch):
    monkeypatch.delenv("AGENTOS_RATE_LIMIT", raising=False)
    assert is_rate_limit_enabled() is False


def test_is_rate_limit_enabled_supports_alternate_env_name(monkeypatch):
    monkeypatch.setenv("CUSTOM_RATE", "on")
    assert is_rate_limit_enabled("CUSTOM_RATE") is True


# ---------------------------------------------------------------------------
# RateLimitPolicy.matches
# ---------------------------------------------------------------------------


def test_policy_matches_path_prefix():
    policy = RateLimitPolicy(
        name="t",
        path_prefixes=("/api/v1/foo",),
        methods=("POST",),
        capacity=5,
        refill_per_second=1.0,
    )
    assert policy.matches("/api/v1/foo", "POST")
    assert policy.matches("/api/v1/foo/bar", "POST")
    assert not policy.matches("/api/v1/bar", "POST")


def test_policy_matches_methods_case_insensitive():
    policy = RateLimitPolicy(
        name="t",
        path_prefixes=("/api/",),
        methods=("POST", "DELETE"),
        capacity=5,
        refill_per_second=1.0,
    )
    assert policy.matches("/api/x", "post")
    assert policy.matches("/api/x", "delete")
    assert not policy.matches("/api/x", "GET")


def test_policy_matches_all_methods_when_unspecified():
    policy = RateLimitPolicy(
        name="t",
        path_prefixes=("/api/",),
        methods=(),
        capacity=5,
        refill_per_second=1.0,
    )
    assert policy.matches("/api/x", "GET")
    assert policy.matches("/api/x", "POST")
    assert policy.matches("/api/x", "DELETE")


# ---------------------------------------------------------------------------
# select_policy
# ---------------------------------------------------------------------------


def test_select_policy_returns_first_match():
    policies = (
        RateLimitPolicy(
            name="specific",
            path_prefixes=("/api/v1/auth/login",),
            methods=("POST",),
            capacity=5,
            refill_per_second=1.0,
        ),
        RateLimitPolicy(
            name="catchall",
            path_prefixes=("/api/v1/",),
            methods=(),
            capacity=100,
            refill_per_second=10.0,
        ),
    )
    p = select_policy("/api/v1/auth/login", "POST", policies=policies)
    assert p is not None and p.name == "specific"

    p = select_policy("/api/v1/feed", "GET", policies=policies)
    assert p is not None and p.name == "catchall"

    p = select_policy("/legacy/foo", "GET", policies=policies)
    assert p is None


def test_default_policies_route_real_paths_correctly():
    cases = [
        ("/api/v1/auth/login", "POST", "auth_login"),
        ("/api/v1/auth/register", "POST", "auth_register"),
        ("/api/v1/auth/send-code", "POST", "auth_send_code"),
        ("/api/v1/ai/conversations/abc/messages", "POST", "ai_messages"),
        ("/api/v1/search", "GET", "search"),
        ("/api/v1/search/suggestions", "GET", "search"),
        ("/api/v1/capture/text", "POST", "capture"),
        ("/api/v1/uploads/local/abc", "PUT", "capture"),
        ("/api/v1/feed", "GET", "global"),
        ("/api/v1/kb/folders", "GET", "global"),
    ]
    for path, method, expected_name in cases:
        policy = select_policy(path, method)
        assert policy is not None, f"no policy matched {method} {path}"
        assert policy.name == expected_name, (
            f"{method} {path} -> {policy.name} (want {expected_name})"
        )


# ---------------------------------------------------------------------------
# derive_key
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, host: str):
        self.host = host


class _FakeRequest:
    def __init__(self, *, host: str = "127.0.0.1", auth: str | None = None):
        self.client = _FakeClient(host) if host else None
        self.headers = {"authorization": auth} if auth else {}


def test_derive_key_ip_scope_uses_client_host():
    policy = RateLimitPolicy(
        name="x",
        path_prefixes=("/",),
        methods=(),
        capacity=1,
        refill_per_second=1.0,
        scope="ip",
    )
    req = _FakeRequest(host="10.0.0.1")
    assert derive_key(req, policy) == "ip:10.0.0.1:x"


def test_derive_key_global_scope_is_singleton():
    policy = RateLimitPolicy(
        name="g",
        path_prefixes=("/",),
        methods=(),
        capacity=1,
        refill_per_second=1.0,
        scope="global",
    )
    req_a = _FakeRequest(host="10.0.0.1")
    req_b = _FakeRequest(host="10.0.0.2", auth="Bearer xxx")
    assert derive_key(req_a, policy) == derive_key(req_b, policy) == "global:g"


def test_derive_key_user_or_ip_prefers_token():
    policy = RateLimitPolicy(
        name="ai",
        path_prefixes=("/",),
        methods=(),
        capacity=1,
        refill_per_second=1.0,
        scope="user_or_ip",
    )
    req = _FakeRequest(host="10.0.0.1", auth="Bearer abcdef123")
    key = derive_key(req, policy)
    assert key.startswith("token:abcdef123")
    assert key.endswith(":ai")


def test_derive_key_user_or_ip_falls_back_to_ip():
    policy = RateLimitPolicy(
        name="ai",
        path_prefixes=("/",),
        methods=(),
        capacity=1,
        refill_per_second=1.0,
        scope="user_or_ip",
    )
    req = _FakeRequest(host="10.0.0.1")
    assert derive_key(req, policy) == "ip:10.0.0.1:ai"


def test_derive_key_ignores_non_bearer_auth():
    policy = RateLimitPolicy(
        name="x",
        path_prefixes=("/",),
        methods=(),
        capacity=1,
        refill_per_second=1.0,
        scope="user_or_ip",
    )
    req = _FakeRequest(host="10.0.0.1", auth="Basic xxx")
    assert derive_key(req, policy) == "ip:10.0.0.1:x"


def test_derive_key_handles_missing_client():
    policy = RateLimitPolicy(
        name="x",
        path_prefixes=("/",),
        methods=(),
        capacity=1,
        refill_per_second=1.0,
        scope="ip",
    )
    req = _FakeRequest(host="")
    assert derive_key(req, policy) == "ip:unknown:x"


# ---------------------------------------------------------------------------
# InMemoryRateLimitStore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_allows_within_capacity():
    store = InMemoryRateLimitStore()
    for _ in range(5):
        allowed, remaining, retry = await store.consume(
            "k", capacity=5, refill_per_second=10.0
        )
        assert allowed is True
        assert retry == 0.0
        assert remaining >= 0


@pytest.mark.asyncio
async def test_store_rejects_when_bucket_empty():
    store = InMemoryRateLimitStore()
    for _ in range(3):
        allowed, _, _ = await store.consume(
            "k", capacity=3, refill_per_second=0.1
        )
        assert allowed is True

    allowed, remaining, retry = await store.consume(
        "k", capacity=3, refill_per_second=0.1
    )
    assert allowed is False
    assert retry > 0
    assert remaining < 1


@pytest.mark.asyncio
async def test_store_refills_over_time():
    store = InMemoryRateLimitStore()
    # 10 tokens / second: each ~100ms refills one.
    for _ in range(2):
        allowed, _, _ = await store.consume(
            "k", capacity=2, refill_per_second=10.0
        )
        assert allowed is True

    allowed, _, _ = await store.consume(
        "k", capacity=2, refill_per_second=10.0
    )
    assert allowed is False

    await asyncio.sleep(0.15)

    allowed, _, _ = await store.consume(
        "k", capacity=2, refill_per_second=10.0
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_store_separate_keys_are_independent():
    store = InMemoryRateLimitStore()
    for _ in range(2):
        a, _, _ = await store.consume(
            "alice", capacity=2, refill_per_second=0.1
        )
        b, _, _ = await store.consume(
            "bob", capacity=2, refill_per_second=0.1
        )
        assert a is True and b is True

    alice_blocked, _, _ = await store.consume(
        "alice", capacity=2, refill_per_second=0.1
    )
    bob_blocked, _, _ = await store.consume(
        "bob", capacity=2, refill_per_second=0.1
    )
    assert alice_blocked is False and bob_blocked is False


@pytest.mark.asyncio
async def test_store_retry_after_is_proportional_to_deficit():
    store = InMemoryRateLimitStore()
    # capacity=1, refill=1/s — drain then ask for 1 → retry ~1s.
    await store.consume("k", capacity=1, refill_per_second=1.0)
    allowed, _, retry = await store.consume(
        "k", capacity=1, refill_per_second=1.0
    )
    assert allowed is False
    assert 0.5 < retry <= 1.0


@pytest.mark.asyncio
async def test_store_zero_capacity_fails_open():
    """Misconfigured zero capacity must not lock everyone out."""

    store = InMemoryRateLimitStore()
    allowed, _, _ = await store.consume(
        "k", capacity=0, refill_per_second=1.0
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_store_reset_clears_buckets():
    store = InMemoryRateLimitStore()
    for _ in range(3):
        await store.consume("k", capacity=3, refill_per_second=0.001)
    assert store.size() == 1
    await store.reset()
    assert store.size() == 0


# ---------------------------------------------------------------------------
# Default policy sanity
# ---------------------------------------------------------------------------


def test_default_policies_are_in_specific_first_order():
    """Policies that are PRD10 §29 critical must precede the catch-all."""

    names = [p.name for p in DEFAULT_POLICIES]
    assert names.index("auth_login") < names.index("global")
    assert names.index("auth_register") < names.index("global")
    assert names.index("ai_messages") < names.index("global")
    assert names.index("search") < names.index("global")
    assert names.index("capture") < names.index("global")


def test_default_policies_use_known_scopes():
    """Defensive — only known scopes are accepted by ``derive_key``."""

    valid = {"ip", "user", "user_or_ip", "global"}
    for p in DEFAULT_POLICIES:
        assert p.scope in valid, f"policy {p.name} scope {p.scope!r} unknown"
