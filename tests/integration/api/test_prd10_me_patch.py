"""PRD10 §5.1 / §5.2 ``PATCH /api/v1/me`` integration tests.

Covers the new endpoint introduced for §15.23 of the multi-agent todo:
the personal-center / settings page in the biz prototype writes user
preferences (theme, auto_save, two_factor_enabled, notification_channels,
default_ai_model, …) through this endpoint instead of the static
``data-toast`` placeholders.

The tests deliberately exercise the security boundary: ``role`` and ``plan``
must NOT be elevated through this endpoint, and unknown top-level fields
must be rejected with HTTP 422 by Pydantic ``extra="forbid"``.

Reuses the pattern from ``test_auth_api.py``: per-test in-memory SQLite,
``Base.metadata.create_all`` for the full PRD10 schema, ASGI client with
``app.dependency_overrides[get_db]`` redirected to the test session.
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
# auth + me_router transitively touches at request time.
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
from agent_os.auth.security import get_password_hash
from agent_os.db.base import Base, get_db
from agent_os.server.app import app

# --------------------------------------------------------------------------
# Fixtures (scoped per-test for full isolation; same pattern as test_auth_api)
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
async def seeded_user(session_factory) -> User:
    """Seed a deterministic user with the legacy ``role`` / ``plan`` shape so
    we can prove the PATCH endpoint refuses to elevate them."""

    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            username="prd10_me_user",
            email="prd10_me@example.com",
            full_name="Demo User",
            avatar_url=None,
            password_hash=get_password_hash("test_pass_123"),
            settings={
                "role": "owner",
                "plan": "free",
                "locale": "zh-CN",
                "timezone": "Asia/Shanghai",
                "theme": "light",
                "notification_channels": {
                    "ai_done": True,
                    "system_alert": True,
                    "knowledge_link": True,
                },
            },
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _login_and_get_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "prd10_me_user", "password": "test_pass_123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_me_unauthenticated_returns_401(client, seeded_user):
    """No auth header → 401, body shaped per FastAPI default error envelope."""
    resp = await client.patch("/api/v1/me", json={"name": "Hacker"})
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_patch_me_basic_name_and_avatar(client, seeded_user):
    """Updating ``name`` and ``avatar_url`` writes the User row directly."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Allison Investor", "avatar_url": "https://cdn/img.png"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "Allison Investor"
    assert data["avatar_url"] == "https://cdn/img.png"
    # PRD10 §5.1 envelope — these top-level fields must be present.
    for k in ("id", "username", "email", "role", "locale", "timezone", "plan", "settings"):
        assert k in data


