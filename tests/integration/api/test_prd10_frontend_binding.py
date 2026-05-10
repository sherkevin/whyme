"""End-to-end binding smoke tests: Mydow Web frontend + PRD10 backend.

These tests prove that the bundle delivered in
``Mydow_Web_Frontend_Complete_Package.zip`` (deployed to ``static/mydow``)
is reachable through the FastAPI app **and** that every PRD10 backend path
the bundled ``mydow-api.js`` exercises is live in the same app instance.

We don't drive the DOM here — that's E2E's job. The goal is to verify the
contract surface a real browser would call, end-to-end against the real
``agent_os.server.app`` with a fixture user and an in-memory SQLite DB.
"""

from __future__ import annotations

import uuid
import json
from collections.abc import AsyncGenerator
from pathlib import Path

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

# Side-effect imports so ``Base.metadata.create_all`` covers everything.
import agent_os.ai.models  # noqa: F401
import agent_os.conversations.models  # noqa: F401
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
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import Base, get_db
from agent_os.server.app import app as prd_app

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MYDOW_DIR = PROJECT_ROOT / "static" / "mydow"


def _envelope_data(payload: dict) -> dict:
    """Return PRD10 envelope data while tolerating legacy flat demo payloads."""

    if payload.get("success") is True and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


# ---------------------------------------------------------------------------
# Fixtures
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
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def fixture_user(prd10_engine) -> User:
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
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
async def client(prd10_engine, fixture_user) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_db():
        async with factory() as session:
            yield session

    async def _override_user():
        return fixture_user

    prd_app.dependency_overrides[get_db] = _override_db
    prd_app.dependency_overrides[get_current_user] = _override_user

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            prd_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Static bundle reachability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFrontendBundleReachable:
    async def test_root_serves_landing_or_redirects_to_biz(self, client):
        """PRD10 §10.5 / §15.20 — ``/`` now serves an investor-friendly landing
        page (when ``static/landing/index.html`` exists) instead of the older
        307 redirect to the demo workspace. ``?go=demo`` keeps the redirect
        behaviour as an opt-in for press / smoke / docker healthcheck. Tests
        accept either: 200 HTML (landing deployed) **or** 307 to the demo
        workspace (``/mydow/biz_v14/`` post §15.34, ``/mydow/biz/`` legacy
        fallback).
        """

        resp = await client.get("/", follow_redirects=False)
        if resp.status_code == 200:
            text = resp.text
            assert "<title>" in text
            # Landing page MUST link to the demo workspace so the CTA is reachable.
            assert "/mydow/biz" in text or "go=demo" in text
        else:
            assert resp.status_code == 307
            assert resp.headers["location"] in {
                "/mydow/biz_v14/",
                "/mydow/biz/",
                "/mydow/",
            }

    async def test_root_with_go_demo_redirects_to_biz(self, client):
        """PRD10 §10.5 / §15.34 — ``?go=demo`` short-circuits to the demo
        workspace; prefers v1.4 bundle when present.
        """

        resp = await client.get("/?go=demo", follow_redirects=False)
        # When the biz bundle exists this is always a 307; when it doesn't
        # exist (rare in CI), falling back to landing or legacy index is fine.
        assert resp.status_code in {200, 307}
        if resp.status_code == 307:
            assert resp.headers["location"] in {"/mydow/biz_v14/", "/mydow/biz/"}

    async def test_mydow_default_entry_redirects_to_biz(self, client):
        """PRD10 §15.20 / §15.34 — ``/mydow/`` is rerouted to the business
        prototype, preferring the v1.4 bundle (the user-facing default
        post-2026-05-07) and falling back to v1.0 when only legacy is present.
        """

        resp = await client.get("/mydow/", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] in {"/mydow/biz_v14/", "/mydow/biz/"}

    async def test_mydow_biz_index_served(self, client):
        """The business prototype HTML is reachable and references bridge.js."""

        resp = await client.get("/mydow/biz/")
        assert resp.status_code == 200
        text = resp.text
        assert "<title>Mydow" in text
        # bridge.js is the runtime hook that re-binds the prototype's
        # buttons to real PRD10 endpoints.
        assert "bridge.js" in text

    async def test_mydow_spa_alias_served(self, client):
        """``/mydow/spa/`` keeps the legacy SPA reachable for regression diff."""

        resp = await client.get("/mydow/spa/")
        assert resp.status_code == 200
        text = resp.text
        assert "<title>Mydow" in text
        # Legacy SPA shell still references mydow-api.js as the contract shim.
        assert 'src="./mydow-api.js"' in text

    async def test_mydow_api_js_served(self, client):
        resp = await client.get("/mydow/mydow-api.js")
        assert resp.status_code == 200
        body = resp.text
        assert "window.MydowAPI" in body
        # The JS must point at /api/v1 by default; otherwise calls won't hit
        # the PRD10 routers wired in app.py.
        assert "/api/v1" in body

    async def test_mydow_handoff_doc_served(self, client):
        resp = await client.get("/mydow/HANDOFF.md")
        assert resp.status_code == 200
        assert "Mydow Web Frontend" in resp.text


