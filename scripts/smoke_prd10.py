"""End-to-end smoke test for the PRD10 product-data backend.

Boots the real FastAPI app via ``uvicorn`` (in a background thread), registers
a fresh user, and walks through the V1 critical-path scenarios:

    1. Auth: POST /api/v1/auth/register   → access_token
    2. Capture: POST /api/v1/capture/text → InboxItem + Job(completed)
    3. Today:   GET  /api/v1/today        → stats / quick_actions / tasks
    4. Feed:    GET  /api/v1/feed         → items derived from capture
    5. Upload:  POST /api/v1/uploads/presign
                PUT  /api/v1/uploads/local/{upload_id}  (raw bytes)
                POST /api/v1/capture/file/commit
                GET  /api/v1/uploads/local/{upload_id}/raw  (round-trip)
    6. KB:      GET  /api/v1/kb/overview / GET /api/v1/kb/folders
    7. Inbox:   GET  /api/v1/inbox / PATCH /api/v1/inbox/{id}
    8. Notifications: unread-count / list / read-all
    9. Notifications SSE: GET /api/v1/notifications/stream until ``event: ready``

Each step writes a ``{step, status_code, success}`` row plus a small payload
sample to ``tests/integration/api/prd10/smoke_run.json`` so a human (or
follow-up tooling) can review the run after the fact.

Usage::

    python scripts/smoke_prd10.py
    python scripts/smoke_prd10.py --keep   # don't drop the SQLite db at end
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, *, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.25)
    raise TimeoutError(f"server did not come up on {host}:{port} within {timeout}s")


def _start_server(port: int) -> threading.Thread:
    """Boot uvicorn in a daemon thread so the script stays foreground."""

    import uvicorn  # imported lazily to avoid cost when --help is run

    from agent_os.server.app import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    def _run():
        # Each thread needs its own asyncio loop.
        asyncio.run(server.serve())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


async def _smoke(base: str, output_path: Path) -> int:
    import httpx

    timeline: list[dict] = []

    def _record(step: str, response, *, sample_keys: list[str] | None = None):
        try:
            body = response.json()
        except Exception:
            body = {"_non_json": response.text[:500]}
        sample = body
        if isinstance(body, dict) and sample_keys:
            sample = {k: body.get(k) for k in sample_keys}
        elif isinstance(body, dict) and "data" in body:
            data = body.get("data")
            if isinstance(data, dict):
                sample = {
                    "success": body.get("success"),
                    "request_id": body.get("request_id"),
                    "data_keys": sorted(data.keys()),
                }
            elif isinstance(data, list):
                sample = {
                    "success": body.get("success"),
                    "data_len": len(data),
                }
        timeline.append(
            {
                "step": step,
                "status": response.status_code,
                "ok": 200 <= response.status_code < 300,
                "sample": sample,
            }
        )

    failures: list[str] = []
    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        # 1. Register
        email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
        username = f"smoke_{uuid.uuid4().hex[:8]}"
        password = "smoke-pass-1234"
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": password},
        )
        if register.status_code >= 300:
            try:
                err_body = register.json()
            except Exception:
                err_body = {"_text": register.text[:500]}
            timeline.append(
                {
                    "step": "auth.register",
                    "status": register.status_code,
                    "ok": False,
                    "sample": err_body,
                }
            )
            failures.append("register failed")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps({"timeline": timeline, "failures": failures}, indent=2, ensure_ascii=False))
            return 1
        _record("auth.register", register, sample_keys=["access_token", "token_type"])

        access_token = register.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Capture text
        capture = await client.post(
            "/api/v1/capture/text",
            json={
                "content": "Smoke 测试: 想法 - 把首页内容流的卡片做成可拖拽的灵感板。",
                "title": "灵感板想法",
                "tags": ["smoke", "首页"],
            },
            headers=auth_headers,
        )
        _record("capture.text", capture)
        if capture.status_code >= 300:
            failures.append("capture text failed")

        # 3. Today
        today = await client.get("/api/v1/today", headers=auth_headers)
        _record("today.get", today)
        if today.status_code >= 300:
            failures.append("today failed")

        # 4. Feed
        feed = await client.get("/api/v1/feed", headers=auth_headers)
        _record("feed.get", feed)
        if feed.status_code >= 300:
            failures.append("feed failed")

        # 5. Upload + commit + raw
        presign = await client.post(
            "/api/v1/uploads/presign",
            json={
                "filename": "smoke.txt",
                "mime_type": "text/plain",
                "size_bytes": 19,
            },
            headers=auth_headers,
        )
        _record("uploads.presign", presign)
        upload_id = presign.json()["data"]["upload_id"]

        put = await client.put(
            f"/api/v1/uploads/local/{upload_id}",
            content=b"smoke upload bytes!",
            headers={
                **auth_headers,
                "X-Filename": "smoke.txt",
                "Content-Type": "text/plain",
            },
        )
        _record("uploads.put_bytes", put)

        commit = await client.post(
            "/api/v1/capture/file/commit",
            json={
                "upload_id": upload_id,
                "filename": "smoke.txt",
                "mime_type": "text/plain",
                "size_bytes": 19,
            },
            headers=auth_headers,
        )
        _record("capture.file.commit", commit)

        raw = await client.get(
            f"/api/v1/uploads/local/{upload_id}/raw", headers=auth_headers
        )
        timeline.append(
            {
                "step": "uploads.raw",
                "status": raw.status_code,
                "ok": raw.status_code == 200 and raw.content == b"smoke upload bytes!",
                "sample": {"bytes_len": len(raw.content)},
            }
        )

        # 6. KB
        overview = await client.get("/api/v1/kb/overview", headers=auth_headers)
        _record("kb.overview", overview)
        folders = await client.get("/api/v1/kb/folders", headers=auth_headers)
        _record("kb.folders", folders)
        documents = await client.get("/api/v1/kb/documents", headers=auth_headers)
        _record("kb.documents", documents)

        # 7. Inbox
        inbox_list = await client.get("/api/v1/inbox", headers=auth_headers)
        _record("inbox.list", inbox_list)
        items = inbox_list.json()["data"]["items"]
        if items:
            target = items[0]["id"]
            patch = await client.patch(
                f"/api/v1/inbox/{target}",
                json={"status": "archived", "tags": ["smoke", "archived"]},
                headers=auth_headers,
            )
            _record("inbox.patch", patch)

        # 8. Notifications
        unread = await client.get(
            "/api/v1/notifications/unread-count", headers=auth_headers
        )
        _record("notifications.unread_count", unread)
        notif_list = await client.get(
            "/api/v1/notifications", headers=auth_headers
        )
        _record("notifications.list", notif_list)
        read_all = await client.post(
            "/api/v1/notifications/read-all", headers=auth_headers
        )
        _record("notifications.read_all", read_all)

        # 9. Notifications SSE — exercises StreamingResponse on real uvicorn (not ASGITransport).
        sse_ok = False
        sse_preview = ""
        try:
            async with client.stream(
                "GET",
                "/api/v1/notifications/stream",
                headers={
                    **auth_headers,
                    "Accept": "text/event-stream",
                },
                timeout=httpx.Timeout(30.0, connect=10.0, read=15.0),
            ) as sse_resp:
                status = sse_resp.status_code
                if status >= 300:
                    timeline.append(
                        {
                            "step": "notifications.sse_stream",
                            "status": status,
                            "ok": False,
                            "sample": {"error": "non-2xx"},
                        }
                    )
                    failures.append("notifications sse non-2xx")
                else:
                    buf = b""
                    async for chunk in sse_resp.aiter_bytes():
                        buf += chunk
                        if b"event: ready" in buf:
                            sse_ok = True
                            break
                        if len(buf) > 262144:
                            break
                    sse_preview = buf[:400].decode("utf-8", errors="replace")
                    timeline.append(
                        {
                            "step": "notifications.sse_stream",
                            "status": status,
                            "ok": sse_ok,
                            "sample": {"ready_seen": sse_ok, "preview": sse_preview},
                        }
                    )
                    if not sse_ok:
                        failures.append("notifications sse missing ready event")
        except Exception as exc:
            timeline.append(
                {
                    "step": "notifications.sse_stream",
                    "status": 0,
                    "ok": False,
                    "sample": {"error": repr(exc)},
                }
            )
            failures.append(f"notifications sse exception: {exc}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "ran_at": datetime.utcnow().isoformat() + "Z",
                "base_url": base,
                "timeline": timeline,
                "failures": failures,
                "summary": {
                    "steps": len(timeline),
                    "ok": sum(1 for s in timeline if s["ok"]),
                    "fail": sum(1 for s in timeline if not s["ok"]),
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    if failures:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default="sqlite+aiosqlite:///./data/smoke_prd10.db",
        help="DATABASE_URL for the smoke run (default: file SQLite)",
    )
    parser.add_argument(
        "--output",
        default="tests/integration/api/prd10/smoke_run.json",
        help="Path to write the JSON report",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Do not delete the SQLite file or upload directory at the end",
    )
    args = parser.parse_args(argv)

    output_path = (ROOT / args.output).resolve()
    Path("data").mkdir(exist_ok=True)
    Path("data/smoke_uploads").mkdir(exist_ok=True)

    sqlite_file = None
    if args.db.startswith("sqlite"):
        # Use a fresh DB per run.
        prefix = "sqlite+aiosqlite:///"
        if args.db.startswith(prefix):
            sqlite_file = Path(args.db[len(prefix):])
            if sqlite_file.exists():
                sqlite_file.unlink()

    os.environ["DATABASE_URL"] = args.db
    os.environ["PRD10_UPLOADS_BASE"] = str((ROOT / "data" / "smoke_uploads").resolve())

    port = _pick_free_port()
    base = f"http://127.0.0.1:{port}"

    _start_server(port)
    try:
        _wait_for_port("127.0.0.1", port)
    except TimeoutError as exc:
        print(f"[smoke] {exc}", file=sys.stderr)
        return 2

    rc = asyncio.run(_smoke(base, output_path))

    print(f"[smoke] report: {output_path}")
    if rc == 0:
        print("[smoke] all PRD10 critical-path steps passed")
    else:
        print("[smoke] FAILURES, see report for details", file=sys.stderr)

    if not args.keep:
        if sqlite_file and sqlite_file.exists():
            try:
                sqlite_file.unlink()
            except OSError:
                pass

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
