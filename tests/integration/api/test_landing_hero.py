"""PRD10 §10.5 — investor-friendly hero landing page tests.

Asserts:

1. ``GET /`` returns 200 + HTML containing the headline ("把灵感变成
   体系化的知识"), the primary CTA href ``/mydow/biz/`` and the brand
   wordmark ``Mydow``.
2. ``GET /?go=demo`` short-circuits to 307 → ``/mydow/biz/`` so press
   users / Chrome-MCP smoke / docker healthcheck can skip the landing.
3. ``GET /landing/index.html`` is served by the dedicated mount (so
   future asset splits remain reachable as direct deep links).
4. The landing page footer links to the existing PRD10 §11.10 legal
   pages (``/legal/privacy.html`` / ``/legal/terms.html``) and to
   ``/docs`` for the auto-generated OpenAPI surface.

The handler does not touch the database or the auth layer, so we use a
plain ``ASGITransport`` against the full ``agent_os.server.app`` without
the heavy DB / fixture-user setup the other PRD10 suites need.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from agent_os.server.app import app as prd_app


@pytest.mark.asyncio
async def test_root_serves_landing_hero_html() -> None:
    """``GET /`` renders the static landing page, not a redirect."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/html"), content_type

    body = response.text
    # Hero copy (key Chinese tokens that should never silently disappear).
    assert "Mydow" in body
    assert "把灵感变成" in body
    assert "体系化" in body
    assert "开始体验" in body
    # PRD10 §15.34: primary CTA points at v1.4 (post-2026-05-07 user-grade
    # business prototype). Older snapshots may still link to v1.0 biz/.
    assert 'href="/mydow/biz_v14/"' in body or 'href="/mydow/biz/"' in body
    # Module names from PRD10 §2.1 must all be enumerated on the page.
    for module in [
        "灵感采集",
        "知识库",
        "Mydow AI",
        "数字花园",
        "Skills",
        "全局搜索",
        "通知",
    ]:
        assert module in body, module


@pytest.mark.asyncio
async def test_root_with_go_demo_query_short_circuits_to_biz() -> None:
    """``GET /?go=demo`` opts out of the landing and 307s to the demo."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/?go=demo")

    assert response.status_code == 307, response.status_code
    # PRD10 §15.34: prefer v1.4 destination when biz_v14/ bundle is present;
    # gracefully fall back to v1.0 when only the legacy bundle exists.
    location = response.headers.get("location")
    assert location in {"/mydow/biz_v14/", "/mydow/biz/"}, location


@pytest.mark.asyncio
async def test_root_without_query_param_does_not_redirect() -> None:
    """The landing page is the default; the old §15.20 redirect should
    only be reachable via the explicit ``?go=demo`` opt-in."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "location" not in {k.lower() for k in response.headers.keys()}


@pytest.mark.asyncio
async def test_landing_mount_serves_index_directly() -> None:
    """``/landing/`` mount serves the same index.html for forward-compat."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/landing/")

    assert response.status_code == 200
    body = response.text
    # Same hero markers as the root handler.
    assert "Mydow" in body
    assert "开始体验" in body


@pytest.mark.asyncio
async def test_landing_footer_links_to_legal_and_docs() -> None:
    """The landing footer must surface investor-grade compliance links
    (privacy / terms) plus the developer-facing API docs entrypoints."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    body = response.text
    # PRD10 §11.10 — privacy / terms surfaces (my-mcp-15 lane).
    assert 'href="/legal/privacy.html"' in body
    assert 'href="/legal/terms.html"' in body
    # FastAPI auto-OpenAPI surface for developer discovery.
    assert 'href="/docs"' in body
    assert 'href="/openapi.json"' in body
    # SPA fallback (PRD10 §15.20) remains reachable from the footer.
    assert 'href="/mydow/spa/"' in body


@pytest.mark.asyncio
async def test_landing_pricing_card_anchors_match_business_model() -> None:
    """Pricing tease must reflect the README §13.6 commercialisation
    table: a personal Pro card and a featured team card. The team card
    is the ``featured`` variant (badge present) per the design spec."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "个人 Pro" in body
    assert "团队 License" in body
    # Personal price baseline from README: ¥39 / month.
    assert "¥39" in body
    # Team price baseline: ¥199 / seat / month.
    assert "¥199" in body
    # Featured badge marks the team card as primary CTA.
    assert "最受欢迎" in body


@pytest.mark.asyncio
async def test_landing_meta_and_brand_tokens_present() -> None:
    """Meta description / theme color / brand wordmark are all in place
    so social shares + browser themes light up correctly."""

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    body = response.text
    assert "<title>Mydow" in body
    assert 'name="description"' in body
    assert 'name="theme-color"' in body
    # Must NOT inadvertently inline external script/style tags (offline-first).
    # We allow inline `<style>` blocks but no remote `<script src="http...">`.
    assert "<script src=\"http" not in body
    assert "<link rel=\"stylesheet\" href=\"http" not in body