# ---------------------------------------------------------------------------
# Every backend path the frontend touches actually responds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBackendBindingsLive:
    """Each test mirrors a `MydowAPI.<domain>.<method>` call from the JS."""

    async def test_search_query(self, client):
        resp = await client.get("/api/v1/search", params={"q": ""})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert resp.headers.get("X-Request-ID")

    async def test_search_suggestions(self, client):
        resp = await client.get("/api/v1/search/suggestions", params={"q": ""})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["suggestions"] == []

    async def test_ai_conversations_list(self, client):
        resp = await client.get("/api/v1/ai/conversations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["items"] == []

    async def test_ai_conversation_create_and_send_message(self, client):
        created = await client.post(
            "/api/v1/ai/conversations",
            json={"title": "Mydow 联调 demo", "mode": "general"},
        )
        assert created.status_code == 201
        cid = created.json()["data"]["id"]

        sent = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "你好"},
        )
        assert sent.status_code == 201
        sent_data = sent.json()["data"]
        assert sent_data["assistant_message"]["role"] == "assistant"
        assert sent_data["job"]["job_type"] == "ai_chat"

    async def test_skills_list(self, client):
        resp = await client.get("/api/v1/skills")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["items"]
        assert body["data"]["items"][0]["name"] == "Mydow 快速总结"

    async def test_garden_overview_and_graph(self, client):
        overview = await client.get("/api/v1/garden/overview")
        assert overview.status_code == 200
        ov = overview.json()["data"]
        assert ov["node_count"] == 0 and ov["edge_count"] == 0

        graph = await client.get("/api/v1/garden/graph")
        assert graph.status_code == 200
        g = graph.json()["data"]
        assert g["nodes"] == [] and g["edges"] == []

    async def test_today_home_binding(self, client):
        resp = await client.get("/api/v1/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert "quick_actions" in data
        assert "stats" in data
        assert resp.headers.get("X-Request-ID")

    async def test_prd10_me_binding(self, client):
        resp = await client.get("/api/v1/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"]
        assert body["email"]


# ---------------------------------------------------------------------------
# Front-end JS contract: the API bundle covers every PRD10 path the
# handoff doc enumerates.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mydow_app_js_covers_prd10_paths():
    """Lock the SPA's API surface in place.

    The deployed bundle ships the real implementation in ``app.js`` and a
    thin contract shim in ``mydow-api.js``. Both files together must
    declare every PRD10 path the SPA ever calls — checking ``app.js`` here
    pins the live behavior (rendering, page transitions, button handlers).
    """

    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")

    must_contain = [
        "/search",
        "/search/suggestions",
        "/ai/conversations",
        "save-to-kb",
        "create-tasks",
        "/skills",
        "/garden/overview",
        "/garden/graph",
        "/feed",
        "/cards",
        "/favorite",
        "/kb/overview",
        "/kb/folders",
        "/kb/documents",
        "/capture/text",
        "/capture/link",
        "/uploads/presign",
        "/capture/file/commit",
        "/notifications",
        "/notifications/read-all",
        "/jobs/",
        "/today",
        "/me",
        "/auth/login",
        "/auth/register",
        "/demo/login",
        "/demo/status",
    ]
    missing = [token for token in must_contain if token not in js]
    assert not missing, f"app.js missing PRD10 hooks: {missing}"


@pytest.mark.asyncio
async def test_mydow_spa_theme_tokens_and_toggle_are_wired():
    css = (MYDOW_DIR / "style.css").read_text(encoding="utf-8")
    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")
    html = (MYDOW_DIR / "index.html").read_text(encoding="utf-8")

    css_tokens = [
        "--space-1:",
        "--space-2:",
        "--space-3:",
        "--space-4:",
        "--text-xs:",
        "--text-xxl:",
        "--radius-xs:",
        "--shadow-sm:",
        "--shadow-md:",
        "--shadow-lg:",
        ':root[data-theme="dark"]',
        ':root[data-theme="light"]',
        '@media (prefers-color-scheme: dark)',
        ".theme-toggle",
    ]
    missing_css = [token for token in css_tokens if token not in css]
    assert not missing_css, f"style.css missing theme tokens: {missing_css}"

    js_tokens = [
        'const THEME_KEY = "mydow_theme"',
        "theme: () =>",
        "setTheme:",
        "function applyTheme",
        "function cycleTheme",
        "data-theme-toggle",
        "localStorage.setItem(THEME_KEY",
    ]
    missing_js = [token for token in js_tokens if token not in js]
    assert not missing_js, f"app.js missing theme wiring: {missing_js}"

    assert 'symbol id="i-sun"' in html
    assert 'symbol id="i-moon"' in html


@pytest.mark.asyncio
async def test_mydow_spa_responsive_breakpoints_are_wired():
    css = (MYDOW_DIR / "style.css").read_text(encoding="utf-8")

    css_tokens = [
        "@media (max-width: 1279px)",
        "@media (max-width: 1100px)",
        "@media (max-width: 767px)",
        "@media (max-width: 420px)",
        "grid-template-columns: 88px 1fr",
        "position: fixed",
        "bottom: 0",
        "height: 72px",
        "env(safe-area-inset-bottom)",
        "scrollbar-width: none",
        "padding-bottom: calc(72px + env(safe-area-inset-bottom))",
    ]
    missing_css = [token for token in css_tokens if token not in css]
    assert not missing_css, f"style.css missing responsive wiring: {missing_css}"


@pytest.mark.asyncio
async def test_mydow_spa_six_state_visual_contract_is_wired():
    css = (MYDOW_DIR / "style.css").read_text(encoding="utf-8")
    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")

    js_tokens = [
        "function stateCard",
        "function stateIllustration",
        "state-visual-svg",
        'icon: "search"',
        'icon: "ai"',
        "function skeletonPage",
        "function emptyState",
        "function errorState",
        "function forbiddenState",
        "function processingState",
        "function successState",
        'class: `state-card state-${type} ${type}-state`',
        'type === "error" || type === "forbidden" ? "alert" : "status"',
        'err.status === 403',
        "uiStates: {",
    ]
    missing_js = [token for token in js_tokens if token not in js]
    assert not missing_js, f"app.js missing six-state wiring: {missing_js}"

    css_tokens = [
        ".state-card",
        ".state-loading",
        ".state-empty",
        ".state-error",
        ".state-forbidden",
        ".state-processing",
        ".state-success",
        ".state-illustration",
        ".state-visual-svg",
        ".state-visual-surface",
        ".state-visual-accent",
        "@keyframes state-spin",
        "@media (prefers-reduced-motion: reduce)",
    ]
    missing_css = [token for token in css_tokens if token not in css]
    assert not missing_css, f"style.css missing six-state styles: {missing_css}"


@pytest.mark.asyncio
async def test_mydow_spa_micro_interactions_are_wired():
    css = (MYDOW_DIR / "style.css").read_text(encoding="utf-8")

    css_tokens = [
        "--motion-fast: 80ms",
        "--motion-base: 160ms",
        "--motion-slow: 240ms",
        "--motion-ease:",
        ".card:hover",
        ".card:active",
        ".is-dragging",
        '[draggable="true"]:active',
        ".drag-over",
        ".bubble.is-typing",
        "@keyframes bubble-in",
        "@keyframes stream-caret",
        "@media (prefers-reduced-motion: reduce)",
        "transition-duration: 1ms !important",
    ]
    missing_css = [token for token in css_tokens if token not in css]
    assert not missing_css, f"style.css missing micro-interactions: {missing_css}"


@pytest.mark.asyncio
async def test_mydow_spa_unified_toast_system_is_wired():
    css = (MYDOW_DIR / "style.css").read_text(encoding="utf-8")
    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")

    js_tokens = [
        "const TOAST_LIMIT = 5",
        'new Set(["info", "success", "warning", "error"])',
        'function toast(msg, kind = "info", options = {})',
        "function dismissToast",
        'role: type === "error" ? "alert" : "status"',
        '"data-toast-kind": type',
        "toast-close",
        'while (stack.querySelectorAll(".toast").length > TOAST_LIMIT)',
    ]
    missing_js = [token for token in js_tokens if token not in js]
    assert not missing_js, f"app.js missing unified toast wiring: {missing_js}"

    css_tokens = [
        ".toast-info",
        ".toast-success",
        ".toast-warning",
        ".toast-error",
        ".toast-close",
        ".toast.is-leaving",
    ]
    missing_css = [token for token in css_tokens if token not in css]
    assert not missing_css, f"style.css missing unified toast styles: {missing_css}"


@pytest.mark.asyncio
async def test_mydow_spa_drag_and_multiselect_are_wired():
    css = (MYDOW_DIR / "style.css").read_text(encoding="utf-8")
    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")

    js_tokens = [
        "feedSelection: new Set()",
        "function updateFeedSelectionToolbar",
        "{ is_archived: true }",
        '"application/x-mydow-document"',
        "A.kb.moveDocument(docId, f.id)",
        "data-garden-node",
        "pointerdown",
        "pointermove",
        "pointerup",
    ]
    missing_js = [token for token in js_tokens if token not in js]
    assert not missing_js, f"app.js missing drag/multiselect wiring: {missing_js}"

    css_tokens = [
        ".feed-selection-toolbar",
        ".feed-card.is-selected",
        '.doc-row[draggable="true"]',
        ".kb-folder.drag-over",
        "[data-garden-node].is-dragging",
    ]
    missing_css = [token for token in css_tokens if token not in css]
    assert not missing_css, f"style.css missing drag/multiselect styles: {missing_css}"


@pytest.mark.asyncio
async def test_mydow_spa_i18n_runtime_is_wired():
    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")
    zh = json.loads((MYDOW_DIR / "i18n" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((MYDOW_DIR / "i18n" / "en.json").read_text(encoding="utf-8"))

    required_keys = [
        "nav.home",
        "topbar.search",
        "locale.toggle",
        "home.submit",
        "empty.search.title",
        "kb.newFolder",
        "ai.empty.cta",
    ]
    for key in required_keys:
        assert zh.get(key), f"zh.json missing {key}"
        assert en.get(key), f"en.json missing {key}"

    js_tokens = [
        'const LOCALE_KEY = "mydow_locale"',
        'const LOCALE_VALUES = ["zh", "en"]',
        "function normalizeLocale",
        "function resolveLocale",
        "async function loadLocale",
        "function t(key, fallback = key, vars = {})",
        "async function setLocale",
        'fetch(`./i18n/${next}.json`',
        "document.documentElement.lang",
        '"data-locale-toggle": ""',
        'api("/me", {',
        't("nav.home"',
        't("home.submit"',
        't("kb.newFolder"',
        't("ai.empty.cta"',
    ]
    missing_js = [token for token in js_tokens if token not in js]
    assert not missing_js, f"app.js missing i18n runtime wiring: {missing_js}"


@pytest.mark.asyncio
async def test_mydow_spa_accessibility_guardrails_are_wired():
    css = (MYDOW_DIR / "style.css").read_text(encoding="utf-8")
    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")

    css_tokens = [
        ".sr-only",
        ":focus-visible",
        "outline: 3px solid",
        "outline-offset: 3px",
        "color-mix(in srgb, var(--primary)",
    ]
    missing_css = [token for token in css_tokens if token not in css]
    assert not missing_css, f"style.css missing a11y CSS: {missing_css}"

    js_tokens = [
        'node.getAttribute("role") === "button"',
        'event.key === "Enter" || event.key === " "',
        '"aria-current":',
        '"aria-label": "主导航"',
        '"aria-label": "Mydow 主导航"',
        '"aria-live": "polite"',
        'tabindex: "-1"',
    ]
    missing_js = [token for token in js_tokens if token not in js]
    assert not missing_js, f"app.js missing a11y wiring: {missing_js}"


@pytest.mark.asyncio
async def test_mydow_primary_action_bindings_are_wired():
    """Agent 4 guardrail: high-intent SPA pages bind to real PRD10 APIs.

    The SPA replaces the legacy hardcoded prototype with JS-rendered pages.
    The contract shifted from "DOM selectors X/Y/Z exist in the static
    HTML" to "the SPA module declares the right routes, render entry
    points, and PRD10 verbs". This test pins both layers.
    """

    html = (MYDOW_DIR / "index.html").read_text(encoding="utf-8")
    js = (MYDOW_DIR / "app.js").read_text(encoding="utf-8")

    html_hooks = [
        '<div id="app"',
        'id="auth-overlay"',
        'id="toast-stack"',
        'href="./style.css"',
        'src="./app.js"',
    ]
    missing_html = [token for token in html_hooks if token not in html]
    assert not missing_html, f"index.html missing SPA hooks: {missing_html}"

    js_hooks = [
        # Page renderers — every PRD10 §2.1 first-level entry has its own.
        "function renderHome",
        "function renderKB",
        "function renderFolder",
        "function renderDoc",
        "function renderAi",
        "function renderSkills",
        "function renderGarden",
        # Drill-down drawers / modals (PRD10 §10/§11/§9).
        "openCardDrawer",
        "openNotificationDrawer",
        "openSearchPanel",
        "openCreateFolderModal",
        "openClipModal",
        "openUploadModal",
        "openSkillRunModal",
        "openDeepResearchModal",
        "openAiSaveToKbModal",
        "openAiCreateTasksModal",
        "function applyPageMode",
        "function syncOverlayState",
        "dataset.drawerOpen",
        "dataset.modalOpen",
        "streamUrl:",
        "cancelMessage:",
        "regenerateMessage:",
        'title: "停止生成"',
        # PRD10 §20 four-state affordances.
        "skeletonPage",
        "emptyState",
        "errorState",
        # Auth / demo entry points.
        "tryDemoAutoLogin",
        "renderAuthOverlay",
        # Public surface.
        "window.MydowAPI = {",
    ]
    missing_js = [token for token in js_hooks if token not in js]
    assert not missing_js, f"app.js missing primary SPA hooks: {missing_js}"


@pytest.mark.asyncio
async def test_mydow_api_js_full_demo_domain_coverage():
    """Agent 4 demo-mode contract: every PRD10 router surface that the
    deployed prototype can possibly invoke is wrapped by a domain client."""

    js = (MYDOW_DIR / "mydow-api.js").read_text(encoding="utf-8")

    domain_clients = [
        "const search = {",
        "const ai = {",
        "const skills = {",
        "const garden = {",
        "const feed = {",
        "const cards = {",
        "const kb = {",
        "const capture = {",
        "const inbox = {",
        "const notifications = {",
        "const jobs = {",
        "const today = {",
        "const me = {",
        "const insights = {",
        "const reports = {",
        "const auth = {",
    ]
    missing = [token for token in domain_clients if token not in js]
    assert not missing, f"mydow-api.js missing domain clients: {missing}"

    public_surface = [
        "window.MydowAPI = {",
        "search,",
        "ai,",
        "skills,",
        "garden,",
        "feed,",
        "cards,",
        "kb,",
        "capture,",
        "inbox,",
        "notifications,",
        "jobs,",
        "today,",
        "me,",
        "insights,",
        "reports,",
        "auth,",
    ]
    missing_surface = [token for token in public_surface if token not in js]
    assert not missing_surface, (
        f"mydow-api.js public surface missing: {missing_surface}"
    )


@pytest.mark.asyncio
async def test_mydow_api_js_has_demo_auto_login_and_renderers():
    """Agent 4 demo build contract: ``mydow-api.js`` ships demo auto-login,
    contenteditable composer support, and live renderers that replace the
    prototype mock blocks with backend-sourced data."""

    js = (MYDOW_DIR / "mydow-api.js").read_text(encoding="utf-8")

    demo_hooks = [
        "tryDemoAutoLogin",
        "/demo/status",
        "/demo/login",
        "Demo auto-login completed",
    ]
    missing_demo = [token for token in demo_hooks if token not in js]
    assert not missing_demo, f"mydow-api.js missing demo bindings: {missing_demo}"

    composer_hooks = [
        "readComposerContent",
        "appendAiBubble",
        "[contenteditable=\\\"true\\\"]",
        "renderHomeFeed",
        "renderKnowledgePage",
        "renderSkillsPage",
        "renderNotifications",
        "renderAiConversationList",
        "renderGardenPage",
        "renderAll",
        ".library-grid",
        ".card-grid",
        ".skill-grid",
        ".notice-list",
    ]
    missing_render = [token for token in composer_hooks if token not in js]
    assert not missing_render, (
        f"mydow-api.js missing render hooks: {missing_render}"
    )

    drilldown_hooks = [
        "openFolderDetail",
        "openDocumentDetail",
        "openCardDetail",
        "showDocumentDrawer",
        "showCardDrawer",
        "applyPageMode",
        "mydow-doc-drawer",
        "mydow-garden-node",
    ]
    missing_drill = [token for token in drilldown_hooks if token not in js]
    assert not missing_drill, (
        f"mydow-api.js missing drill-down hooks: {missing_drill}"
    )


@pytest.mark.asyncio
async def test_demo_endpoints_disabled_by_default(monkeypatch, client):
    """``/api/v1/demo/*`` must be **off** unless ``AGENTOS_DEMO_MODE=on``."""

    monkeypatch.delenv("AGENTOS_DEMO_MODE", raising=False)

    status = await client.get("/api/v1/demo/status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["success"] is True
    body = _envelope_data(status_payload)
    assert body["enabled"] is False
    assert body["email"] is None

    login = await client.post("/api/v1/demo/login")
    assert login.status_code == 403


@pytest.mark.asyncio
async def test_demo_endpoints_enabled_when_flag_set(monkeypatch, client):
    """When demo mode is enabled the login endpoint hands out a session and
    creates the demo user lazily so a fresh DB still works."""

    monkeypatch.setenv("AGENTOS_DEMO_MODE", "on")

    status = await client.get("/api/v1/demo/status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["success"] is True
    payload = _envelope_data(status_payload)
    assert payload["enabled"] is True
    assert payload["email"] == "demo@mydow.example"

    login = await client.post("/api/v1/demo/login")
    assert login.status_code == 200
    login_payload = login.json()
    assert login_payload["success"] is True
    body = _envelope_data(login_payload)
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    # Idempotent: a second call uses the existing user and still succeeds.
    again = await client.post("/api/v1/demo/login")
    assert again.status_code == 200
    again_payload = again.json()
    assert again_payload["success"] is True
    assert _envelope_data(again_payload)["access_token"]


# ---------------------------------------------------------------------------
# PRD10 §15 — Business-prototype lane: ``static/mydow/biz/`` is reachable
# under FastAPI and ``bridge.js`` rebinds the static prototype to real
# ``/api/v1/*`` routes. This is Engineer 1's §15.2 acceptance shim.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBusinessPrototypeBridge:
    """§15.1/§15.2 contract: the business-prototype HTML and bridge.js are
    served from ``/mydow/biz/`` and the bridge wires the high-intent
    PRD10 paths the prototype's inline ``simulateAction`` originally
    stubbed out."""

    async def test_biz_index_served(self, client):
        # ``StaticFiles(html=True)`` resolves directory roots to index.html.
        resp = await client.get("/mydow/biz/")
        assert resp.status_code == 200
        text = resp.text
        # Business prototype keeps the original page title.
        assert "<title>Mydow" in text
        # Bridge module must be referenced, otherwise the prototype keeps
        # its inline ``simulateAction`` stubs and never hits PRD10.
        assert "bridge.js" in text

    async def test_biz_bridge_js_served(self, client):
        resp = await client.get("/mydow/biz/bridge.js")
        assert resp.status_code == 200
        body = resp.text
        # Bridge points at the PRD10 base path.
        assert "/api/v1" in body
        # Bridge keeps an isolated token key so it doesn't collide with
        # the SPA's ``mydow_token`` key when both prototypes coexist.
        assert "mydow_biz_token" in body

    async def test_biz_bridge_js_covers_prd10_paths(self):
        bridge = (MYDOW_DIR / "biz" / "bridge.js").read_text(encoding="utf-8")
        must_contain = [
            "/demo/status",
            "/demo/login",
            "/me",
            "/capture/text",
            # §15.7 modal bindings
            "/capture/link",
            "/uploads/presign",
            "/capture/file/commit",
            "/ai/conversations",
            "/notifications/unread-count",
            "/today",
            "/feed",
            # §15.8 KB
            "/kb/folders",
            # §15.9 KB document list
            "/kb/documents",
            # §15.6 cards
            "/cards/",
            "/favorite",
            # §15.17 notifications list + mark read
            "/notifications/read-all",
            # §15.24 skillRun modal — POST /skills/{id}/run
            "/skills/",
            "/run",
            # §15.22 settings page — PATCH /me/preferences convenience alias
            "/me/preferences",
        ]
        missing = [token for token in must_contain if token not in bridge]
        assert not missing, f"biz/bridge.js missing PRD10 paths: {missing}"

    async def test_biz_bridge_js_exposes_named_helpers(self):
        bridge = (MYDOW_DIR / "biz" / "bridge.js").read_text(encoding="utf-8")
        helpers = [
            "function apiFetch",
            "function ensureSession",
            "function rebindCaptureSubmit",
            "function refreshProfileChip",
            "function refreshUnreadBadge",
            "function refreshTodayInsights",
            "function refreshFeedCounters",
            # §15.7 modal helpers
            "function bindHomeModalSubmits",
            "function uploadAndCommitFile",
            "function handleUploadFileModal",
            "function handleWebLinkModal",
            "function handleDeepResearchModal",
            "function handleVoiceInputModal",
            "function closeAllModals",
            # §15.8 KB
            "function loadKbLibraryGrid",
            "function toggleFolderFavorite",
            "function createFolderFromModal",
            "function bindKbStarActions",
            "function bindKbNewFolderSubmit",
            "function bindKbCardOpenFolder",
            # §15.6 cards
            "function loadCardForDrawer",
            "function hydrateItemDetailDrawer",
            "function bindCardClickToDrawer",
            "function favoriteCardById",
            "function bindCardFavoriteAction",
            # §15.9 folder detail
            "function loadFolderDetail",
            "function bindFolderClickToDetail",
            # §15.17 notifications
            "function loadNotifications",
            "function markNotificationRead",
            "function markAllNotificationsRead",
            "function bindNotificationRowMarkRead",
            "function bindNotificationMarkAll",
            # §15.18 profile main
            "function hydrateProfileMain",
            # §15.10 doc detail/edit
            "function loadDocumentForEditor",
            "function patchCurrentDocument",
            "function bindDocRowClick",
            "function bindDocEditorAutoSave",
            # §15.5j right-rail top stat cards
            "function refreshHomeRightRailStatCards",
            # §15.23 newDocument modal — POST /kb/documents
            "function bindKbNewDocumentSubmit",
            "function handleNewDocumentSubmit",
            "function createDocumentFromModal",
            # §15.24 skillRun modal — POST /skills/{id}/run with form payload
            "function handleSkillRunModal",
            # §15.25 notificationSettings modal — PATCH /me notification toggles
            "function handleNotificationSettingsModal",
            # §15.26 editProfile modal — PATCH /me name + display_role
            "function handleEditProfileModal",
            # §15.22 settings page toggles + confirmDelete logout/clear-cache
            "function attachProfileSettingsHandlers",
            "function bindConfirmDeleteContextTracking",
            "function bindConfirmDeleteSubmit",
            "function bindSettingsPanelHydration",
            # §15.23 boot aliases that hook §15.22 helpers into existing boot
            "function attachSettingsBindings",
            "function _watchProfileMainMutations",
            "function hydrateSettingsControlsFromMe",
            "function patchMePreference",
            "window.MydowBridge",
        ]
        missing = [token for token in helpers if token not in bridge]
        assert not missing, f"biz/bridge.js missing helpers: {missing}"

    async def test_biz_index_keeps_prd10_dom_hooks(self):
        html = (MYDOW_DIR / "biz" / "index.html").read_text(encoding="utf-8")
        # bridge.js relies on these data-attributes/class names for binding;
        # if the business prototype is regenerated and these drift the
        # bridge silently no-ops.
        hooks = [
            "data-open-profile",
            "data-open-notifications",
            "data-search-trigger",
            'data-view-target="recent"',
            'data-view-target="records"',
            'class="account"',
            'class="capture"',
            "send-button",
            # §15.7 modal hooks
            'data-modal="uploadFile"',
            'data-modal="webLink"',
            'data-modal="voiceInput"',
            'data-modal="deepResearch"',
            'data-toast="上传任务已创建"',
            'data-toast="网页已保存到最近捕捉"',
            'data-toast="深度研究任务已创建"',
            # §15.8 KB
            'class="library-grid"',
            'class="library-card"',
            "library-meta",
            "star-action",
            'data-toast="知识库文件夹已创建"',
            # §15.6 cards
            'class="idea-card"',
            'data-drawer="itemDetail"',
            # §15.23 newDocument modal
            'data-modal="newDocument"',
            "data-create-doc",
            # §15.24 skillRun modal — surface (opener wired by bridge to
            # stash skill id; toast label is what bindHomeModalSubmits
            # routes through handleSkillRunModal).
            'data-modal="skillRun"',
            'data-toast="Skill 正在运行"',
            # §15.25 notificationSettings modal — bridge reads the 3
            # toggle-switch states + maps to PRD10 notification_channels.
            'data-modal="notificationSettings"',
            'data-toast="通知设置已保存"',
            # §15.26 editProfile modal — bridge writes name + display_role
            # back to PATCH /me.
            'data-modal="editProfile"',
            'data-toast="个人资料已更新"',
        ]
        missing = [token for token in hooks if token not in html]
        assert not missing, f"biz/index.html lost PRD10 DOM hooks: {missing}"

    async def test_biz_bridge_demo_login_flow_still_works(self, client, monkeypatch):
        """The bridge boots ``/demo/status`` → ``/demo/login`` → ``/me``;
        ensure that round-trip still succeeds end-to-end with the same
        FastAPI app the bridge will hit at runtime."""

        monkeypatch.setenv("AGENTOS_DEMO_MODE", "on")

        status = await client.get("/api/v1/demo/status")
        assert status.status_code == 200
        status_payload = status.json()
        assert status_payload["success"] is True
        assert _envelope_data(status_payload)["enabled"] is True

        login = await client.post("/api/v1/demo/login")
        assert login.status_code == 200
        login_payload = login.json()
        assert login_payload["success"] is True
        token = _envelope_data(login_payload)["access_token"]
        assert token

        # PRD10 §5.1 — bridge calls /me right after login to populate the
        # sidebar chip.
        me = await client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        body = me.json()
        # /me is the legacy auth router which returns a flat envelope; the
        # bridge tolerates both shapes (``data`` wrapped or flat). Either
        # way email + username must be present.
        flat = body if "email" in body else (body.get("data") or {})
        assert flat.get("email")
        assert flat.get("username") or flat.get("name")


@pytest.mark.asyncio
async def test_biz_v14_html_injects_bridge_v14_script(client):
    """§15.32 — ``/mydow/biz_v14/`` injects the v1.4 bridge beside the static HTML."""
    v14_index = MYDOW_DIR / "biz_v14" / "index.html"
    if not v14_index.exists():
        pytest.skip("biz_v14 bundle not present")

    r = await client.get("/mydow/biz_v14/")
    assert r.status_code == 200
    body = r.text
    assert 'data-mydow-bridge-v14="true"' in body
    assert 'data-mydow-darkreader="true"' in body
    assert 'data-mydow-markdown-it="true"' in body
    assert 'src="/mydow/biz_v14/vendor/darkreader.min.js"' in body
    assert 'src="/mydow/biz_v14/vendor/markdown-it.min.js"' in body
    assert 'src="/mydow/biz_v14/bridge_v14.js"' in body

    darkreader = await client.get("/mydow/biz_v14/vendor/darkreader.min.js")
    assert darkreader.status_code == 200
    assert "DarkReader" in darkreader.text
    markdown_it = await client.get("/mydow/biz_v14/vendor/markdown-it.min.js")
    assert markdown_it.status_code == 200
    assert "markdownit" in markdown_it.text


def test_biz_v14_ext_exposes_six_state_runtime():
    """§16.10 — v1.4 extension renders real loading/empty/error states."""

    ext = (MYDOW_DIR / "biz_v14" / "bridge_v14_ext.js").read_text(encoding="utf-8")
    tokens = [
        "function renderStateCard",
        "function renderSearchResultsSixState",
        "function showFeedSkeleton",
        "function bindSixStateRuntime",
        "mydow:v14:feed-loaded",
        "mydow:v14:records-loaded",
        "mydow:v14:kb-folders-loaded",
        "mydow:v14:notifications-loaded",
        "空态来自 /feed",
        "空态来自 /kb/folders",
        "空态来自 /notifications",
        "空态来自 /search",
        "请重试",
        "mydow-state-card",
        "mydow-sixstate-empty-active",
        "mydow-sixstate-loading-active",
    ]
    missing = [token for token in tokens if token not in ext]
    assert not missing, f"biz_v14 ext missing six-state hooks: {missing}"


def test_biz_v14_profile_preferences_are_real_controls():
    """§18.1 — profile preference controls must be real API-backed UI."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    ext = (MYDOW_DIR / "biz_v14" / "bridge_v14_ext.js").read_text(encoding="utf-8")
    bridge_tokens = [
        '"自动保存设置已更新": "auto_save"',
        'sw.setAttribute("aria-pressed", String(next))',
        'sw.setAttribute("aria-label", next ? "自动保存已开启" : "自动保存已关闭")',
    ]
    ext_tokens = [
        "function bindProfilePreferencesV18",
        "function hydrateProfilePreferences",
        'base.apiFetch("/me/preferences", { method: "PATCH", body: { [key]: value } })',
        'base.apiFetch("/me/preferences", { method: "PATCH", body: { theme } })',
        "PROFILE_PREF_OPTIONS",
        "mydow-choice-popover",
        "default_ai_model",
        "default_input_mode",
        "function applyProfilePreferencesV18",
        "function applyThemePreferenceV18",
        "function applyLanguagePreferenceV18",
        "function applyDefaultInputModePreferenceV18",
        "document.body.dataset.defaultInputMode",
        "document.documentElement.lang",
    ]
    missing_bridge = [token for token in bridge_tokens if token not in bridge]
    missing_ext = [token for token in ext_tokens if token not in ext]
    assert not missing_bridge, f"biz_v14 bridge missing §18.1 preference tokens: {missing_bridge}"
    assert not missing_ext, f"biz_v14 ext missing §18.1 preference tokens: {missing_ext}"


def test_biz_v14_dark_mode_uses_darkreader_library():
    """Dark mode uses the mature Dark Reader engine instead of hand recoloring only."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    vendor = MYDOW_DIR / "biz_v14" / "vendor" / "darkreader.min.js"
    assert vendor.exists(), "Dark Reader vendor bundle missing"
    tokens = [
        "DARK_READER_THEME_V21",
        "DARK_READER_FIXES_V21",
        "darkReader.enable(DARK_READER_THEME_V21, DARK_READER_FIXES_V21)",
        "darkReader.disable()",
        "mydow-darkreader-active",
        "setFetchMethod(window.fetch.bind(window))",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Dark Reader integration tokens: {missing}"


def test_biz_v14_account_security_uses_real_api_state():
    """Section 18.12: account security buttons must read/write real endpoints."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function renderAccountSecurityV18",
        "function hydrateAccountSecurityV18",
        "bindAccountSecurityHydrateV18();",
        'apiFetch("/me/security")',
        'apiFetch("/me/security/email-verification"',
        'apiFetch("/me/security/devices/refresh"',
        'sw.setAttribute("aria-label", next ? "二步验证已开启" : "二步验证已关闭")',
        "email_verification_requested_at",
        "last_security_refresh_at",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing account security tokens: {missing}"
    forbidden = [
        "邮箱验证 V1：链接已记录",
        "登录设备 V1：当前会话已刷新",
    ]
    stale = [token for token in forbidden if token in bridge]
    assert not stale, f"biz_v14 bridge still has fake account security toasts: {stale}"


def test_biz_v14_latest_no_silent_fake_success_regressions():
    """Latest browser findings: key buttons must use real endpoints or hard fail."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    required = [
        'await openKbDocumentEditorV20(docId)',
        'data.fetch_status === "failed"',
        'data.fetch_error',
        'isVisible(document.querySelector(".ai-main, .ai-workspace-canvas"))',
        'apiFetch("/billing/overview")',
        'apiFetch("/billing/subscription"',
        'permission_acl_mode: "owner_only"',
        'title: "数字花园节点: " + subject.title.slice(0, 48)',
    ]
    missing = [token for token in required if token not in bridge]
    assert not missing, f"biz_v14 bridge missing latest real-linkage tokens: {missing}"
    forbidden = [
        "后端待支持永久删除",
        "付费门户在 V2 上线",
        "权限矩阵编辑器在 V2 上线",
    ]
    stale = [token for token in forbidden if token in bridge]
    assert not stale, f"biz_v14 bridge still has fake-success copy: {stale}"


def test_biz_v14_ai_stream_refreshes_session_before_send():
    """Section 18.2: AI streaming send recovers from stale browser tokens."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function ensureAiConversationVisibleV18",
        'page.classList.add("ai-open", "ai-chat-open")',
        'msg.style.opacity = "1"',
        "async function fetchAiStreamWithSession",
        "await ensureSession();",
        "if (resp.status === 401)",
        'setToken("");',
        "resp = await fetch(API_BASE + path, buildInit())",
        "const streamPath = `/ai/conversations/${conversationId}/messages/stream`",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.2 stream auth recovery: {missing}"


def test_biz_v14_ai_context_picker_is_searchable_and_traceable():
    """Section 18.3: @ context picker searches real KB data and stores sources."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function injectAiContextPickerStylesV18",
        "data-ai-context-search",
        "role=\"searchbox\"",
        "apiFetch(docPath)",
        "apiFetch(folderPath)",
        "context-source-v18",
        "sources.push({ type: \"folder\", label: title, ref: id })",
        "sources.push({ type: \"doc\", label: title, ref: id })",
        "contextFoldersCache",
        "sources: Array.isArray(V14.contextScope.sources)",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.3 context picker tokens: {missing}"


def test_biz_v14_ai_personalize_dropdowns_are_modern_and_persisted():
    """Section 18.4: AI personalization dropdowns are modern and API-backed."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function bindAiPersonalizeModernControlsV18",
        "function hydrateAiPersonalizeControlsV18",
        "AI_PERSONALIZE_SELECTS_V18",
        "v18-ai-select-button",
        "v18-ai-select-panel",
        "payload.ai_response_style",
        "payload.ai_detail_level",
        "payload.cite_knowledge_by_default",
        'apiFetch("/me/preferences", { method: "PATCH", body: payload })',
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.4 AI personalize tokens: {missing}"


def test_biz_v14_doc_editor_autosaves_without_black_focus_frame():
    """Section 18.5: document editor hydrates real docs and autosaves edits."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function injectDocEditorPolishCssV18",
        ".doc-body[contenteditable=\"true\"]",
        "outline: none !important",
        "function hydrateDocEditorFromDocumentV18",
        "function saveDocEditorNowV18",
        "function bindDocEditorHydrateAndAutosaveV18",
        'apiFetch("/kb/documents/" + encodeURIComponent(id))',
        'apiFetch("/kb/documents/" + encodeURIComponent(docId),',
        "method: \"PATCH\"",
        "scheduleDocEditorSaveV18",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.5 doc editor tokens: {missing}"


def test_biz_v14_doc_editor_renders_markdown_preview():
    """Section 18.30: KB documents render Markdown while preserving raw edit mode."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "src" / "agent_os" / "server" / "app.py").read_text(encoding="utf-8")
    tokens = [
        "vendor/markdown-it.min.js",
        "function markdownRendererV18",
        "window.markdownit",
        "markdown-rendered-v18",
        "function renderDocBodyPreviewV18",
        "function enterDocMarkdownEditModeV18",
        "data-v18-md-toggle",
        "function openKbDocumentFromHashV18",
        "function bindKbDocHashRouteV18",
        "#/kb/doc/",
        "编辑 Markdown",
        "预览 Markdown",
    ]
    haystack = bridge + "\n" + app
    missing = [token for token in tokens if token not in haystack]
    assert not missing, f"biz_v14 Markdown document preview wiring missing: {missing}"


def test_biz_v14_long_running_ai_and_skill_errors_are_visible():
    """Section 18.30: AI/Skill runs expose timeout/provider failures instead of spinning forever."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    service = (PROJECT_ROOT / "src" / "agent_os" / "jobs" / "service.py").read_text(encoding="utf-8")
    tokens = [
        "CLIENT_POLL_TIMEOUT",
        "已等待 ${tick.elapsed}s",
        "_pollSkillRunUntilDone(runId, jobId, 60",
        "AI_STREAM_TIMEOUT",
        "AI 请求超过 90 秒未返回",
        "streamHadError = true",
        "AI_PROVIDER_TIMEOUT",
        "asyncio.wait_for",
        "AGENTOS_SKILL_LLM_TIMEOUT_SECONDS",
    ]
    haystack = bridge + "\n" + service
    missing = [token for token in tokens if token not in haystack]
    assert not missing, f"v14 AI/Skill timeout visibility tokens missing: {missing}"


def test_biz_v14_ai_context_picker_has_draft_selection_and_cancel():
    """Section 18.30: context picker keeps selected state visible and cancellable across searches."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "aiContextDraft",
        "function seedAiContextDraftV18",
        "function aiContextDraftToggleV18",
        "function syncAiContextRowStateV18",
        "取消选择",
        "aria-pressed",
        "page_size=100",
        "documentIds = (V14.aiContextDraft.document_ids || [])",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"v14 AI context picker selection/cancel tokens missing: {missing}"


def test_biz_v14_uses_deepseek_v4_flash_only_for_ai_model_surface():
    """Section 18.30: remove GLM/multi-model leakage and pin v14 to DeepSeek v4 flash."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    ext = (MYDOW_DIR / "biz_v14" / "bridge_v14_ext.js").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "src" / "agent_os" / "ai" / "router.py").read_text(encoding="utf-8")
    tokens = [
        "DEEPSEEK_V4_FLASH_MODEL_V18",
        "body.model = DEEPSEEK_V4_FLASH_MODEL_V18",
        "function bindDeepSeekModelEnforcementV18",
        "def _format_llm_provider_error",
        "DeepSeek v4 flash 调用失败",
        '"id": "deepseek-v4-flash"',
        '"default": True',
        '{ value: "deepseek-v4-flash", label: "DeepSeek V4 Flash"',
    ]
    haystack = bridge + "\n" + ext + "\n" + router
    missing = [token for token in tokens if token not in haystack]
    assert not missing, f"v14 DeepSeek-only model surface missing: {missing}"
    forbidden = [
        '"id": "opus-4.6"',
        '"id": "gemini-2.5-flash"',
        '"id": "gpt-5.2"',
        'value: "glm-4-flash"',
        "GLM-4 Flash",
    ]
    leaked = [token for token in forbidden if token in haystack]
    assert not leaked, f"v14 still leaks non-DeepSeek model choices: {leaked}"


def test_biz_v14_item_detail_drawer_blocks_static_mock_content():
    """Section 18.31: item detail drawers must wait for real card data, never static prototype content."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function showItemDetailLoadingV18",
        "加载失败时不会展示原型假内容",
        "event.stopImmediatePropagation()",
        "function cardMetaLineV18",
        "真实 AI 摘要",
        "已阻止打开原型假详情",
        "revealItemDetailDrawerV18(payload)",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"v14 item detail drawer real-data guard missing: {missing}"


def test_biz_v14_skill_run_picker_is_searchable_and_modern():
    """Section 18.6: Skill run modal uses a searchable KB document picker."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function injectSkillRunPickerStylesV18",
        "skill-doc-picker-v18",
        "data-v18-skill-doc-search",
        "data-v18-skill-doc-list",
        "skill-doc-option-v18",
        "role=\"searchbox\"",
        "role=\"listbox\"",
        'apiFetch("/kb/documents?page_size=48")',
        "docSel = layer.querySelector(\"select[data-v16-skill-doc-select]\")",
        "document_id: documentId",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.6 skill picker tokens: {missing}"


def test_biz_v14_skills_sidebar_recommendations_do_not_clip_recent_usage():
    """Section 18.7: Skill recommendations collapse cleanly and the side rail scrolls."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "skill-side-rec-list-v18",
        "skill-side-rec-items-v18",
        "extra = document.createElement(\"details\")",
        "extra.open = wasOpen",
        ".page.skills-open .skills-drawer .insight-panel",
        "overflow-y: auto !important",
        "scrollbar-gutter: stable",
        "其他推荐 Skill",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.7 sidebar layout tokens: {missing}"


def test_biz_v14_skill_category_filters_use_real_cached_data_and_url_state():
    """Section 18.8: Skills chips filter/sort the real /skills list."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "V14.allSkills = items.slice()",
        "function applySkillsFilterV18",
        "function syncSkillFilterHashV18",
        "function readSkillFilterFromHashV18",
        "function openSkillsFromHashV18",
        "openSkillsFromHashV18();",
        "skillFilterBlobV18",
        "renderSkillFilterEmptyStateV18",
        "bindSkillsCategoryFilterV40();",
        "mydow:v14:skills-filter",
        "favorite_count",
        "skill-filter-empty-v18",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.8 skill filter tokens: {missing}"


def test_biz_v14_voice_input_saves_real_transcript_as_voice_capture():
    """Section 18.10: voice input no longer uses placeholder-only toasts."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function hydrateVoiceInputModalV18",
        "data-v18-voice-transcript",
        "window.SpeechRecognition || window.webkitSpeechRecognition",
        "function handleVoiceInputModal",
        "type: \"voice\"",
        "apiFetch(\"/capture/text\"",
        "bindVoiceInputModalV18();",
        "handleVoiceInputModal(btn, btn.closest('.surface-layer[data-modal=\"voiceInput\"]'))",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 bridge missing Section 18.10 voice input tokens: {missing}"
    assert "演示环境仍走占位" not in bridge
    assert "语音转写占位" not in bridge


def test_biz_v14_skill_recommendation_scores_are_clamped():
    """§7.31 — personalized Skill scores must render as human percentages."""

    bridge = (MYDOW_DIR / "biz_v14" / "bridge_v14.js").read_text(encoding="utf-8")
    tokens = [
        "function formatSkillRecommendationScoreV17",
        "Math.max(1, Math.min(100, Math.round(pct)))",
        "formatSkillRecommendationScoreV17(rec.recommendation_score)",
        "formatSkillRecommendationScoreV17(it.recommendation_score)",
    ]
    missing = [token for token in tokens if token not in bridge]
    assert not missing, f"biz_v14 skill recommendation score formatter missing: {missing}"
    assert "Math.round(rec.recommendation_score * 100)" not in bridge
