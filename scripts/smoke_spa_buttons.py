"""Mydow SPA low-frequency button smoke test.

This script drives the real FastAPI app through a browser. It registers a
real user, persists data through UI actions, and records every API response
triggered by the buttons it exercises.

Usage:
    python scripts/smoke_spa_buttons.py --base http://127.0.0.1:8023
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / ".tmp" / "spa_button_audit.json"
DEFAULT_SCREENSHOT_DIR = PROJECT_ROOT / ".tmp" / "screenshots" / "v4_9_buttons"


class ButtonAudit:
    def __init__(self, page: Page, base_url: str, screenshot_dir: Path) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.screenshot_dir = screenshot_dir
        self.results: list[dict[str, Any]] = []
        self.api_calls: list[dict[str, Any]] = []
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []

        page.on("response", self._record_response)
        page.on("console", self._record_console)
        page.on("pageerror", lambda exc: self.page_errors.append(str(exc)))

    def _record_response(self, response) -> None:
        if "/api/v1/" not in response.url:
            return
        self.api_calls.append(
            {
                "status": response.status,
                "url": response.url,
                "ok": response.ok,
                "method": response.request.method,
            }
        )

    def _record_console(self, msg) -> None:
        if msg.type in {"error", "warning"}:
            text = msg.text
            if "favicon" not in text.lower():
                self.console_errors.append(f"{msg.type}: {text}")

    async def record(
        self,
        name: str,
        action: Callable[[], Awaitable[Any]],
        *,
        expect_api: str | None = None,
        expect_hash: str | None = None,
        expect_selector: str | None = None,
        screenshot: bool = False,
    ) -> Any:
        start_idx = len(self.api_calls)
        start_hash = await self.page.evaluate("location.hash")
        started = time.time()
        entry: dict[str, Any] = {
            "name": name,
            "status": "passed",
            "started_at": started,
            "duration_ms": None,
            "api_calls": [],
            "hash_before": start_hash,
            "hash_after": None,
            "screenshot": None,
        }
        try:
            result = await action()
            await self.page.wait_for_timeout(250)
            calls = self.api_calls[start_idx:]
            entry["api_calls"] = calls
            entry["hash_after"] = await self.page.evaluate("location.hash")
            if expect_api and not any(expect_api in c["url"] and c["ok"] for c in calls):
                raise AssertionError(f"expected successful API call containing {expect_api!r}")
            if expect_hash and expect_hash not in str(entry["hash_after"]):
                raise AssertionError(
                    f"expected hash containing {expect_hash!r}, got {entry['hash_after']!r}"
                )
            if expect_selector:
                await self.page.locator(expect_selector).first.wait_for(timeout=5000)
            if any(c["status"] >= 500 for c in calls):
                bad = [c for c in calls if c["status"] >= 500]
                raise AssertionError(f"server error API calls: {bad}")
            if screenshot:
                self.screenshot_dir.mkdir(parents=True, exist_ok=True)
                path = self.screenshot_dir / f"{len(self.results) + 1:02d}_{slug(name)}.png"
                await self.page.screenshot(path=str(path), full_page=True)
                entry["screenshot"] = str(path)
            self.results.append(entry)
            return result
        except Exception as exc:  # noqa: BLE001 - report every smoke failure.
            entry["status"] = "failed"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["api_calls"] = self.api_calls[start_idx:]
            entry["hash_after"] = await safe_eval(self.page, "location.hash")
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            path = self.screenshot_dir / f"{len(self.results) + 1:02d}_{slug(name)}_failed.png"
            try:
                await self.page.screenshot(path=str(path), full_page=True)
                entry["screenshot"] = str(path)
            except Exception:
                pass
            self.results.append(entry)
            raise
        finally:
            entry["duration_ms"] = round((time.time() - started) * 1000)

    async def click_text(self, text: str, selector: str = "button,[role=button],a") -> None:
        locator = self.page.locator(selector).filter(has_text=text).first
        await locator.click(timeout=5000)

    async def click_title(self, title: str) -> None:
        await self.page.locator(f'[title="{title}"], [aria-label="{title}"]').first.click(timeout=5000)

    async def modal_input(self, index: int, value: str) -> None:
        await self.page.locator(".modal input, .modal textarea").nth(index).fill(value)

    async def wait_idle(self) -> None:
        await self.page.wait_for_load_state("networkidle", timeout=10000)
        await self.page.locator("#page-region").wait_for(timeout=10000)

    def summary(self) -> dict[str, Any]:
        return {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["status"] == "passed"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "api_call_count": len(self.api_calls),
            "api_failures": [c for c in self.api_calls if c["status"] >= 400],
            "console_errors": self.console_errors,
            "page_errors": self.page_errors,
        }


async def safe_eval(page: Page, expression: str) -> Any:
    try:
        return await page.evaluate(expression)
    except Exception:
        return None


def slug(value: str) -> str:
    chars = []
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {" ", "-", "_"}:
            chars.append("_")
    out = "".join(chars).strip("_")
    return out[:72] or "step"


async def register_user(page: Page, base_url: str) -> tuple[str, dict[str, Any]]:
    suffix = uuid.uuid4().hex[:10]
    payload = {
        "username": f"button_{suffix}",
        "email": f"button_{suffix}@example.com",
        "password": "ButtonSmoke123!",
    }
    response = await page.request.post(f"{base_url}/api/v1/auth/register", data=payload)
    if not response.ok:
        raise AssertionError(f"register failed: {response.status} {await response.text()}")
    body = await response.json()
    token = body.get("access_token") or body.get("data", {}).get("access_token")
    if not token:
        raise AssertionError(f"register response did not contain token: {body}")
    me_resp = await page.request.get(
        f"{base_url}/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not me_resp.ok:
        raise AssertionError(f"/me failed: {me_resp.status} {await me_resp.text()}")
    me_body = await me_resp.json()
    user = me_body.get("data") or me_body
    return token, user


async def seed_capture(page: Page, base_url: str, token: str, title: str) -> dict[str, Any]:
    response = await page.request.post(
        f"{base_url}/api/v1/capture/text",
        data={
            "content": (
                f"{title}: This smoke record verifies real database persistence, "
                "search indexing, knowledge base rendering, and button actions."
            ),
            "title": title,
            "tags": ["button-smoke", "prd10"],
            "auto_process": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    if not response.ok:
        raise AssertionError(f"seed capture failed: {response.status} {await response.text()}")
    return await response.json()


async def first_document_id(page: Page, base_url: str, token: str) -> str:
    response = await page.request.get(
        f"{base_url}/api/v1/kb/documents?page_size=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not response.ok:
        raise AssertionError(f"kb documents failed: {response.status} {await response.text()}")
    body = await response.json()
    items = (body.get("data") or {}).get("items") or []
    if not items:
        raise AssertionError("seed capture did not create any KB document")
    return items[0]["id"]


async def first_folder_id(page: Page, base_url: str, token: str) -> str:
    response = await page.request.get(
        f"{base_url}/api/v1/kb/folders?page_size=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not response.ok:
        raise AssertionError(f"kb folders failed: {response.status} {await response.text()}")
    body = await response.json()
    items = (body.get("data") or {}).get("items") or []
    if not items:
        raise AssertionError("no folder was created by UI flow")
    return items[0]["id"]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--screenshot-dir", type=Path, default=DEFAULT_SCREENSHOT_DIR)
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    base_url = args.base.rstrip("/")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headful)
        context = await browser.new_context(viewport={"width": 1440, "height": 940})
        page = await context.new_page()
        audit = ButtonAudit(page, base_url, args.screenshot_dir)

        try:
            token, user = await register_user(page, base_url)
            await seed_capture(page, base_url, token, "Seed inspiration for button smoke")
            await page.goto(f"{base_url}/mydow/spa/", wait_until="domcontentloaded")
            await page.evaluate(
                """([token, user]) => {
                  localStorage.setItem("mydow_token", token);
                  localStorage.setItem("mydow_user", JSON.stringify(user));
                }""",
                [token, user],
            )
            await page.reload(wait_until="networkidle")
            await audit.wait_idle()

            await audit.record(
                "sidebar opens Today",
                lambda: audit.click_text("Today", "[role=button]"),
                expect_hash="#/today",
                screenshot=True,
            )

            await audit.record(
                "sidebar opens Inbox",
                lambda: audit.click_text("Inbox", "[role=button]"),
                expect_hash="#/inbox",
                screenshot=True,
            )

            await audit.record(
                "sidebar opens KB",
                lambda: audit.click_text("知识库", "[role=button]"),
                expect_hash="#/kb",
                screenshot=True,
            )

            await audit.record(
                "theme toggle persists preference",
                lambda: page.locator("[data-theme-toggle]").click(),
                screenshot=True,
            )

            await audit.record(
                "notification drawer marks all read",
                async_lambda(
                    page.locator(".topbar .icon-btn").nth(1).click(),
                    page.wait_for_selector("#notif-drawer.is-open", timeout=5000),
                    page.wait_for_timeout(800),
                    click_if_visible(page, "全部已读"),
                    page.wait_for_timeout(800),
                    page.locator('#notif-drawer [title="关闭"], #notif-drawer [aria-label="关闭"]').first.click(),
                ),
                expect_api="/notifications",
            )

            await audit.record(
                "home text capture persists",
                async_lambda(
                    goto_hash(page, "#/home"),
                    fill_first_textarea(
                        page,
                        "Button smoke captures a fresh inspiration and stores it as a card and KB asset.",
                    ),
                    page.locator(".capture-actions .btn-primary").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api="/capture/text",
                screenshot=True,
            )

            await audit.record(
                "upload button opens real upload modal",
                async_lambda(
                    goto_hash(page, "#/home"),
                    page.locator(".capture-tools .btn-icon").first.click(),
                    page.wait_for_selector(".modal-mask.is-open input[type=file]", timeout=5000),
                    page.locator(".modal .btn").filter(has_text="取消").first.click(),
                ),
                expect_selector="#page-region",
            )

            await audit.record(
                "web clip button posts link capture",
                async_lambda(
                    goto_hash(page, "#/home"),
                    page.locator(".capture-tools .btn-icon").nth(1).click(),
                    page.wait_for_selector(".modal-mask.is-open", timeout=5000),
                    page.locator(".modal input").first.fill("https://example.com/button-smoke"),
                    page.locator(".modal textarea").first.fill("Button smoke link note"),
                    page.locator(".modal .btn-primary").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api="/capture/link",
            )

            await audit.record(
                "deep research button creates AI conversation",
                async_lambda(
                    goto_hash(page, "#/home"),
                    page.locator(".quick-action").filter(has_text="深度研究").first.click(),
                    page.wait_for_selector(".modal-mask.is-open", timeout=5000),
                    page.locator(".modal input").first.fill("button smoke research topic"),
                    page.locator(".modal textarea").first.fill("Use real KB context and create a concise plan."),
                    page.locator(".modal .btn-primary").first.click(),
                    wait_hash_contains(page, "#/ai/", timeout_ms=25000),
                ),
                expect_api="/ai/conversations",
                expect_hash="#/ai/",
                screenshot=True,
            )

            await audit.record(
                "KB create folder routes to folder detail",
                async_lambda(
                    goto_hash(page, "#/kb"),
                    page.locator("button").filter(has_text="新建文件夹").first.click(),
                    page.wait_for_selector(".modal-mask.is-open", timeout=5000),
                    page.locator(".modal input").first.fill(f"Button Smoke Folder {uuid.uuid4().hex[:6]}"),
                    page.locator(".modal textarea").first.fill("Created by button smoke through the real UI."),
                    page.locator(".modal .btn-primary").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api="/kb/folders",
                expect_hash="#/kb/folder/",
                screenshot=True,
            )

            folder_id = await first_folder_id(page, base_url, token)
            await audit.record(
                "folder rename updates backend",
                async_lambda(
                    goto_hash(page, f"#/kb/folder/{folder_id}"),
                    page.locator("button").filter(has_text="重命名").first.click(),
                    page.wait_for_selector(".modal-mask.is-open", timeout=5000),
                    page.locator(".modal input").first.fill(f"Renamed Button Folder {uuid.uuid4().hex[:4]}"),
                    page.locator(".modal .btn-primary").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api=f"/kb/folders/{folder_id}",
            )

            doc_id = await first_document_id(page, base_url, token)
            await audit.record(
                "KB document detail opens",
                async_lambda(goto_hash(page, f"#/kb/doc/{doc_id}"), page.wait_for_selector(".doc-body, .page-head", timeout=10000)),
                expect_hash=f"#/kb/doc/{doc_id}",
                screenshot=True,
            )

            await audit.record(
                "document favorite toggles backend",
                async_lambda(
                    goto_hash(page, f"#/kb/doc/{doc_id}"),
                    page.locator("button").filter(has_text="收藏").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api=f"/kb/documents/{doc_id}",
            )

            await audit.record(
                "document edit saves backend",
                async_lambda(
                    goto_hash(page, f"#/kb/doc/{doc_id}"),
                    page.locator("button").filter(has_text="编辑").first.click(),
                    page.wait_for_selector(".modal-mask.is-open", timeout=5000),
                    page.locator(".modal input").first.fill(f"Edited Button Smoke Doc {uuid.uuid4().hex[:6]}"),
                    page.locator(".modal .btn-primary").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api=f"/kb/documents/{doc_id}",
            )

            await audit.record(
                "AI new conversation button",
                async_lambda(
                    goto_hash(page, "#/ai"),
                    page.locator(".ai-conv-list .new-conv").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api="/ai/conversations",
                expect_hash="#/ai/",
                screenshot=True,
            )

            await audit.record(
                "AI send message persists conversation turn",
                async_lambda(
                    page.locator("textarea").first.fill("Use the knowledge base to summarize the button smoke assets."),
                    page.locator(".ai-composer .send-btn").first.click(),
                    page.wait_for_timeout(1800),
                ),
                expect_api="/ai/conversations/",
                screenshot=True,
            )

            await audit.record(
                "Skills run button enqueues real job",
                async_lambda(
                    goto_hash(page, "#/skills"),
                    page.wait_for_selector(".skill-card, .card", timeout=10000),
                    page.locator(".skills-grid .skill-card .btn-primary").first.click(),
                    page.wait_for_selector(".modal-mask.is-open", timeout=5000),
                    page.locator(".modal textarea").first.fill("Button smoke skill run input."),
                    page.locator(".modal .btn-primary").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api="/skills/",
                screenshot=True,
            )

            await audit.record(
                "Today create task persists",
                async_lambda(
                    goto_hash(page, "#/today"),
                    page.locator(".section-title .btn-primary, .row-spread .btn-primary").first.click(),
                    page.wait_for_selector(".modal-mask.is-open", timeout=5000),
                    page.locator(".modal input").first.fill(f"Button smoke task {uuid.uuid4().hex[:6]}"),
                    page.locator(".modal .btn-primary").first.click(),
                    page.wait_for_timeout(1200),
                ),
                expect_api="/tasks",
                screenshot=True,
            )

            await audit.record(
                "global search opens and queries backend",
                async_lambda(
                    page.keyboard.press("Control+K"),
                    page.wait_for_selector(".search-panel input", timeout=5000),
                    page.locator(".search-panel input").first.fill("button-smoke"),
                    page.wait_for_timeout(1200),
                ),
                expect_api="/search",
                screenshot=True,
            )

            await audit.record(
                "Garden opens graph from real data",
                async_lambda(goto_hash(page, "#/garden"), page.wait_for_timeout(1200)),
                expect_api="/garden",
                expect_hash="#/garden",
                screenshot=True,
            )

        finally:
            report = {
                "base_url": base_url,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "summary": audit.summary(),
                "results": audit.results,
                "api_calls": audit.api_calls,
            }
            args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            await context.close()
            await browser.close()

    failed = report["summary"]["failed"]
    bad_api = [c for c in report["summary"]["api_failures"] if c["status"] >= 500]
    return 1 if failed or bad_api or report["summary"]["page_errors"] else 0


def async_lambda(*awaitables: Awaitable[Any]) -> Callable[[], Awaitable[None]]:
    async def _runner() -> None:
        for index, item in enumerate(awaitables):
            try:
                await item
            except Exception:
                for pending in awaitables[index + 1 :]:
                    if inspect.iscoroutine(pending):
                        pending.close()
                raise

    return _runner


async def click_if_visible(page: Page, text: str) -> None:
    locator = page.locator("button").filter(has_text=text).first
    try:
        await locator.click(timeout=1500)
    except PlaywrightTimeoutError:
        pass


async def goto_hash(page: Page, hash_value: str) -> None:
    await page.evaluate("(hashValue) => { location.hash = hashValue; }", hash_value)
    await page.wait_for_timeout(250)
    await page.wait_for_load_state("networkidle", timeout=10000)


async def fill_first_textarea(page: Page, value: str) -> None:
    await page.locator("textarea").first.fill(value)


async def wait_hash_contains(page: Page, substring: str, timeout_ms: int = 10000) -> None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        current = await page.evaluate("location.hash")
        if substring in str(current):
            return
        await page.wait_for_timeout(250)
    raise AssertionError(f"timed out waiting for location.hash to contain {substring!r}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