@pytest.mark.asyncio
async def test_patch_me_settings_deep_merge_notification_channels(
    client, seeded_user
):
    """``notification_channels`` is deep-merged: flipping ``ai_done`` to
    False must NOT delete ``system_alert`` / ``knowledge_link``."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settings": {
                "notification_channels": {"ai_done": False},
                "auto_save": True,
            }
        },
    )
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["auto_save"] is True
    channels = settings["notification_channels"]
    assert channels["ai_done"] is False
    assert channels["system_alert"] is True
    assert channels["knowledge_link"] is True


@pytest.mark.asyncio
async def test_patch_me_rejects_role_and_plan_via_settings(client, seeded_user):
    """Sneaking ``role`` / ``plan`` in via ``settings`` payload must be ignored:
    the server-side whitelist filter drops them and the response shape proves
    the original values are unchanged."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settings": {
                "role": "system",
                "plan": "enterprise",
                "is_active": False,
                "theme": "dark",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "owner"
    assert data["plan"] == "free"
    assert data["is_active"] is True
    # Whitelisted ``theme`` did get applied.
    assert data["settings"]["theme"] == "dark"
    # Forbidden keys never landed in settings either.
    assert data["settings"].get("role") == "owner"  # original
    assert data["settings"].get("plan") == "free"
    assert "is_active" not in data["settings"]


@pytest.mark.asyncio
async def test_patch_me_rejects_unknown_top_level_field(client, seeded_user):
    """Pydantic ``extra='forbid'`` must reject ``email``/``role`` etc. in the
    top level of the request body with 422 — proves clients can't bypass the
    settings whitelist by writing top-level columns."""
    token = await _login_and_get_token(client)

    for forbidden_field, value in [
        ("email", "hacker@example.com"),
        ("role", "system"),
        ("plan", "enterprise"),
        ("is_active", False),
        ("username", "newname"),
    ]:
        resp = await client.patch(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
            json={forbidden_field: value},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for forbidden top-level {forbidden_field}, "
            f"got {resp.status_code}: {resp.text}"
        )


@pytest.mark.asyncio
async def test_patch_me_locale_mirrors_into_settings(client, seeded_user):
    """Convenience: top-level ``locale`` / ``timezone`` are mirrored into
    ``settings`` so the response remains internally consistent and the
    Get/Patch round-trip is idempotent."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"locale": "en-US", "timezone": "America/Los_Angeles"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["locale"] == "en-US"
    assert data["timezone"] == "America/Los_Angeles"
    assert data["settings"]["locale"] == "en-US"
    assert data["settings"]["timezone"] == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_patch_me_idempotent_partial_updates(client, seeded_user):
    """Issue two consecutive partial PATCHes; later writes must not nuke
    earlier writes (deep merge semantics over time)."""
    token = await _login_and_get_token(client)

    r1 = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"settings": {"theme": "dark"}},
    )
    assert r1.status_code == 200
    assert r1.json()["settings"]["theme"] == "dark"

    r2 = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"settings": {"two_factor_enabled": True}},
    )
    assert r2.status_code == 200
    settings = r2.json()["settings"]
    # Both updates persisted.
    assert settings["theme"] == "dark"
    assert settings["two_factor_enabled"] is True


@pytest.mark.asyncio
async def test_patch_me_get_returns_same_shape(client, seeded_user):
    """GET /me after PATCH /me returns the same Prd10MeResponse — proves the
    biz frontend can swap its cached profile in one round-trip without
    re-fetching."""
    token = await _login_and_get_token(client)

    patch_resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Display Name",
            "settings": {"default_ai_model": "Mydow Pro"},
        },
    )
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()

    get_resp = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    get_data = get_resp.json()

    assert patch_data["name"] == get_data["name"] == "Display Name"
    assert (
        patch_data["settings"]["default_ai_model"]
        == get_data["settings"]["default_ai_model"]
        == "Mydow Pro"
    )
    # Same envelope keys.
    assert set(patch_data.keys()) >= {
        "id", "name", "username", "avatar_url", "email", "role",
        "locale", "timezone", "plan", "settings",
    }


@pytest.mark.asyncio
async def test_patch_me_filters_unknown_settings_keys(client, seeded_user):
    """Unknown ``settings`` keys outside PRD10_SETTINGS_WHITELIST are silently
    dropped, not echoed back, even though Pydantic accepts arbitrary dicts.

    This is the second line of defense after Pydantic so legacy or third-party
    keys can't sneak into User.settings."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settings": {
                "theme": "dark",
                "is_superuser": True,
                "_internal_billing_override": "free→enterprise",
                "x_random_key": "y",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["theme"] == "dark"
    assert "is_superuser" not in settings
    assert "_internal_billing_override" not in settings
    assert "x_random_key" not in settings


# --------------------------------------------------------------------------
# §15.22 — PATCH /api/v1/me/preferences (convenience alias) tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_me_preferences_unauthenticated_returns_401(
    client, seeded_user
):
    """PATCH /me/preferences is gated behind the same auth dependency."""
    resp = await client.patch(
        "/api/v1/me/preferences", json={"theme": "dark"}
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_patch_me_preferences_flat_body_merges_into_settings(
    client, seeded_user
):
    """The convenience alias accepts a flat preference dict and shallow-merges
    it into ``User.settings`` after running the PRD10 whitelist filter — no
    need for the SPA to wrap the body inside ``{settings: {...}}``."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "theme": "dark",
            "auto_save": True,
            "default_ai_model": "Mydow Pro",
            "default_input_mode": "voice",
            "ai_response_style": "academic",
            "ai_detail_level": "deep",
            "cite_knowledge_by_default": False,
        },
    )
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["theme"] == "dark"
    assert settings["auto_save"] is True
    assert settings["default_ai_model"] == "Mydow Pro"
    assert settings["default_input_mode"] == "voice"
    assert settings["ai_response_style"] == "academic"
    assert settings["ai_detail_level"] == "deep"
    assert settings["cite_knowledge_by_default"] is False
    # Pre-existing keys from seed are preserved (shallow merge).
    assert settings["locale"] == "zh-CN"
    assert settings["timezone"] == "Asia/Shanghai"


@pytest.mark.asyncio
async def test_patch_me_preferences_notification_channels_deep_merge(
    client, seeded_user
):
    """Like PATCH /me, the notification_channels sub-dict is deep-merged so
    flipping one channel doesn't wipe siblings — the biz settings page can
    PATCH a single key safely."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "notification_channels": {"ai_done": False},
        },
    )
    assert resp.status_code == 200, resp.text
    channels = resp.json()["settings"]["notification_channels"]
    assert channels["ai_done"] is False
    assert channels["system_alert"] is True
    assert channels["knowledge_link"] is True


@pytest.mark.asyncio
async def test_patch_me_preferences_drops_privileged_keys(client, seeded_user):
    """Sneaking ``role`` / ``plan`` / ``is_active`` via the flat alias body
    must NOT elevate them — same whitelist as PATCH /me."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "role": "system",
            "plan": "enterprise",
            "is_active": False,
            "theme": "dark",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "owner"
    assert data["plan"] == "free"
    assert data["is_active"] is True
    assert data["settings"]["theme"] == "dark"


@pytest.mark.asyncio
async def test_patch_me_preferences_filters_unknown_keys(client, seeded_user):
    """Unknown keys outside the whitelist are silently dropped, mirroring
    PATCH /me behaviour."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "auto_save": True,
            "totally_made_up_key": "value",
            "_internal": "leak",
        },
    )
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["auto_save"] is True
    assert "totally_made_up_key" not in settings
    assert "_internal" not in settings


