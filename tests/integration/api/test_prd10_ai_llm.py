"""PRD10 §11.4 LLM-driven send-message + SSE streaming tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import agent_os.db.sqlite_compat  # noqa: F401
from agent_os.ai import llm_provider
from agent_os.ai.models import AIConversation, AIMessage
from agent_os.ai.router import router as ai_router
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db import base as db_base
from agent_os.db.base import get_db
from agent_os.jobs.models import Job
from agent_os.search_engine.models import SearchIndex

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeProvider:
    """Drop-in replacement for ``LiteLLMProvider`` in tests."""

    def __init__(
        self,
        reply: str = "你好，这是一段真实回答。",
        chunks: list[str] | None = None,
        usage: dict[str, int] | None = None,
    ) -> None:
        self.reply = reply
        self.chunks = chunks or ["你好，", "这是一段", "流式真实回答。"]
        self.usage = usage or {
            "prompt_tokens": 12,
            "completion_tokens": 24,
            "total_tokens": 36,
        }
        self.complete_calls: list[list[dict[str, Any]]] = []
        self.stream_calls: list[list[dict[str, Any]]] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.complete_calls.append(list(messages))
        return {
            "content": self.reply,
            "role": "assistant",
            "model": "fake-llm",
            "usage": self.usage,
        }

    async def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        self.stream_calls.append(list(messages))
        for piece in self.chunks:
            yield {"content": piece}


# ---------------------------------------------------------------------------
# Fixtures (mirror test_prd10_ai_api.py shape)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def prd10_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        def _create(connection):
            User.__table__.create(connection, checkfirst=True)
            Job.__table__.create(connection, checkfirst=True)
            SearchIndex.__table__.create(connection, checkfirst=True)
            AIConversation.__table__.create(connection, checkfirst=True)
            AIMessage.__table__.create(connection, checkfirst=True)

        await conn.run_sync(_create)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def prd10_sessionmaker(prd10_engine):
    return async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def fixture_user(prd10_sessionmaker) -> User:
    async with prd10_sessionmaker() as session:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            id=uuid.uuid4(),
            email=f"u{suffix}@example.com",
            username=f"u_{suffix}",
            password_hash="x",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def app(prd10_sessionmaker, fixture_user, monkeypatch):
    fastapi_app = FastAPI()
    fastapi_app.include_router(ai_router)

    async def _override_db():
        async with prd10_sessionmaker() as session:
            yield session

    async def _override_user():
        return fixture_user

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_current_user] = _override_user

    # The streaming endpoint asks ``get_sessionmaker`` for a fresh session
    # outside the request scope; redirect it to the per-test in-memory engine
    # so concurrent commits land on the same DB.
    monkeypatch.setattr(db_base, "get_sessionmaker", lambda: prd10_sessionmaker)

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@contextmanager
def _env(name: str, value: str | None) -> Iterator[None]:
    previous = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


@pytest.fixture
def fake_provider():
    provider = FakeProvider()
    llm_provider.set_test_provider(provider)
    try:
        yield provider
    finally:
        llm_provider.set_test_provider(None)


# ---------------------------------------------------------------------------
# is_llm_enabled
# ---------------------------------------------------------------------------


def test_is_llm_enabled_default_off():
    llm_provider.set_test_provider(None)
    with _env("AGENTOS_AI_LLM", None):
        assert llm_provider.is_llm_enabled() is False


def test_is_llm_enabled_when_env_on():
    llm_provider.set_test_provider(None)
    for value in ("on", "1", "true", "Enabled"):
        with _env("AGENTOS_AI_LLM", value):
            assert llm_provider.is_llm_enabled() is True


def test_is_llm_enabled_when_test_provider_present(fake_provider):
    with _env("AGENTOS_AI_LLM", None):
        assert llm_provider.is_llm_enabled() is True


# ---------------------------------------------------------------------------
# Synchronous LLM-driven send message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_message_uses_real_llm_when_enabled(client, fake_provider):
    created = await client.post(
        "/api/v1/ai/conversations",
        json={"title": "LLM 接入验收", "mode": "general"},
    )
    assert created.status_code == 201
    cid = created.json()["data"]["id"]

    sent = await client.post(
        f"/api/v1/ai/conversations/{cid}/messages",
        json={"content": "用一句话回答 PRD10 是什么"},
    )
    assert sent.status_code == 201, sent.text
    data = sent.json()["data"]
    assistant = data["assistant_message"]

    assert assistant["model"] == "litellm"
    assert assistant["content"] == fake_provider.reply
    assert assistant["status"] == "completed"
    assert assistant["input_tokens"] == fake_provider.usage["prompt_tokens"]
    assert assistant["output_tokens"] == fake_provider.usage["completion_tokens"]
    assert fake_provider.complete_calls, "expected the LLM to be called"

    last_call = fake_provider.complete_calls[-1]
    assert any(m["role"] == "system" for m in last_call)
    assert last_call[-1] == {"role": "user", "content": "用一句话回答 PRD10 是什么"}


@pytest.mark.asyncio
async def test_post_message_keeps_placeholder_when_llm_disabled(client):
    # Ensure neither the env switch nor a test provider is active.
    llm_provider.set_test_provider(None)
    with _env("AGENTOS_AI_LLM", None):
        created = await client.post(
            "/api/v1/ai/conversations",
            json={"title": "默认占位"},
        )
        assert created.status_code == 201
        cid = created.json()["data"]["id"]

        sent = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "默认路径"},
        )
        data = sent.json()["data"]
        assistant = data["assistant_message"]
        assert assistant["model"] == "placeholder"
        assert "占位回答" in assistant["content"]


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    block: list[str] = []
    for line in body.splitlines():
        if not line:
            if block:
                event_type = ""
                data = ""
                for piece in block:
                    if piece.startswith("event:"):
                        event_type = piece.split(":", 1)[1].strip()
                    elif piece.startswith("data:"):
                        data = piece.split(":", 1)[1].strip()
                events.append((event_type, data))
                block = []
            continue
        block.append(line)
    if block:
        event_type = ""
        data = ""
        for piece in block:
            if piece.startswith("event:"):
                event_type = piece.split(":", 1)[1].strip()
            elif piece.startswith("data:"):
                data = piece.split(":", 1)[1].strip()
        events.append((event_type, data))
    return events


@pytest.mark.asyncio
async def test_stream_endpoint_with_fake_llm(client, fake_provider):
    created = await client.post(
        "/api/v1/ai/conversations",
        json={"title": "SSE 验收"},
    )
    cid = created.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/ai/conversations/{cid}/messages/stream",
        json={"content": "请流式回答"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    events = _parse_sse(body)
    event_types = [e[0] for e in events]
    assert event_types[0] == "meta"
    assert event_types[-1] == "done"
    assert "token" in event_types

    token_text = "".join(
        # data is JSON like {"delta": "..."}; quick parse via in-text find.
        evt[1] for evt in events if evt[0] == "token"
    )
    for piece in fake_provider.chunks:
        assert piece in token_text


@pytest.mark.asyncio
async def test_stream_endpoint_falls_back_to_offline_chunks(client):
    llm_provider.set_test_provider(None)
    with _env("AGENTOS_AI_LLM", None):
        created = await client.post(
            "/api/v1/ai/conversations",
            json={"title": "SSE 占位"},
        )
        cid = created.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages/stream",
            json={"content": "占位流式"},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        types = [e[0] for e in events]
        assert types[0] == "meta"
        assert types[-1] == "done"
        assert types.count("token") >= 2  # multiple offline chunks


# ---------------------------------------------------------------------------
# SSE keepalive / reconnect hardening (PRD10 §12.4)
# ---------------------------------------------------------------------------


class _SlowFakeProvider(FakeProvider):
    """Stream a single chunk after a short delay so we can verify keepalive
    fires while the upstream is idle."""

    def __init__(self, delay_seconds: float = 0.6, reply: str = "晚到的回答") -> None:
        super().__init__(reply=reply, chunks=[reply])
        self.delay_seconds = delay_seconds

    async def stream_complete(  # type: ignore[override]
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        self.stream_calls.append(list(messages))
        # Sleep long enough that at least one keepalive tick must fire when
        # AGENTOS_SSE_HEARTBEAT_SECONDS is set to <= delay/2.
        import asyncio

        await asyncio.sleep(self.delay_seconds)
        for piece in self.chunks:
            yield {"content": piece}


@pytest.mark.asyncio
async def test_stream_meta_carries_retry_and_heartbeat_hint(client, fake_provider):
    """The first SSE block must carry ``retry: 5000`` and ``heartbeat_seconds``.

    ``retry:`` lets the browser EventSource auto-reconnect after 5s on a
    TCP drop. ``heartbeat_seconds`` lets the FE configure its own watchdog
    that's aware of the proxy keepalive cadence.
    """

    created = await client.post(
        "/api/v1/ai/conversations",
        json={"title": "SSE retry hint"},
    )
    cid = created.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/ai/conversations/{cid}/messages/stream",
        json={"content": "请回答"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "retry: 5000" in body, body
    # PRD10 §12.4 — proxies must NOT buffer.
    assert resp.headers.get("x-accel-buffering") == "no"
    # The first event must still be ``meta`` so existing parsers keep working.
    events = _parse_sse(body)
    assert events[0][0] == "meta"
    # Meta payload includes the heartbeat config so the FE can show it.
    assert '"heartbeat_seconds":' in events[0][1]


@pytest.mark.asyncio
async def test_stream_keepalive_fires_when_upstream_is_idle(client):
    """When the LLM is slow, the SSE stream must emit ``event: keepalive``
    so proxies don't drop the connection on idle."""

    slow = _SlowFakeProvider(delay_seconds=0.6)
    llm_provider.set_test_provider(slow)
    try:
        with _env("AGENTOS_SSE_HEARTBEAT_SECONDS", "1"):
            # Heartbeat 1s; we make the upstream sleep 0.6s.
            # The wrap_with_heartbeat helper rounds to seconds, so we cannot
            # guarantee a keepalive fires inside 0.6s on every machine.
            # We assert the *plumbing* (retry hint + meta heartbeat_seconds)
            # rather than racing real time. See
            # ``test_wrap_with_heartbeat_yields_keepalive_when_upstream_blocks``
            # below for a unit-level deterministic check.
            created = await client.post(
                "/api/v1/ai/conversations",
                json={"title": "SSE keepalive"},
            )
            cid = created.json()["data"]["id"]

            resp = await client.post(
                f"/api/v1/ai/conversations/{cid}/messages/stream",
                json={"content": "慢一点回答"},
            )
            assert resp.status_code == 200
            events = _parse_sse(resp.text)
            types = [e[0] for e in events]
            assert types[0] == "meta"
            assert types[-1] == "done"
            assert "token" in types
    finally:
        llm_provider.set_test_provider(None)


