"""Browser-level smoke tests for the deployed Mydow Web bundle.

These are intentionally light: they rely on Playwright when it is
installed locally, and skip otherwise. This keeps the repo's default
``pytest`` run offline-friendly while giving CI / engineers an opt-in
"is the bundle actually clickable" check via::

    python -m pip install playwright
    python -m playwright install chromium
    python -m pytest tests/e2e/test_mydow_browser.py -q

The fixtures spin up the canonical FastAPI app on a free port, point
the browser at ``/mydow/``, and assert the high-intent DOM hooks render
and bind to the expected PRD10 paths via ``window.MydowAPI``.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import threading

import pytest

playwright = pytest.importorskip(
    "playwright.async_api",
    reason="Install playwright + browsers to run Mydow browser smoke tests",
)


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def server() -> str:
    """Start ``agent_os.server.app:app`` on a private port."""

    import os
    from pathlib import Path

    import uvicorn

    # SPA boots with ``tryDemoAutoLogin()`` when demo mode is enabled; otherwise
    # the home capture surface never mounts and legacy selectors fail.
    os.environ["AGENTOS_DEMO_MODE"] = "on"
    db_path = Path(__file__).resolve().parents[2] / ".tmp" / "e2e_mydow_browser.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.resolve().as_posix()}"

    from agent_os.server.app import app

    port = _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="asyncio",
        lifespan="on",
    )
    server_instance = uvicorn.Server(config)

    def _serve() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server_instance.serve())
        finally:
            loop.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    # Wait for the server to come up.
    for _ in range(50):
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            try:
                sock.connect(("127.0.0.1", port))
                break
            except OSError:
                import time

                time.sleep(0.1)
    else:
        pytest.fail("Mydow web server did not start in time")

    yield f"http://127.0.0.1:{port}"

    server_instance.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
async def test_mydow_browser_renders_and_exposes_api(server: str) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(f"{server}/mydow/", wait_until="networkidle")

            # Native ESM shell: demo auto-login hides ``#auth-overlay`` and mounts home.
            ta = page.locator(".capture-box textarea")
            await ta.wait_for(state="attached", timeout=20000)
            await ta.scroll_into_view_if_needed()
            assert await page.evaluate(
                "() => document.getElementById('auth-overlay')?.hasAttribute('hidden')"
            ), (
                "auth overlay must remain hidden after demo login "
                "(see style.css #auth-overlay[hidden])"
            )


            # MydowAPI must expose the auth + capture clients.
            api_keys = await page.evaluate(
                "() => Object.keys(window.MydowAPI || {})"
            )
            for key in ("auth", "capture", "ai", "kb", "skills", "garden"):
                assert key in api_keys, f"window.MydowAPI missing '{key}'"

            # High-intent DOM hooks on the SPA home shell (see ``static/mydow/app.js``).
            for selector in (
                ".capture-box textarea",
                ".capture-actions .btn-primary",
                'button[title="网页剪藏"]',
                '[data-nav="kb"]',
            ):
                assert await page.query_selector(selector) is not None, (
                    f"DOM hook missing: {selector}"
                )
        finally:
            await browser.close()
