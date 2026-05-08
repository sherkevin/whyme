"""PRD10 product-data API integration tests.

These tests cover the first wired PRD10 backend slice: Capture, KB, Jobs, and
Notifications through the real FastAPI app. Auth and DB dependencies are
overridden so the tests can focus on route wiring, user isolation, and envelope
shape without relying on external Postgres/JWT setup.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import agent_os.db.sqlite_compat  # noqa: F401
from agent_os.auth import dependencies as auth_dependencies
from agent_os.auth.models import User
from agent_os.db import base as db_base
from agent_os.db.base import Base
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.server.app import app


@asynccontextmanager
async def _prd10_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    current_user = User(
        id=uuid.uuid4(),
        email="prd10@example.com",
        username="prd10-user",
        password_hash="not-used",
        is_active=True,
    )
    async with session_factory() as db:
        db.add(current_user)
        await db.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_current_user():
        return current_user

    app.dependency_overrides[db_base.get_db] = override_get_db
    app.dependency_overrides[auth_dependencies.get_current_user] = override_get_current_user

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            yield client, current_user, session_factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


def test_prd10_routes_are_wired_once() -> None:
    paths = [getattr(route, "path", "") for route in app.routes]

    assert "/api/v1/capture/text" in paths
    assert "/api/v1/kb/overview" in paths
    assert "/api/v1/jobs/{job_id}" in paths
    assert "/api/v1/notifications/unread-count" in paths
    assert "/api/v1/feed" in paths
    assert "/api/v1/cards/{card_id}" in paths
    assert paths.count("/api/v1/today") == 1


def test_capture_text_creates_job_and_notification_envelopes() -> None:
    async def scenario() -> None:
        async with _prd10_client() as (client, _user, _session_factory):
            response = await client.post(
                "/api/v1/capture/text",
                json={
                    "content": "Remember to review PRD10 route wiring.",
                    "title": "PRD10 route wiring",
                    "tags": ["prd10"],
                },
                headers={"X-Request-ID": "req_capture_test"},
            )

            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == "req_capture_test"
            body = response.json()
            assert body["success"] is True
            assert body["request_id"] == "req_capture_test"
            assert body["data"]["inbox_item"]["type"] == "text"
            assert body["data"]["inbox_item"]["processing_status"] == "completed"

            job_id = body["data"]["job"]["id"]
            job_response = await client.get(f"/api/v1/jobs/{job_id}")
            assert job_response.status_code == 200
            assert job_response.json()["data"]["job_type"] == "summarize"
            assert job_response.json()["data"]["status"] == "completed"

            count_response = await client.get("/api/v1/notifications/unread-count")
            assert count_response.status_code == 200
            assert count_response.json()["data"] == {"count": 1}

            notifications = await client.get("/api/v1/notifications")
            assert notifications.status_code == 200
            assert notifications.json()["data"]["pagination"]["total"] == 1
            assert notifications.json()["data"]["items"][0]["object_type"] == "inbox_item"

            feed = await client.get("/api/v1/feed")
            assert feed.status_code == 200
            feed_body = feed.json()
            assert feed_body["success"] is True
            assert feed_body["data"]["pagination"]["total"] == 1
            assert feed_body["data"]["items"][0]["content_type"] == "note"

    asyncio.run(scenario())


def test_capture_validation_errors_use_prd10_envelope() -> None:
    async def scenario() -> None:
        async with _prd10_client() as (client, _user, _session_factory):
            response = await client.post(
                "/api/v1/capture/text",
                json={"content": ""},
                headers={"X-Request-ID": "req_bad_capture"},
            )

            assert response.status_code == 422
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "VALIDATION_ERROR"
            assert body["request_id"] == "req_bad_capture"

    asyncio.run(scenario())


def test_job_lookup_hides_other_users_jobs() -> None:
    async def scenario() -> None:
        async with _prd10_client() as (client, _user, session_factory):
            other_user = User(
                id=uuid.uuid4(),
                email="other-prd10@example.com",
                username="other-prd10-user",
                password_hash="not-used",
                is_active=True,
            )
            async with session_factory() as db:
                db.add(other_user)
                await db.flush()
                job = Job(
                    user_id=other_user.id,
                    job_type=JobType.SUMMARIZE.value,
                    status=JobStatus.QUEUED.value,
                    input={"kind": "other-user"},
                )
                db.add(job)
                await db.commit()
                other_job_id = job.id

            response = await client.get(f"/api/v1/jobs/{other_job_id}")
            assert response.status_code == 404
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "NOT_FOUND"

    asyncio.run(scenario())


def test_kb_folder_and_file_capture_document_flow() -> None:
    async def scenario() -> None:
        async with _prd10_client() as (client, _user, _session_factory):
            folder_response = await client.post(
                "/api/v1/kb/folders",
                json={"name": "Product Design", "is_favorite": True},
            )
            assert folder_response.status_code == 200
            folder_id = folder_response.json()["data"]["id"]

            list_response = await client.get("/api/v1/kb/folders?include_counts=true")
            assert list_response.status_code == 200
            folder = list_response.json()["data"]["items"][0]
            assert folder["id"] == folder_id
            assert folder["document_count"] == 0

            upload_id = str(uuid.uuid4())
            commit_response = await client.post(
                "/api/v1/capture/file/commit",
                json={
                    "upload_id": upload_id,
                    "filename": "prd10-notes.md",
                    "mime_type": "text/markdown",
                    "size_bytes": 128,
                    "target_folder_id": folder_id,
                },
            )
            assert commit_response.status_code == 200
            document_id = commit_response.json()["data"]["document_id"]

            docs_response = await client.get(f"/api/v1/kb/documents?folder_id={folder_id}")
            assert docs_response.status_code == 200
            assert docs_response.json()["data"]["pagination"]["total"] == 1
            assert docs_response.json()["data"]["items"][0]["id"] == document_id

            detail_response = await client.get(f"/api/v1/kb/documents/{document_id}")
            assert detail_response.status_code == 200
            detail = detail_response.json()["data"]
            assert detail["folder"]["id"] == folder_id
            assert detail["source"]["name"] == "prd10-notes.md"
            assert detail["ai_suggestions"][0]["type"] == "ask_ai"

    asyncio.run(scenario())