@pytest.mark.asyncio
async def test_patch_me_preferences_returns_same_envelope_as_get_me(
    client, seeded_user
):
    """The alias returns the canonical Prd10MeResponse so the SPA can replace
    its cached profile state in one round-trip after toggling a setting."""
    token = await _login_and_get_token(client)

    patch_resp = await client.patch(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={"theme": "dark", "two_factor_enabled": True},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patch_data = patch_resp.json()

    get_resp = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    get_data = get_resp.json()

    # Same envelope shape; canonical /me reflects the alias write.
    for key in ("id", "name", "username", "email", "role", "locale", "timezone", "plan", "settings"):
        assert key in patch_data
        assert key in get_data
    assert get_data["settings"]["theme"] == "dark"
    assert get_data["settings"]["two_factor_enabled"] is True


@pytest.mark.asyncio
async def test_patch_me_preferences_empty_body_is_noop(client, seeded_user):
    """An empty JSON body returns the current Prd10MeResponse unchanged so
    front-end probes (e.g. ``await api.patchPrefs({})``) don't accidentally
    reset preferences."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["theme"] == "light"
    assert settings["locale"] == "zh-CN"
    assert settings["notification_channels"]["ai_done"] is True


@pytest.mark.asyncio
async def test_patch_me_preferences_rejects_non_object_body(client, seeded_user):
    """A bare list / string body must not crash the endpoint; FastAPI's
    body validator returns 422 for non-object JSON, which is good enough as a
    smoke (no need to reach the inner ``isinstance`` guard)."""
    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
        content=b'"just a string"',
    )
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------------
# §15.25 / §15.26 — biz-prototype editProfile + notificationSettings modals
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_me_persists_display_role_for_biz_editprofile_modal(
    client, seeded_user
):
    """§15.26 — the biz prototype's `editProfile` modal lets the user
    type a free-form 角色 string ("Pro Plan 用户" / "产品经理" / ...). The
    bridge sends it as ``settings.display_role``; the whitelist must
    accept it (PRD10_SETTINGS_WHITELIST extension) and the GET /me
    round-trip must surface it so the sidebar / topbar / settings page
    can re-render with the user's custom label."""

    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "投资人 Demo",
            "settings": {"display_role": "产品负责人"},
        },
    )
    assert resp.status_code == 200, resp.text
    patch_data = resp.json()
    assert patch_data["name"] == "投资人 Demo"
    assert patch_data["settings"]["display_role"] == "产品负责人"

    # Round-trip through GET /me — sidebar/topbar reads the same envelope.
    get_resp = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["settings"]["display_role"] == "产品负责人"
    # Privileged keys still untouched after a display-role write.
    assert get_resp.json()["plan"] == "free"
    assert get_resp.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_patch_me_biz_notificationsettings_modal_payload(
    client, seeded_user
):
    """§15.25 — the biz prototype's `notificationSettings` modal sends 3
    toggles mapped to PRD10 keys: ``notification_enabled`` (top-level
    switch for 浏览器通知) plus ``notification_channels.{ai_done,
    knowledge_link}`` (AI 任务结果 / 知识连接提醒). Replays the exact
    bridge.js payload shape and verifies the resulting settings."""

    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settings": {
                "notification_enabled": False,
                "notification_channels": {
                    "ai_done": False,
                    "knowledge_link": True,
                },
            }
        },
    )
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["notification_enabled"] is False
    channels = settings["notification_channels"]
    # Toggled by the bridge.
    assert channels["ai_done"] is False
    assert channels["knowledge_link"] is True
    # Untouched siblings preserved by the deep-merge contract.
    assert channels["system_alert"] is True


@pytest.mark.asyncio
async def test_patch_me_does_not_let_random_notification_channel_keys_leak(
    client, seeded_user
):
    """§15.25 defensive — even if the bridge accidentally sends a channel
    key outside PRD10_NOTIFICATION_CHANNEL_KEYS (e.g. typo'd
    ``garden_connection``), the inner whitelist must drop it so the
    persisted notification_channels stays clean."""

    token = await _login_and_get_token(client)

    resp = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "settings": {
                "notification_channels": {
                    "ai_done": False,
                    "garden_connection_typo": True,
                    "internal_admin_alert": True,
                }
            }
        },
    )
    assert resp.status_code == 200, resp.text
    channels = resp.json()["settings"]["notification_channels"]
    assert channels["ai_done"] is False
    assert "garden_connection_typo" not in channels
    assert "internal_admin_alert" not in channels
