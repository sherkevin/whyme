#!/usr/bin/env python3
"""Chrome smoke for `/mydow/biz_v14/` with optional CDP port for MCP attach.

Starts Playwright **persistent Chrome** with `--remote-debugging-port` (default
9333). After this script runs while the browser is open, Cursor
`chrome-devtools-mcp` can use `--browserUrl http://127.0.0.1:9333`.

  pip install playwright && python -m playwright install chromium
  python scripts/chrome_cdp_biz_v14_smoke.py

Env: ``BASE_URL`` (default ``http://127.0.0.1:8000``), ``CDP_PORT`` (default ``9333``).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".tmp"
SHOT = TMP / "screenshots"
PROFILE = TMP / "pw-chrome-v14-smoke"


def _wait_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        sys.stderr.write("Install playwright: pip install playwright && python -m playwright install chromium\n")
        return 1

    base = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    cdp_port = int(os.environ.get("CDP_PORT", "9333"))
    PROFILE.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)

    try:
        urllib.request.urlopen(f"{base}/health", timeout=5).read()
    except OSError as exc:
        sys.stderr.write(f"Backend not reachable at {base}: {exc}\n")
        sys.stderr.write("Start uvicorn on 8000 + seed demo first.\n")
        return 2

    url = f"{base}/mydow/biz_v14/"

    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE),
                channel="chrome",
                headless=False,
                args=[
                    f"--remote-debugging-port={cdp_port}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                viewport={"width": 1440, "height": 900},
            )
        except Exception:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE),
                headless=False,
                args=[
                    f"--remote-debugging-port={cdp_port}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                viewport={"width": 1440, "height": 900},
            )

        listening = _wait_port("127.0.0.1", cdp_port, timeout=25.0)
        if listening:
            try:
                meta = urllib.request.urlopen(
                    f"http://127.0.0.1:{cdp_port}/json/version", timeout=3
                ).read().decode("utf-8", "replace")
                j = json.loads(meta)
                print(f"[ok] CDP {j.get('webSocketDebuggerUrl', 'websocket?')}")
            except OSError:
                print(f"[ok] CDP TCP {cdp_port} (version fetch failed)")
        else:
            print(f"[warn] Port {cdp_port} did not listen; skip MCP attach.")

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []

        def _cap_console(msg):  # noqa: ANN001
            if msg.type == "error":
                console_errors.append(msg.text)

        page.on("console", _cap_console)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        page.goto(url, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(2000)

        booted = page.evaluate(
            "() => !!(window.MydowBridgeV14 && window.MydowBridgeV14.booted)",
        )
        token = page.evaluate("() => window.localStorage.getItem('mydow_v14_token') || ''")
        page.screenshot(path=str(SHOT / "cdp_biz_v14_boot.png"))

        # Best-effort: open AI workspace from sidebar if link exists.
        for sel in ('a[href*="#"][href*="ai"]', "[data-route='ai']", "text=Mydow AI"):
            link = page.locator(sel).first
            try:
                if link.count() > 0 and link.is_visible(timeout=1200):
                    link.click(timeout=8000)
                    page.wait_for_timeout(1200)
                    break
            except Exception:
                continue
        page.screenshot(path=str(SHOT / "cdp_biz_v14_ai.png"))

        ok = booted and not console_errors and not page_errors
        print("booted=", booted, "token_bytes~=", len(token))
        print("console_errors=", len(console_errors), "page_errors=", len(page_errors))
        for e in (console_errors + page_errors)[:15]:
            print(" ", e)

        ctx.close()
        return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
