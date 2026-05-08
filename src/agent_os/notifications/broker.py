"""In-process SSE broker for notifications.

This is the V1 implementation of PRD10 §15 real-time push. It is intentionally
simple: per-user ``asyncio.Queue`` instances live in process memory; producers
push payloads via :func:`publish_notification`, and the SSE endpoint
consumes through :func:`subscribe`.

Production deployments are expected to swap this for Redis Pub/Sub or a
dedicated message bus by replacing the broker singleton; the API surface
intentionally mirrors that of a typical pubsub client.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from agent_os.notifications.models import Notification


class _Broker:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._subscribers: dict[uuid.UUID, set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, user_id: uuid.UUID, payload: dict) -> None:
        # Snapshot the subscriber set under the lock so we can iterate
        # without holding it (queues handle their own backpressure).
        async with self._lock:
            queues = list(self._subscribers.get(user_id, ()))
        for queue in queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop the oldest message rather than block producers; SSE
                # is best-effort for V1.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(payload)

    @asynccontextmanager
    async def subscribe(self, user_id: uuid.UUID) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1024)
        async with self._lock:
            self._subscribers[user_id].add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                bucket = self._subscribers.get(user_id)
                if bucket is not None:
                    bucket.discard(queue)
                    if not bucket:
                        self._subscribers.pop(user_id, None)


_broker_singleton: _Broker | None = None


def get_broker() -> _Broker:
    global _broker_singleton
    if _broker_singleton is None:
        _broker_singleton = _Broker()
    return _broker_singleton


def reset_broker_for_tests() -> None:
    global _broker_singleton
    _broker_singleton = _Broker()


async def publish_notification(notification: Notification) -> None:
    """Convenience entry: publish a freshly-inserted Notification row."""

    await get_broker().publish(notification.user_id, notification.to_prd10_dict())


def encode_sse(event: str, data: dict) -> bytes:
    """Format an SSE event frame."""

    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode()


__all__ = [
    "get_broker",
    "reset_broker_for_tests",
    "publish_notification",
    "encode_sse",
]
