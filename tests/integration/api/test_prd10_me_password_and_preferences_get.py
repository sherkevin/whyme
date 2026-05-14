"""PRD10 §15 /me follow-up: ``GET /api/v1/me/preferences`` + ``POST /api/v1/me/password``.

These tests cover the two endpoints owned by §8.16 (Agent my-mcp-22) that
fill the gap left by §15.22 / §15.23 ``PATCH /me`` work:

* ``GET /api/v1/me/preferences`` — read-only projection of PRD10 §5.2
  ``UserPreference`` shape with safe defaults, used by the biz settings
  page to hydrate toggles even on a brand-new account.
* ``POST /api/v1/me/password`` — rotate the user's password; biz security
  tab "修改密码" button. Requires the current password (so a stolen access
  token cannot silently lock the legitimate owner out) and rejects no-op
  rotations.

Mirrors the per-test in-memory SQLite isolation pattern from
``test_prd10_me_patch.py`` so cross-agent edits to either file stay
independent.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

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

# Side-effect imports so ``Base.metadata.create_all`` covers everything the
# auth + me_router transitively touches at request time. Same set as
# ``test_prd10_me_patch.py`` to guarantee FK targets exist.
import agent_os.ai.models  # noqa: F401
import agent_os.conversations.models  # noqa: F401
import agent_os.db.sqlite_compat  # noqa: F401  (PG UUID -> CHAR(32))
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
from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash, verify_password
from agent_os.db.base import Base, get_db
from agent_os.server.app import app

# --------------------------------------------------------------------------
# Fixtures (per-test isolation, identical to test_prd10_me_patch.py)
# --------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_engine():
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
async def session_factory(test_engine):
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def client(test_engine, session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def fresh_user(session_factory) -> User:
    """User with empty ``settings`` — exercises GET /me/preferences defaults."""

    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            username="prefs_fresh",
            email="prefs_fresh@example.com",
            full_name="Fresh User",
            avatar_url=None,
            password_hash=get_password_hash("orig_pass_456"),
            settings={},
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seeded_user(session_factory) -> User:
    """User with partial preferences already written — exercises merge path."""

    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            username="prefs_seeded",
            email="prefs_seeded@example.com",
            full_name="Seeded User",
            avatar_url=None,
            password_hash=get_password_hash("orig_pass_456"),
            settings={
                "theme": "dark",
                "auto_save": False,
                "default_ai_model": "Mydow Pro",
                "notification_channels": {
                    "ai_done": False,
                    "knowledge_link": True,
                    # system_alert / job_completed deliberately absent so we
                    # can prove the GET endpoint backfills them with defaults.
                },
                # Privileged + unknown keys — must NOT be exposed by the
                # PRD10 §5.2 projection.
                "role": "system",
                "plan": "enterprise",
                "_internal_billing_override": True,
            },
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _login(client: AsyncClient, *, username: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# --------------------------------------------------------------------------
# GET /api/v1/me/preferences
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_preferences_unauthenticated_returns_401(client, fresh_user):
    resp = await client.get("/api/v1/me/preferences")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_get_me_preferences_fresh_account_returns_full_default_shape(
    client, fresh_user
):
    """A brand-new account with empty ``settings`` must still hydrate the
    full PRD10 §5.2 ``UserPreference`` envelope so the SPA settings page can
    render every toggle without a null guard."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.get(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Every PRD10 §5.2 key must be present.
    expected_keys = {
        "default_view",
        "default_input_mode",
        "theme",
        "language",
        "locale",
        "timezone",
        "ai_response_style",
        "ai_detail_level",
        "cite_knowledge_by_default",
        "ai_auto_suggest",
        "ai_streaming",
        "default_ai_model",
        "daily_report_time",
        "notification_enabled",
        "auto_save",
        "two_factor_enabled",
        "notification_channels",
    }
    assert expected_keys <= set(body.keys()), (
        f"Missing keys: {expected_keys - set(body.keys())}"
    )

    # Defaults match what's documented in PRD10 §5.2.
    assert body["default_view"] == "card"
    assert body["theme"] == "light"
    assert body["language"] == "zh-CN"
    assert body["locale"] == "zh-CN"
    assert body["timezone"] == "Asia/Shanghai"
    assert body["ai_response_style"] == "concise_structured"
    assert body["ai_detail_level"] == "balanced"
    assert body["cite_knowledge_by_default"] is True
    assert body["ai_auto_suggest"] is True
    assert body["ai_streaming"] is True
    assert body["default_ai_model"] == "mydow"
    assert body["daily_report_time"] == "21:30"
    assert body["notification_enabled"] is True
    assert body["auto_save"] is True
    assert body["two_factor_enabled"] is False

    # Default channel set is the full PRD10 contract — biz UI relies on this
    # for rendering the notification settings modal even on fresh accounts.
    channels = body["notification_channels"]
    for required_channel in (
        "ai_done",
        "system_alert",
        "knowledge_link",
        "job_completed",
        "job_failed",
        "daily_insight",
    ):
        assert required_channel in channels, (
            f"PRD10 §5.2 requires default channel {required_channel}"
        )