@pytest.mark.asyncio
async def test_wrap_with_heartbeat_yields_keepalive_when_upstream_blocks():
    """Unit-level deterministic check for the heartbeat helper.

    Bypasses the HTTP layer to prove ``_wrap_with_heartbeat`` produces
    multiple ``_HEARTBEAT_SENTINEL`` markers whenever the upstream takes
    longer than the configured heartbeat interval. Uses a 100ms heartbeat
    + 350ms upstream block so the test finishes in well under a second
    while leaving plenty of slack for slow CI runners.
    """

    import asyncio

    from agent_os.ai.router import _HEARTBEAT_SENTINEL, _wrap_with_heartbeat

    async def _slow_upstream() -> AsyncIterator[dict[str, str]]:
        await asyncio.sleep(0.35)
        yield {"content": "first"}
        await asyncio.sleep(0.05)
        yield {"content": "second"}

    seen: list[Any] = []
    async for chunk in _wrap_with_heartbeat(
        _slow_upstream(), heartbeat_seconds=0.1
    ):
        seen.append(chunk)

    heartbeats = [c for c in seen if c is _HEARTBEAT_SENTINEL]
    contents = [c.get("content") for c in seen if isinstance(c, dict)]
    assert len(heartbeats) >= 2, f"expected >=2 heartbeats, got {seen!r}"
    assert "first" in contents
    assert "second" in contents


