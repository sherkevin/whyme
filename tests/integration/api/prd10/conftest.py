"""Lightweight test harness for PRD10 product-data routers.

Each test gets a fresh database (in-memory SQLite by default; real Postgres
when ``TEST_DATABASE_URL`` is set, e.g. when running against the Docker PG
container described in the README) and a FastAPI app that only mounts the
PRD10 routers under test. ``get_current_user`` is overridden with a
deterministic fake user so we don't rely on JWT plumbing.

To run against Postgres in Docker:

    docker run -d --name whyme-prd10-pg \
        -e POSTGRES_USER=agentos -e POSTGRES_PASSWORD=agentos \
        -e POSTGRES_DB=agentos_db -p 5433:5432 postgres:16-alpine
    $env:TEST_DATABASE_URL =
        "postgresql+asyncpg://agentos:agentos@localhost:5433/agentos_db"
    pytest tests/integration/api/prd10/ -q
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import UUID as SqlAlchemyUUID
from sqlalchemy import text
from sqlalchemy.dialects.sqlite import base as sqlite_base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


# ``auth.models.User`` uses ``sqlalchemy.UUID`` (PG-flavored), which has no
# default SQLite compilation in SQLAlchemy 2.0.23. We register a one-line
# fallback so test schemas materialize as ``CHAR(32)`` on SQLite. Production
# Postgres still uses the native UUID type because the dialect-specific
# compiler is unaffected.
@compiles(SqlAlchemyUUID, "sqlite")
def _compile_uuid_for_sqlite(_type, _compiler, **_kw):  # noqa: D401 - tiny shim
    return "CHAR(32)"


_ = sqlite_base  # ensure dialect import order is stable


_TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import APIKey, AuditLog, Role, Session, User, UserRole
from agent_os.capture.router import router as capture_router
from agent_os.common import ApiErrorCode, error_json_response, http_exception_to_envelope
from agent_os.common.middleware import RequestIdMiddleware
from agent_os.db.base import get_db
from agent_os.inbox.prd10_models import Prd10InboxItem
from agent_os.items.models import Area, Item, Project, Workspace
from agent_os.jobs.models import Job
from agent_os.jobs.router import router as jobs_router
from agent_os.kb.models import Chunk, Document, Folder
from agent_os.kb.router import router as kb_router
from agent_os.knowledge.models import Card
from agent_os.notifications.models import Notification
from agent_os.notifications.router import router as notifications_router
from agent_os.search_engine.models import SearchIndex
from agent_os.sources.models import Source
from agent_os.tasks.models import PRD10Task

# ---------------------------------------------------------------------------
# Database engine fixture (function scope keeps tests fully isolated).
# ---------------------------------------------------------------------------


_TABLE_DROP_ORDER = (
    "search_indices",
    "cards",
    "prd10_inbox_items",
    "prd10_notifications",
    "prd10_jobs",
    "prd10_tasks",
    "kb_chunks",
    "kb_documents",
    "kb_folders",
    "prd10_sources",
    "items",
    "projects",
    "areas",
    "workspaces",
    "audit_logs",
    "user_roles",
    "roles",
    "sessions",
    "api_keys",
    "users",
)

# We deliberately keep this list to PRD10's minimal closure plus a stripped-down
# Workspace/Item pair, because legacy PRD4 satellite tables (AgentProcessEvent,
# TaskExtension, DecisionPoint, LedgerEvent, GraphEdge) carry historical type
# mismatches (e.g. ``agent_process_events.item_id`` is VARCHAR while
# ``items.id`` is UUID) that real Postgres rejects when materializing FKs.
_TABLE_CREATE_ORDER = (
    User.__table__,
    APIKey.__table__,
    Session.__table__,
    Role.__table__,
    UserRole.__table__,
    AuditLog.__table__,
    Workspace.__table__,
    Area.__table__,
    Project.__table__,
    Item.__table__,
    Source.__table__,
    Folder.__table__,
    Document.__table__,
    Chunk.__table__,
    Job.__table__,
    PRD10Task.__table__,
    Notification.__table__,
    Prd10InboxItem.__table__,
    Card.__table__,
    # PRD10 §13 + §19.1 step 8: capture pipeline writes Card/Document into
    # the unified SearchIndex so /api/v1/search hits them right away.
    SearchIndex.__table__,
)


def _prd10_should_use_drop_cascade() -> bool:
    url = (_TEST_DATABASE_URL or "").strip().lower()
    if not url:
        return False
    return "postgresql" in url or "+asyncpg" in url or "+psycopg" in url


@pytest_asyncio.fixture
async def prd10_engine():
    if _TEST_DATABASE_URL:
        engine = create_async_engine(_TEST_DATABASE_URL, future=True)
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )

    cascade = " CASCADE" if _prd10_should_use_drop_cascade() else ""

    async with engine.begin() as conn:
        if _TEST_DATABASE_URL:
            for name in _TABLE_DROP_ORDER:
                await conn.execute(text(f"DROP TABLE IF EXISTS {name}{cascade}"))
        for table in _TABLE_CREATE_ORDER:
            await conn.run_sync(table.create, checkfirst=True)

    yield engine

    if _TEST_DATABASE_URL:
        async with engine.begin() as conn:
            for name in _TABLE_DROP_ORDER:
                await conn.execute(text(f"DROP TABLE IF EXISTS {name}{cascade}"))

    await engine.dispose()


@pytest_asyncio.fixture
async def prd10_sessionmaker(prd10_engine):
    return async_sessionmaker(prd10_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def prd10_user(prd10_sessionmaker):
    async with prd10_sessionmaker() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"u{uuid.uuid4().hex[:8]}@example.com",
            username=f"u{uuid.uuid4().hex[:8]}",
            password_hash="x",
            is_active=True,
            settings={},
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def prd10_other_user(prd10_sessionmaker):
    async with prd10_sessionmaker() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"u{uuid.uuid4().hex[:8]}@example.com",
            username=f"u{uuid.uuid4().hex[:8]}",
            password_hash="x",
            is_active=True,
            settings={},
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ---------------------------------------------------------------------------
# FastAPI app + HTTP client.
# ---------------------------------------------------------------------------


def _build_app(
    sessionmaker,
    current_user,
    *,
    with_request_id_middleware: bool = True,
) -> FastAPI:
    from agent_os.feed.router import router as feed_router
    from agent_os.tasks.prd10_router import router as tasks_prd10_router
    from agent_os.today.prd10_router import router as today_prd10_router
    from agent_os.uploads.router import router as uploads_router

    app = FastAPI()
    if with_request_id_middleware:
        app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException):
        if request.url.path.startswith("/api/v1/"):
            return http_exception_to_envelope(exc, request=request)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        if request.url.path.startswith("/api/v1/"):
            return error_json_response(
                ApiErrorCode.VALIDATION_ERROR,
                "Validation error",
                details={"errors": jsonable_encoder(exc.errors())},
                status_code=422,
                request=request,
            )
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    app.include_router(today_prd10_router)
    app.include_router(tasks_prd10_router)
    app.include_router(capture_router)
    app.include_router(uploads_router)
    app.include_router(feed_router)
    app.include_router(jobs_router)
    app.include_router(notifications_router)
    app.include_router(kb_router)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmaker() as session:
            try:
                yield session
            finally:
                await session.close()

    async def override_current_user():
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    return app


@pytest_asyncio.fixture
async def prd10_client(prd10_sessionmaker, prd10_user) -> AsyncGenerator[AsyncClient, None]:
    app = _build_app(prd10_sessionmaker, prd10_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def prd10_other_client(
    prd10_sessionmaker, prd10_other_user
) -> AsyncGenerator[AsyncClient, None]:
    app = _build_app(prd10_sessionmaker, prd10_other_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def prd10_app(prd10_sessionmaker, prd10_user) -> FastAPI:
    """SSE / threaded harness — no ``RequestIdMiddleware`` (see module doc)."""

    return _build_app(
        prd10_sessionmaker,
        prd10_user,
        with_request_id_middleware=False,
    )


@pytest_asyncio.fixture
async def prd10_other_app(prd10_sessionmaker, prd10_other_user) -> FastAPI:
    """Second-user app for SSE isolation tests."""

    return _build_app(
        prd10_sessionmaker,
        prd10_other_user,
        with_request_id_middleware=False,
    )


# ---------------------------------------------------------------------------
# Misc.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _disable_llm_in_prd10_tests(monkeypatch):
    """PRD10 unit tests stay offline by default.

    `.env.local` ships ``AGENTOS_AI_LLM=on`` so a developer can run the
    real DeepSeek provider during e2e/manual smoke. Inside the tight
    PRD10 test loop we want deterministic heuristic enrichment so
    assertions like ``titles == ["想法 A", "想法 B"]`` keep passing.

    Tests that explicitly need a fake or real provider opt in by
    overriding ``AGENTOS_AI_LLM`` or calling
    ``llm_provider.set_test_provider(...)`` themselves.
    """

    monkeypatch.delenv("AGENTOS_AI_LLM", raising=False)

    from agent_os.ai import llm_provider as _llm_provider

    _llm_provider.set_test_provider(None)
    _llm_provider.reset_provider_for_test()
    yield
    _llm_provider.set_test_provider(None)
    _llm_provider.reset_provider_for_test()