@pytest.mark.asyncio
async def test_me_security_hydrates_real_device_state(client, fresh_user):
    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.get(
        "/api/v1/me/security",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/147.0",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "prefs_fresh@example.com"
    assert body["email_verified"] is False
    assert body["two_factor_enabled"] is False
    assert body["login_devices"][0]["label"] == "Windows · Chrome"
    assert body["login_devices"][0]["current"] is True


@pytest.mark.asyncio
async def test_me_security_email_verification_request_persists_state(
    client, fresh_user
):
    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.post(
        "/api/v1/me/security/email-verification",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "prefs_fresh@example.com"
    assert body["email_verified"] is False
    assert body["email_verification_requested_at"]
    assert body["email_verification_delivery"] in {"local_outbox", "smtp"}
    assert body["request_id"]

    follow_up = await client.get(
        "/api/v1/me/security",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert follow_up.status_code == 200, follow_up.text
    assert follow_up.json()["email_verification_requested_at"] == body["email_verification_requested_at"]


@pytest.mark.asyncio
async def test_me_security_device_refresh_persists_current_session(
    client, fresh_user
):
    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.post(
        "/api/v1/me/security/devices/refresh",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/147.0",
        },
        json={},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["last_security_refresh_at"]
    assert body["login_devices"][0]["label"] == "Windows · Chrome"
    assert body["login_devices"][0]["last_seen_at"]


@pytest.mark.asyncio
async def test_get_me_preferences_merges_partial_settings_with_defaults(
    client, seeded_user
):
    """User-written keys override defaults; missing keys fall back to defaults.

    seeded_user has ``theme=dark`` / ``auto_save=False`` / ``default_ai_model=Mydow Pro``
    explicitly. The GET response must echo those AND backfill the rest.
    """

    token = await _login(client, username="prefs_seeded", password="orig_pass_456")

    resp = await client.get(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["theme"] == "dark"  # user-written wins
    assert body["auto_save"] is False  # user-written wins
    assert body["default_ai_model"] == "Mydow Pro"  # user-written wins
    # Missing keys backfilled to PRD10 §5.2 defaults.
    assert body["language"] == "zh-CN"
    assert body["timezone"] == "Asia/Shanghai"
    assert body["default_view"] == "card"


@pytest.mark.asyncio
async def test_get_me_preferences_notification_channels_deep_merge(
    client, seeded_user
):
    """``notification_channels`` merges the user-written subset on top of the
    PRD10 §5.2 default set so unwritten channels are still listed (with
    their default ``True``/``False``) — the SPA can render every toggle
    without checking which channels have been written before."""

    token = await _login(client, username="prefs_seeded", password="orig_pass_456")

    resp = await client.get(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    channels = resp.json()["notification_channels"]

    # User-written values preserved.
    assert channels["ai_done"] is False
    assert channels["knowledge_link"] is True

    # Unwritten channels fall back to defaults (must still appear).
    assert "system_alert" in channels
    assert "job_completed" in channels
    assert "job_failed" in channels
    assert "daily_insight" in channels


@pytest.mark.asyncio
async def test_get_me_preferences_does_not_leak_privileged_or_unknown_keys(
    client, seeded_user
):
    """``role`` / ``plan`` / random ``_internal_*`` keys live on
    ``User.settings`` for legacy reasons; the PRD10 §5.2 projection MUST NOT
    surface them, so a low-trust client component can render the settings
    page without ever seeing the words ``enterprise`` or ``system``."""

    token = await _login(client, username="prefs_seeded", password="orig_pass_456")

    resp = await client.get(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Privileged or arbitrary keys must NOT be projected.
    assert "role" not in body
    assert "plan" not in body
    assert "_internal_billing_override" not in body
    assert "is_superuser" not in body


@pytest.mark.asyncio
async def test_get_me_preferences_round_trip_after_patch(client, fresh_user):
    """PATCH /me/preferences (the §15.22 alias) → GET /me/preferences must
    reflect the write — the two endpoints are part of the same contract."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")
    headers = {"Authorization": f"Bearer {token}"}

    patch_resp = await client.patch(
        "/api/v1/me/preferences",
        headers=headers,
        json={
            "theme": "dark",
            "two_factor_enabled": True,
            "auto_save": False,
            "ai_response_style": "detailed",
            "ai_detail_level": "brief",
            "cite_knowledge_by_default": False,
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text

    get_resp = await client.get("/api/v1/me/preferences", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    body = get_resp.json()
    assert body["theme"] == "dark"
    assert body["two_factor_enabled"] is True
    assert body["auto_save"] is False
    assert body["ai_response_style"] == "detailed"
    assert body["ai_detail_level"] == "brief"
    assert body["cite_knowledge_by_default"] is False


# --------------------------------------------------------------------------
# POST /api/v1/me/password
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_me_password_unauthenticated_returns_401(client, fresh_user):
    resp = await client.post(
        "/api/v1/me/password",
        json={"current_password": "orig_pass_456", "new_password": "new_secret_789"},
    )
    assert resp.status_code == 401, resp.text


def _envelope_error_message(body: dict) -> str:
    """Helper: read the error message regardless of envelope vs flat shape.

    /api/v1/me/* runs through ``http_exception_to_envelope`` so the body is
    ``{success: false, error: {code, message, details}, request_id}``. Some
    other auth endpoints (and FastAPI defaults) still use
    ``{detail: ...}``; this helper handles both.
    """

    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or "").lower()
    return str(body.get("detail") or "").lower()


@pytest.mark.asyncio
async def test_post_me_password_wrong_current_returns_400(client, fresh_user):
    """Wrong current_password ⇒ 400 + clear error message; the password
    must NOT be rotated (login with original password still works)."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.post(
        "/api/v1/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "totally_wrong_xxx",
            "new_password": "new_secret_789",
        },
    )
    assert resp.status_code == 400, resp.text
    msg = _envelope_error_message(resp.json())
    assert "current" in msg or "incorrect" in msg, resp.text

    # Password NOT rotated — original still works.
    relogin = await client.post(
        "/api/v1/auth/login",
        json={"username": "prefs_fresh", "password": "orig_pass_456"},
    )
    assert relogin.status_code == 200, relogin.text


@pytest.mark.asyncio
async def test_post_me_password_same_as_current_returns_400(client, fresh_user):
    """Re-setting the same password is a no-op risk (audit trail noise) —
    server rejects with 400 + ``differ`` keyword in the error so the SPA can
    surface it inline next to the new-password input."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.post(
        "/api/v1/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "orig_pass_456",
            "new_password": "orig_pass_456",
        },
    )
    assert resp.status_code == 400, resp.text
    msg = _envelope_error_message(resp.json())
    assert "differ" in msg or "same" in msg or "different" in msg, resp.text


@pytest.mark.asyncio
async def test_post_me_password_success_rotates_and_login_with_new_password(
    client, fresh_user, session_factory
):
    """Happy path: 200, response is the documented Prd10PasswordUpdateResponse,
    DB is updated, login with the new password succeeds and login with the
    old password fails."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.post(
        "/api/v1/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "orig_pass_456",
            "new_password": "rotated_pass_xyz",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rotated"] is True
    assert body["id"] == str(fresh_user.id)
    assert "updated_at" in body

    # DB-level confirmation that the hash actually changed.
    async with session_factory() as session:
        from sqlalchemy import select
        row = (
            await session.execute(
                select(User).where(User.id == fresh_user.id)
            )
        ).scalar_one()
        assert verify_password("rotated_pass_xyz", row.password_hash)
        assert not verify_password("orig_pass_456", row.password_hash)

    # Functional check: new password works, old one doesn't.
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "prefs_fresh", "password": "rotated_pass_xyz"},
    )
    assert new_login.status_code == 200, new_login.text

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "prefs_fresh", "password": "orig_pass_456"},
    )
    assert old_login.status_code == 401, old_login.text


@pytest.mark.asyncio
async def test_post_me_password_short_new_password_returns_422(client, fresh_user):
    """Pydantic ``min_length=6`` on ``new_password`` rejects too-short
    rotations before the endpoint ever runs."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.post(
        "/api/v1/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "orig_pass_456", "new_password": "abc"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_post_me_password_missing_field_returns_422(client, fresh_user):
    """Both fields are required; omitting either trips Pydantic validation."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")
    headers = {"Authorization": f"Bearer {token}"}

    for partial_body in (
        {"new_password": "rotated_pass_xyz"},
        {"current_password": "orig_pass_456"},
        {},
    ):
        resp = await client.post(
            "/api/v1/me/password", headers=headers, json=partial_body
        )
        assert resp.status_code == 422, (
            f"Expected 422 for {partial_body}, got {resp.status_code}: {resp.text}"
        )


@pytest.mark.asyncio
async def test_post_me_password_rejects_extra_fields(client, fresh_user):
    """``extra='forbid'`` on Prd10PasswordUpdate ensures the endpoint can't
    be used as a backdoor to write arbitrary other fields."""

    token = await _login(client, username="prefs_fresh", password="orig_pass_456")

    resp = await client.post(
        "/api/v1/me/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "orig_pass_456",
            "new_password": "rotated_pass_xyz",
            # unauthorised side-channels:
            "username": "hacker",
            "is_superuser": True,
            "settings": {"role": "system"},
        },
    )
    assert resp.status_code == 422, resp.text
