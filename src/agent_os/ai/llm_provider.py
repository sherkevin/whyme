"""LLM provider plumbing for the PRD10 Mydow AI router.

The router stays decoupled from any specific LLM SDK by going through this
small module. We choose between two backends:

1. **Real LLM** via ``agent_os.llm.litellm_impl.LiteLLMProvider`` when
   ``AGENTOS_AI_LLM`` is on (or when the test harness injects a fake
   provider with ``set_test_provider``).
2. **Visible failure** otherwise. Deterministic placeholder replies are
   available only when ``AGENTOS_AI_OFFLINE_PLACEHOLDER`` is explicitly
   enabled by tests/dev tools.

The router only uses three calls:

- ``is_llm_enabled()``
- ``allow_offline_placeholder()``
- ``await get_provider().complete(messages, ...)``
- ``async for chunk in get_provider().stream_complete(messages, ...)``

so swapping providers (LiteLLM today, vLLM/local tomorrow) does not touch
the router.

PRD10 §12.3 (todo-tasks.md) — same-prompt 24h cache for non-streaming
completions: the wrapper here keeps an in-memory LRU keyed by
``sha256(messages + model + temperature)`` and decorates the result with
``cache="hit" | "miss"`` so the router can attribute usage to caching.
Streaming responses are intentionally NOT cached — re-using a static
list of "tokens" defeats the purpose of streaming.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any, Optional, Protocol

from agent_os.llm.config import resolve_llm_config, resolve_model

_provider_singleton: LLMProviderLike | None = None
_test_provider: LLMProviderLike | None = None


class LLMProviderLike(Protocol):
    """Subset of ``agent_os.core.interfaces.LLMProvider`` we depend on."""

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        ...

    def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        ...


def is_llm_enabled() -> bool:
    """Honor explicit opt-in so unit tests stay offline by default."""

    if _test_provider is not None:
        return True
    flag = (os.environ.get("AGENTOS_AI_LLM") or "").strip().lower()
    return flag in {"on", "1", "true", "enabled"}


def allow_offline_placeholder() -> bool:
    """Allow deterministic assistant output only for explicit offline tests.

    Product and internal-beta runs must either call a real provider or surface
    a visible failure. This opt-in keeps legacy offline tests available without
    letting fake AI answers leak into real user flows.
    """

    raw = (os.environ.get("AGENTOS_AI_OFFLINE_PLACEHOLDER") or "").strip().lower()
    return raw in {"on", "1", "true", "enabled", "yes"}


def set_test_provider(provider: LLMProviderLike | None) -> None:
    """Override the provider for tests; pass ``None`` to clear."""

    global _test_provider, _provider_singleton, _CACHE
    _test_provider = provider
    _provider_singleton = None
    # A new test provider invalidates any cached completions captured
    # from the previous one; otherwise the cache replays a stale answer.
    _CACHE.clear()


# ---------------------------------------------------------------------------
# §12.3 — same-prompt 24h cache for ``provider.complete()`` calls
# ---------------------------------------------------------------------------


def _ai_cache_enabled() -> bool:
    """Toggle the §12.3 cache via env var (default ON when LLM is on).

    Set ``AGENTOS_AI_CACHE=off`` (or ``0`` / ``false``) to disable. The
    test fixture in ``test_prd10_ai_llm.py`` uses a fake provider, where
    caching is desirable so the multiple-call assertions can opt in to
    "second call is hit". When ``AGENTOS_AI_LLM`` is unset and there's no
    test provider, ``is_llm_enabled()`` returns False and the router surfaces
    a visible failure unless the explicit offline placeholder switch is on, so
    the cache is unused.
    """

    raw = (os.environ.get("AGENTOS_AI_CACHE") or "").strip().lower()
    if raw in {"off", "0", "false", "disabled"}:
        return False
    return True


def _ai_cache_ttl_seconds() -> int:
    raw = os.environ.get("AGENTOS_AI_CACHE_TTL_SECONDS")
    try:
        v = int(raw) if raw is not None else 24 * 3600
    except (TypeError, ValueError):
        return 24 * 3600
    return v if v > 0 else 24 * 3600


def _ai_cache_max_entries() -> int:
    raw = os.environ.get("AGENTOS_AI_CACHE_MAX_ENTRIES")
    try:
        v = int(raw) if raw is not None else 256
    except (TypeError, ValueError):
        return 256
    return v if v > 0 else 256


# OrderedDict so we can do an O(1) LRU eviction on insert.
_CACHE: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_CACHE_LOCK = asyncio.Lock()


def _cache_key(
    messages: list[dict[str, Any]],
    model: str,
    temperature: float | None,
    tools: list[dict[str, Any]] | None,
) -> str:
    """Hash the request shape so semantically-equal calls collide."""

    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
        "tools": tools or [],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if expires_at < time.time():
        _CACHE.pop(key, None)
        return None
    _CACHE.move_to_end(key)
    return value


def _cache_put(key: str, value: dict[str, Any]) -> None:
    ttl = _ai_cache_ttl_seconds()
    _CACHE[key] = (time.time() + ttl, value)
    _CACHE.move_to_end(key)
    while len(_CACHE) > _ai_cache_max_entries():
        _CACHE.popitem(last=False)


class _CachingProvider:
    """Decorator that wraps an upstream provider with the §12.3 LRU.

    Only ``.complete()`` is cached — ``.stream_complete()`` passes through
    untouched (caching a tokenized stream replay would break the SSE UX).
    """

    def __init__(self, upstream: LLMProviderLike) -> None:
        self._upstream = upstream

    @property
    def upstream(self) -> LLMProviderLike:
        return self._upstream

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not _ai_cache_enabled():
            return await self._upstream.complete(messages, tools=tools, **kwargs)

        model = str(kwargs.get("model") or resolve_model("ai"))
        temperature = kwargs.get("temperature")
        if temperature is None:
            try:
                temperature = float(
                    os.environ.get("AGENTOS_AI_TEMPERATURE", "0.3")
                )
            except (TypeError, ValueError):
                temperature = 0.3

        key = _cache_key(messages, model, float(temperature), tools)
        async with _CACHE_LOCK:
            cached = _cache_get(key)
        if cached is not None:
            replay = dict(cached)
            replay["cache"] = "hit"
            replay["cache_key"] = key
            return replay

        result = await self._upstream.complete(messages, tools=tools, **kwargs)
        if not isinstance(result, dict):  # pragma: no cover - defensive
            return result
        # Persist a defensive copy so post-mutations by the caller don't
        # poison the cache, then mark the call as a "miss" for telemetry.
        snapshot = dict(result)
        snapshot.pop("cache", None)
        snapshot.pop("cache_key", None)
        async with _CACHE_LOCK:
            _cache_put(key, snapshot)
        result_view = dict(snapshot)
        result_view["cache"] = "miss"
        result_view["cache_key"] = key
        return result_view

    def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        # Passthrough — see module docstring.
        return self._upstream.stream_complete(messages, tools=tools, **kwargs)


def reset_cache_for_test() -> None:
    """Public helper so tests can clear the §12.3 cache between cases."""

    _CACHE.clear()


def cache_size() -> int:
    return len(_CACHE)


def get_provider() -> LLMProviderLike:
    """Return the active LLM provider, lazily constructing it once.

    The returned object is always a ``_CachingProvider`` wrapper so the
    §12.3 cache covers both the real LiteLLM backend and any test provider
    (the wrapper degrades to a passthrough when ``AGENTOS_AI_CACHE=off``).
    """

    global _provider_singleton

    if _test_provider is not None:
        # Fresh wrapper each call so test_provider swap doesn't leak prior
        # cached results. ``set_test_provider`` already cleared _CACHE.
        return _CachingProvider(_test_provider)

    if _provider_singleton is None:
        # Local import keeps the module light when the LLM is disabled.
        from agent_os.llm.litellm_impl import LiteLLMProvider

        cfg = resolve_llm_config(purpose="ai")
        upstream = LiteLLMProvider(
            model=cfg.model,
            api_base=cfg.api_base,
            api_key=cfg.api_key,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
        _provider_singleton = _CachingProvider(upstream)
    return _provider_singleton


def reset_provider_for_test() -> None:
    """Helper for tests that flip env vars at runtime."""

    global _provider_singleton
    _provider_singleton = None
    _CACHE.clear()


__all__ = [
    "LLMProviderLike",
    "allow_offline_placeholder",
    "is_llm_enabled",
    "set_test_provider",
    "get_provider",
    "reset_provider_for_test",
    "reset_cache_for_test",
    "cache_size",
]