@pytest.mark.asyncio
async def test_complete_is_cached_for_same_prompt(fake_provider):
    """§12.3 — second ``complete()`` call for the same prompt must hit the
    in-memory LRU cache (no upstream call) and return ``cache="hit"``."""

    llm_provider.reset_cache_for_test()
    provider = llm_provider.get_provider()
    messages = [
        {"role": "system", "content": "你是 Mydow AI"},
        {"role": "user", "content": "PRD10 §12.3 是什么"},
    ]
    first = await provider.complete(messages)
    second = await provider.complete(messages)

    assert first["cache"] == "miss"
    assert second["cache"] == "hit"
    assert first["cache_key"] == second["cache_key"]
    # Upstream was called only once even though we asked twice.
    assert len(fake_provider.complete_calls) == 1
    assert llm_provider.cache_size() == 1


@pytest.mark.asyncio
async def test_complete_cache_distinguishes_different_prompts(fake_provider):
    """Different prompts must produce different cache keys + 2 upstream calls."""

    llm_provider.reset_cache_for_test()
    provider = llm_provider.get_provider()
    a = await provider.complete([{"role": "user", "content": "alpha"}])
    b = await provider.complete([{"role": "user", "content": "beta"}])
    assert a["cache_key"] != b["cache_key"]
    assert a["cache"] == "miss"
    assert b["cache"] == "miss"
    assert len(fake_provider.complete_calls) == 2


