"""§15.33 — v1.4 prototype (`/mydow/biz_v14/`) bridge smoke walk.

Opt-in (``tests/e2e`` is ignored by default ``pytest``)::

    pip install playwright && python -m playwright install chromium
    python -m pytest tests/e2e/test_v14_walk.py -q -p no:cacheprovider

Starts **uvicorn in a subprocess** with a fresh seeded SQLite file so the DB URL
is not poisoned by ``tests/conftest.py`` importing ``agent_os.db.base`` before
this module runs (which would otherwise latch ``DATABASE_URL`` to localhost
Postgres).

Asserts ``MydowBridgeV14`` finishes boot, demo token is stored, capture surface
exists, and there are no console / page / API request failures.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip(
    "playwright.async_api",
    reason="Install playwright + browsers for v14 walk tests",
)


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def v14_server() -> str:
    root = Path(__file__).resolve().parents[2]
    db_path = root / ".tmp" / "e2e_v14_walk.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    src = root / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    env["AGENTOS_DEMO_MODE"] = "on"
    env["AGENTOS_PRD10_WORKER"] = "off"

    subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "seed_prd10.py"),
            "--email",
            "demo@mydow.example",
            "--password",
            "demo123",
            "--reset",
        ],
        cwd=str(root),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "agent_os.server.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        for _ in range(100):
            with contextlib.closing(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ) as sock:
                try:
                    sock.connect(("127.0.0.1", port))
                    break
                except OSError:
                    time.sleep(0.15)
                    if proc.poll() is not None:
                        pytest.fail("uvicorn subprocess exited early")
        else:
            pytest.fail("v14 test server did not accept connections")

        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.asyncio
async def test_v14_bridge_boots_and_core_surfaces(v14_server: str) -> None:
    from playwright.async_api import async_playwright

    cb = str(id(object()))
    errors: list[str] = []
    page_errors: list[str] = []
    failed: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})

            def on_console(msg) -> None:
                if msg.type == "error":
                    errors.append(msg.text)

            page.on("console", on_console)
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            page.on(
                "requestfailed",
                lambda req: failed.append(f"{req.method} {req.url}"),
            )

            await page.goto(
                f"{v14_server}/mydow/biz_v14/?cb={cb}",
                wait_until="domcontentloaded",
            )
            await page.wait_for_function(
                "() => window.MydowBridgeV14 && window.MydowBridgeV14.booted === true",
                timeout=45_000,
            )

            snap = await page.evaluate(
                """() => ({
                  booted: !!(window.MydowBridgeV14 && window.MydowBridgeV14.booted),
                  token: !!(localStorage.getItem('mydow_v14_token') || '').length,
                  hasApiFetchV14: !!(window.MydowBridgeV14 && window.MydowBridgeV14.apiFetchV14),
                  hasCapture: !!document.querySelector('.capture textarea, .capture-box textarea'),
                })"""
            )

            assert snap["booted"] is True, "MydowBridgeV14 must finish boot()"
            assert snap["token"] is True, "demo session must persist mydow_v14_token"
            assert snap["hasApiFetchV14"] is True, "§15.31 apiFetchV14 must be exported"
            assert snap["hasCapture"] is True, "v1.4 home capture surface missing"

            api_failed = [
                f
                for f in failed
                if "/api/v1/" in f
                and "favicon" not in f.lower()
                and ".well-known" not in f.lower()
            ]
            assert not page_errors, f"page errors: {page_errors}"
            assert not errors, f"console errors: {errors}"
            assert (
                len(api_failed) == 0
            ), f"unexpected failed API requests: {api_failed[:8]}"
        finally:
            await browser.close()
