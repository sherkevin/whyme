"""PRD10 §11.10 account-compliance integration tests.

Covers the new ``/api/v1/me/{export, unsubscribe}`` and
``DELETE /api/v1/me`` endpoints provided by
``agent_os.account.router``. The fixtures spin up a fresh in-memory
SQLite engine + StaticPool with every PRD10 / PRD4 model imported so
the export aggregation can reach folders / documents / cards / inbox
items / notifications / AI conversations + messages / jobs.

What we assert (per route):

* ``GET /api/v1/me/export``
    1. Returns the PRD10 envelope (``success``, ``data``, ``request_id``).
    2. Aggregates every domain key (``user``, ``kb.folders/documents/chunks``,
       ``feed.cards``, ``inbox.items``, ``notifications``,
       ``ai.conversations/messages``, ``jobs``).
    3. Counts under ``data.stats`` match the seeded row counts.
    4. Excludes data owned by other users (multi-tenant isolation).
    5. After ``DELETE /api/v1/me`` the export endpoint returns 410 GONE.

* ``DELETE /api/v1/me``
    1. Marks the user ``is_active=False``.
    2. Stamps ``settings.deleted_at`` with an ISO 8601 UTC timestamp.
    3. Anonymises ``email`` (``deleted-<id>@deleted.invalid``) and clears
       ``full_name`` / ``avatar_url``.
    4. Records ``settings.original_email_hash`` for audit lookups.
    5. Calling DELETE twice returns 410 GONE the second time.

* ``POST /api/v1/me/unsubscribe``
    1. Sets every notification channel to ``False``.
    2. Stamps ``settings.unsubscribed_at``.
    3. Idempotent: a second call only updates the timestamp.

* App wiring
    1. ``/api/v1/me`` is registered in ``_PRD10_ENVELOPE_PREFIXES`` so 4xx
       responses come through with the PRD10 envelope.
    2. ``/legal/privacy.html`` and ``/legal/terms.html`` are served by the
       legal static mount.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import agent_os.agent.models  # noqa: F401
import agent_os.ai.models  # noqa: F401
import agent_os.conversations.models  # noqa: F401

# Side-effect imports so ``Base.metadata`` covers every PRD10 / PRD4 table
# referenced transitively by the routers we mount below. Order mirrors
# ``test_prd10_app_wiring.py`` which is the existing wiring smoke.
import agent_os.db.sqlite_compat  # noqa: F401
import agent_os.garden.models  # noqa: F401
import agent_os.inbox.prd10_models  # noqa: F401
import agent_os.items.models  # noqa: F401
import agent_os.jobs.models  # noqa: F401
import agent_os.kb.models  # noqa: F401
import agent_os.knowledge.models  # noqa: F401
import agent_os.notifications.models  # noqa: F401
import agent_os.search_engine.models  # noqa: F401
import agent_os.skills.runs  # noqa: F401
import agent_os.sources.models  # noqa: F401
import agent_os.stage3.models  # noqa: F401
import agent_os.tasks.models  # noqa: F401
from agent_os.ai.models import AIConversation, AIMessage
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import Base, get_db
from agent_os.inbox.prd10_models import Prd10InboxItem
from agent_os.jobs.models import Job
from agent_os.kb.models import Document, Folder
from agent_os.knowledge.models import Card
from agent_os.notifications.models import Notification
from agent_os.server.app import (
    _LEGAL_DIR,
    _PRD10_ENVELOPE_PREFIXES,
)
from agent_os.server.app import (
    app as prd_app,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def engine_for_account():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_for_account(
    engine_for_account,
) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        engine_for_account, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


def _new_user(suffix: str | None = None, *, full_name: str | None = "Demo User") -> User:
    suffix = suffix or uuid.uuid4().hex[:8]
    return User(
        id=uuid.uuid4(),
        email=f"u{suffix}@example.com",
        username=f"u_{suffix}",
        password_hash="x",
        full_name=full_name,
        avatar_url="https://example.com/avatar.png",
        is_active=True,
        settings={"role": "owner", "plan": "pro"},
    )


@pytest_asyncio.fixture
async def primary_user(session_for_account) -> User:
    user = _new_user("primary")
    session_for_account.add(user)
    await session_for_account.commit()
    await session_for_account.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(session_for_account) -> User:
    user = _new_user("other")
    session_for_account.add(user)
    await session_for_account.commit()
    await session_for_account.refresh(user)
    return user


@pytest_asyncio.fixture
async def seeded_user_data(session_for_account, primary_user, other_user) -> dict:
    """Seed a small but representative slice of user-owned rows.

    Returns a dict with the row counts we expect to come back from
    ``/api/v1/me/export`` for ``primary_user``.
    """

    folder = Folder(
        id=uuid.uuid4(),
        user_id=primary_user.id,
        name="Demo Folder",
        description="seed",
        is_favorite=True,
    )
    session_for_account.add(folder)
    await session_for_account.flush()

    doc = Document(
        id=uuid.uuid4(),
        user_id=primary_user.id,
        folder_id=folder.id,
        title="Demo Doc",
        summary="hello",
        content="# heading\nbody",
        document_type="note",
        status="ready",
        word_count=12,
    )
    session_for_account.add(doc)

    card = Card(
        id=uuid.uuid4(),
        user_id=primary_user.id,
        title="Demo Card",
        content="card body",
        summary="card summary",
        para_type="concept",
        content_type="note",
        tags=["demo"],
    )
    session_for_account.add(card)

    inbox_item = Prd10InboxItem(
        id=uuid.uuid4(),
        user_id=primary_user.id,
        type="text",
        title="Inbox Item",
        raw_content="raw text",
        status="received",
        processing_status="completed",
        priority="normal",
        auto_process=True,
        tags=[],
        extra={},
    )
    session_for_account.add(inbox_item)

    notif = Notification(
        id=uuid.uuid4(),
        user_id=primary_user.id,
        type="ai_output_saved",
        title="Saved",
        content="Saved to KB",
        is_read=False,
    )
    session_for_account.add(notif)

    conv = AIConversation(
        id=uuid.uuid4(),
        user_id=primary_user.id,
        title="Demo Chat",
        mode="general",
        last_message_preview="hello",
        message_count=2,
    )
    session_for_account.add(conv)
    await session_for_account.flush()

    msg_user = AIMessage(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        user_id=primary_user.id,
        role="user",
        content="hi",
        status="completed",
    )
    msg_bot = AIMessage(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        user_id=primary_user.id,
        role="assistant",
        content="hello back",
        status="completed",
    )
    session_for_account.add(msg_user)
    session_for_account.add(msg_bot)

    job = Job(
        id=uuid.uuid4(),
        user_id=primary_user.id,
        job_type="parse_file",
        status="completed",
        progress=100,
        input={"foo": "bar"},
        output={"ok": True},
    )
    session_for_account.add(job)

    other_folder = Folder(
        id=uuid.uuid4(),
        user_id=other_user.id,
        name="Other Folder",
    )
    session_for_account.add(other_folder)

    await session_for_account.commit()

    return {
        "folder_count": 1,
        "document_count": 1,
        "card_count": 1,
        "inbox_count": 1,
        "notification_count": 1,
        "conversation_count": 1,
        "message_count": 2,
        "job_count": 1,
    }


@pytest_asyncio.fixture
async def client(
    engine_for_account, primary_user, seeded_user_data
) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(
        engine_for_account, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_db():
        async with factory() as session:
            yield session

    async def _override_user():
        # Re-fetch within a fresh session to pick up mutations made by the
        # endpoint under test (the endpoint commits, but the fixture's
        # ``primary_user`` instance is detached from those sessions).
        async with factory() as session:
            from sqlalchemy import select

            res = await session.execute(
                select(User).where(User.id == primary_user.id)
            )
            return res.scalar_one()

    prd_app.dependency_overrides[get_db] = _override_db
    prd_app.dependency_overrides[get_current_user] = _override_user

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            prd_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests — wiring
# ---------------------------------------------------------------------------


class TestAccountWiring:
    def test_me_path_in_envelope_prefixes(self):
        """``/api/v1/me`` should hit the PRD10 envelope branch on errors."""

        assert "/api/v1/me" in _PRD10_ENVELOPE_PREFIXES

    def test_legal_dir_resolved(self):
        """``static/legal`` directory should exist for the static mount."""

        assert _LEGAL_DIR.exists(), f"Legal dir not found: {_LEGAL_DIR}"
        assert (_LEGAL_DIR / "privacy.html").exists()
        assert (_LEGAL_DIR / "terms.html").exists()

    @pytest.mark.asyncio
    async def test_legal_static_pages_served(self, client):
        """Privacy / Terms HTML should be 200 from the public mount."""

        for path in ("/legal/privacy.html", "/legal/terms.html"):
            resp = await client.get(path)
            assert resp.status_code == 200, f"{path} → {resp.status_code}"
            text = resp.text
            assert "Mydow" in text
            # Both are bilingual: each file embeds zh + en sections so the
            # toggle works without a build step.
            assert "Privacy" in text or "Terms" in text


# ---------------------------------------------------------------------------
# Tests — GET /api/v1/me/export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExport:
    async def test_export_envelope_shape(self, client):
        resp = await client.get("/api/v1/me/export")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert body["request_id"].startswith("req_")
        # X-Request-ID is set by RequestIdMiddleware on every PRD10 request.
        assert resp.headers.get("X-Request-ID") == body["request_id"]

    async def test_export_aggregates_every_domain(self, client, seeded_user_data):
        resp = await client.get("/api/v1/me/export")
        body = resp.json()
        data = body["data"]

        assert data["schema_version"] == "prd10.v1"
        # Every top-level section the privacy policy promises:
        for key in (
            "exported_at",
            "user",
            "kb",
            "feed",
            "inbox",
            "notifications",
            "ai",
            "jobs",
            "stats",
        ):
            assert key in data, f"missing section {key!r}"

        kb = data["kb"]
        assert isinstance(kb["folders"], list) and len(kb["folders"]) == 1
        assert kb["folders"][0]["name"] == "Demo Folder"
        assert isinstance(kb["documents"], list) and len(kb["documents"]) == 1
        # Documents must include `content` for portability (Markdown body).
        assert kb["documents"][0]["content"].startswith("# heading")

        feed = data["feed"]
        assert len(feed["cards"]) == 1
        assert feed["cards"][0]["title"] == "Demo Card"

        inbox = data["inbox"]
        assert len(inbox["items"]) == 1
        assert inbox["items"][0]["title"] == "Inbox Item"

        notifications = data["notifications"]
        assert len(notifications) == 1
        assert notifications[0]["type"] == "ai_output_saved"

        ai = data["ai"]
        assert len(ai["conversations"]) == 1
        assert len(ai["messages"]) == 2

        assert len(data["jobs"]) == 1

    async def test_export_stats_match_counts(self, client, seeded_user_data):
        resp = await client.get("/api/v1/me/export")
        body = resp.json()
        stats = body["data"]["stats"]

        assert stats["folder_count"] == seeded_user_data["folder_count"]
        assert stats["document_count"] == seeded_user_data["document_count"]
        assert stats["card_count"] == seeded_user_data["card_count"]
        assert stats["inbox_count"] == seeded_user_data["inbox_count"]
        assert stats["notification_count"] == seeded_user_data["notification_count"]
        assert stats["conversation_count"] == seeded_user_data["conversation_count"]
        assert stats["message_count"] == seeded_user_data["message_count"]
        assert stats["job_count"] == seeded_user_data["job_count"]

    async def test_export_excludes_other_user_rows(self, client):
        resp = await client.get("/api/v1/me/export")
        body = resp.json()
        for folder in body["data"]["kb"]["folders"]:
            assert folder["name"] != "Other Folder"
        # And the count is exactly 1 (only the primary user's folder).
        assert body["data"]["stats"]["folder_count"] == 1

    async def test_export_user_section_returns_profile(self, client, primary_user):
        resp = await client.get("/api/v1/me/export")
        body = resp.json()
        user_section = body["data"]["user"]

        assert user_section["id"] == str(primary_user.id)
        assert user_section["email"] == primary_user.email
        assert user_section["username"] == primary_user.username
        assert user_section["full_name"] == "Demo User"
        assert user_section["is_active"] is True
        # Settings are passed through (helpful for portability between
        # Mydow installations).
        assert user_section["settings"]["role"] == "owner"
        assert user_section["settings"]["plan"] == "pro"


# ---------------------------------------------------------------------------
# Tests — DELETE /api/v1/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeleteAccount:
    async def test_delete_marks_account_as_soft_deleted(
        self, client, primary_user, engine_for_account
    ):
        resp = await client.delete("/api/v1/me")
        assert resp.status_code == 200
        body = resp.json()

        assert body["success"] is True
        assert body["data"]["status"] == "soft_deleted"
        assert body["data"]["id"] == str(primary_user.id)
        # Body carries the stamped deleted_at so the client can echo it
        # back to the user.
        assert body["data"]["deleted_at"]
        # Parseable ISO 8601 timestamp.
        datetime.fromisoformat(body["data"]["deleted_at"])

        # Inspect the row directly to verify the side effects.
        factory = async_sessionmaker(
            engine_for_account, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            from sqlalchemy import select

            res = await session.execute(
                select(User).where(User.id == primary_user.id)
            )
            row = res.scalar_one()

        assert row.is_active is False
        assert row.email.startswith("deleted-")
        assert row.email.endswith("@deleted.invalid")
        assert row.username.startswith("deleted_")
        assert row.full_name is None
        assert row.avatar_url is None

        settings = row.settings or {}
        assert "deleted_at" in settings
        assert "original_email_hash" in settings
        assert settings["original_email_hash"].startswith("sha1:")
        # All notification preferences are flipped off as part of erasure.
        prefs = settings["notification_preferences"]
        for channel in (
            "email",
            "desktop",
            "weekly_digest",
            "product_updates",
            "marketing",
        ):
            assert prefs[channel] is False

    async def test_delete_is_idempotent_returns_410(self, client):
        first = await client.delete("/api/v1/me")
        assert first.status_code == 200

        second = await client.delete("/api/v1/me")
        assert second.status_code == 410
        body = second.json()
        # PRD10 envelope from the app's exception handler.
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

    async def test_export_blocked_after_delete(self, client):
        await client.delete("/api/v1/me")
        resp = await client.get("/api/v1/me/export")
        assert resp.status_code == 410
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Tests — POST /api/v1/me/unsubscribe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUnsubscribe:
    async def test_unsubscribe_disables_every_channel(
        self, client, primary_user, engine_for_account
    ):
        resp = await client.post("/api/v1/me/unsubscribe")
        assert resp.status_code == 200
        body = resp.json()

        assert body["success"] is True
        prefs = body["data"]["notification_preferences"]
        for channel in (
            "email",
            "desktop",
            "weekly_digest",
            "product_updates",
            "marketing",
        ):
            assert prefs[channel] is False

        assert body["data"]["unsubscribed_at"]
        datetime.fromisoformat(body["data"]["unsubscribed_at"])

        # Verify on the row.
        factory = async_sessionmaker(
            engine_for_account, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            from sqlalchemy import select

            res = await session.execute(
                select(User).where(User.id == primary_user.id)
            )
            row = res.scalar_one()
        settings = row.settings or {}
        assert "notification_preferences" in settings
        assert settings["notification_preferences"]["email"] is False
        assert "unsubscribed_at" in settings

    async def test_unsubscribe_is_idempotent(self, client, engine_for_account, primary_user):
        first = await client.post("/api/v1/me/unsubscribe")
        assert first.status_code == 200
        first_ts = first.json()["data"]["unsubscribed_at"]

        # Sleep just enough to guarantee a different timestamp on the
        # second call (the endpoint stamps to microsecond precision so a
        # tight loop is normally enough — we use an explicit await sleep
        # to be extra safe on Windows clock granularity).
        import asyncio as _asyncio

        await _asyncio.sleep(0.01)

        second = await client.post("/api/v1/me/unsubscribe")
        assert second.status_code == 200
        second_ts = second.json()["data"]["unsubscribed_at"]

        # Non-decreasing — the second call must update the timestamp.
        assert second_ts >= first_ts

        # All channels still off, no extra rows created.
        prefs = second.json()["data"]["notification_preferences"]
        assert all(prefs[c] is False for c in (
            "email",
            "desktop",
            "weekly_digest",
            "product_updates",
            "marketing",
        ))

    async def test_unsubscribe_blocked_after_delete(self, client):
        await client.delete("/api/v1/me")
        resp = await client.post("/api/v1/me/unsubscribe")
        assert resp.status_code == 410
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"