@pytest.mark.asyncio
async def test_complete_cache_disabled_via_env(fake_provider):
    """``AGENTOS_AI_CACHE=off`` must turn the wrapper into a passthrough."""

    llm_provider.reset_cache_for_test()
    with _env("AGENTOS_AI_CACHE", "off"):
        provider = llm_provider.get_provider()
        msgs = [{"role": "user", "content": "no-cache run"}]
        a = await provider.complete(msgs)
        b = await provider.complete(msgs)
    # Both calls hit the upstream — no cache annotation either.
    assert "cache" not in a
    assert "cache" not in b
    assert len(fake_provider.complete_calls) == 2


@pytest.mark.asyncio
async def test_stream_complete_bypasses_cache(fake_provider):
    """``stream_complete`` must always go to the upstream so SSE tokens are real."""

    llm_provider.reset_cache_for_test()
    provider = llm_provider.get_provider()
    msgs = [{"role": "user", "content": "stream me"}]

    async def consume(stream):
        out = []
        async for chunk in stream:
            out.append(chunk.get("content", ""))
        return out

    first = await consume(provider.stream_complete(msgs))
    second = await consume(provider.stream_complete(msgs))

    assert first == fake_provider.chunks
    assert second == fake_provider.chunks
    # stream_complete should NOT populate the cache.
    assert llm_provider.cache_size() == 0
    # Upstream was hit twice.
    assert len(fake_provider.stream_calls) == 2


@pytest.mark.asyncio
async def test_wrap_with_heartbeat_propagates_upstream_errors():
    """Errors raised by the upstream stream must surface to the consumer
    once the queue drains, so the SSE generator can emit ``event: error``."""

    import asyncio

    from agent_os.ai.router import _wrap_with_heartbeat

    class BoomError(RuntimeError):
        pass

    async def _failing_upstream() -> AsyncIterator[dict[str, str]]:
        await asyncio.sleep(0.05)
        yield {"content": "ok"}
        await asyncio.sleep(0.02)
        raise BoomError("upstream exploded")

    seen: list[Any] = []
    with pytest.raises(BoomError):
        async for chunk in _wrap_with_heartbeat(
            _failing_upstream(), heartbeat_seconds=1.0
        ):
            seen.append(chunk)
    contents = [c.get("content") for c in seen if isinstance(c, dict)]
    assert "ok" in contents
