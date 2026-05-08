"""PRD10 §15 SSE notification stream tests.

``httpx.ASGITransport`` + ``StreamingResponse`` + pytest's asyncio loop can stall on
Windows (transport scheduling vs Starlette disconnect probes), even with dual
async clients and ``RequestIdMiddleware`` disabled.

These tests start **real uvicorn** on ``127.0.0.1:{free_port}`` (daemon thread) and
use synchronous TCP ``httpx.Client`` — identical networking stack to production and
stable on Windows CI.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn

pytestmark = pytest.mark.asyncio


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_server(base_url: str, *, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_exc: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/openapi.json", timeout=0.25)
            if r.status_code == 200:
                return
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(0.05)
    raise AssertionError(f"server did not become ready at {base_url}: {last_exc!r}")


def _parse_sse_chunk(chunk: bytes) -> tuple[str, dict] | None:
    text = chunk.decode("utf-8").strip()
    if not text:
        return None
    event = None
    data = None
    for line in text.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = json.loads(line.split(":", 1)[1].strip())
    if event is None:
        return None
    return event, (data or {})


def _uvicorn_sse_emits_ready_then_notification(app) -> None:
    from agent_os.notifications.broker import reset_broker_for_tests

    port = _pick_free_port()
    base = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            loop="asyncio",
        )
    )

    threading.Thread(target=server.run, daemon=True).start()
    _wait_for_server(base)

    reset_broker_for_tests()

    seen: list[tuple[str, dict]] = []
    reader_done = threading.Event()
    reader_error: list[BaseException] = []

    def reader_task() -> None:
        try:
            with httpx.Client(base_url=base, timeout=60.0) as client:
                with client.stream(
                    "GET", "/api/v1/notifications/stream"
                ) as response:
                    assert response.status_code == 200
                    for raw in response.iter_bytes():
                        parsed = _parse_sse_chunk(raw)
                        if parsed is None:
                            continue
                        seen.append(parsed)
                        if any(evt == "notification" for evt, _ in seen):
                            break
        except BaseException as exc:  # noqa: BLE001
            reader_error.append(exc)
        finally:
            reader_done.set()

    rt = threading.Thread(target=reader_task, daemon=True)
    rt.start()
    time.sleep(0.3)

    with httpx.Client(base_url=base, timeout=30.0) as client:
        capture_resp = client.post(
            "/api/v1/capture/text",
            json={"content": "SSE 测试内容"},
        )
    assert capture_resp.status_code == 200

    assert reader_done.wait(timeout=20.0), "SSE reader thread stuck"
    rt.join(timeout=2.0)
    server.should_exit = True
    if reader_error:
        raise reader_error[0]

    assert seen, "expected at least one SSE event"
    assert seen[0][0] == "ready"
    notif_payloads = [data for evt, data in seen if evt == "notification"]
    assert notif_payloads, "expected at least one notification event"
    assert notif_payloads[0]["type"] == "job_completed"


def _uvicorn_sse_other_user_does_not_receive(app_owner, app_other) -> None:
    from agent_os.notifications.broker import reset_broker_for_tests

    port_owner = _pick_free_port()
    port_other = _pick_free_port()
    base_owner = f"http://127.0.0.1:{port_owner}"
    base_other = f"http://127.0.0.1:{port_other}"

    srv_owner = uvicorn.Server(
        uvicorn.Config(
            app_owner,
            host="127.0.0.1",
            port=port_owner,
            log_level="warning",
            loop="asyncio",
        )
    )
    srv_other = uvicorn.Server(
        uvicorn.Config(
            app_other,
            host="127.0.0.1",
            port=port_other,
            log_level="warning",
            loop="asyncio",
        )
    )

    threading.Thread(target=srv_owner.run, daemon=True).start()
    threading.Thread(target=srv_other.run, daemon=True).start()
    _wait_for_server(base_owner)
    _wait_for_server(base_other)

    reset_broker_for_tests()

    received: list[tuple[str, dict]] = []
    reader_done = threading.Event()
    reader_error: list[BaseException] = []

    def reader() -> None:
        try:
            with httpx.Client(base_url=base_other, timeout=60.0) as client:
                with client.stream(
                    "GET", "/api/v1/notifications/stream"
                ) as response:
                    assert response.status_code == 200
                    saw_ready = False
                    for raw in response.iter_bytes():
                        parsed = _parse_sse_chunk(raw)
                        if parsed is None:
                            continue
                        received.append(parsed)
                        if parsed[0] == "ready" and not saw_ready:
                            saw_ready = True
                            time.sleep(0.7)
                            break
        except BaseException as exc:  # noqa: BLE001
            reader_error.append(exc)
        finally:
            reader_done.set()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    time.sleep(0.3)

    with httpx.Client(base_url=base_owner, timeout=30.0) as client:
        resp = client.post("/api/v1/capture/text", json={"content": "私密"})
    assert resp.status_code == 200

    assert reader_done.wait(timeout=20.0), "SSE reader thread stuck"
    t.join(timeout=2.0)
    srv_owner.should_exit = True
    srv_other.should_exit = True
    if reader_error:
        raise reader_error[0]

    notif_events = [evt for evt, _ in received if evt == "notification"]
    assert notif_events == [], f"unexpected cross-user notifications: {received}"


async def test_sse_emits_ready_then_notification(prd10_app):
    await asyncio.to_thread(_uvicorn_sse_emits_ready_then_notification, prd10_app)


async def test_sse_other_user_does_not_receive(prd10_app, prd10_other_app):
    await asyncio.to_thread(
        _uvicorn_sse_other_user_does_not_receive, prd10_app, prd10_other_app
    )
