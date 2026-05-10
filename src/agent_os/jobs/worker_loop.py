"""Cooperative startup loop for the PRD10 job worker.

The actual materialization lives in ``agent_os.jobs.service.process_job_once``
and ``process_pending_jobs``. This module owns the *scheduling* part: a tiny
asyncio task that wakes up periodically, opens a fresh DB session, drains a
batch, and goes back to sleep.

Design constraints:

- Must be safe to skip in tests / when the worker is intentionally disabled
  (``AGENTOS_PRD10_WORKER=off``).
- Must never crash the FastAPI startup if the DB is not reachable yet — it
  logs and retries on the next tick.
- Must support graceful shutdown via ``stop_worker_loop``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from agent_os.db.base import get_sessionmaker
from agent_os.jobs.service import process_pending_jobs

logger = logging.getLogger("agent_os.jobs.worker_loop")

_DEFAULT_INTERVAL_SECONDS = 30.0
_DEFAULT_BATCH_LIMIT = 25
_ENV_DISABLE = "AGENTOS_PRD10_WORKER"
_ENV_INTERVAL = "AGENTOS_PRD10_WORKER_INTERVAL"
_ENV_BATCH_LIMIT = "AGENTOS_PRD10_WORKER_BATCH_LIMIT"

_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


def is_worker_enabled() -> bool:
    """Honor an explicit env opt-out so tests / dev can keep startup quiet."""

    return os.environ.get(_ENV_DISABLE, "on").strip().lower() not in {
        "off",
        "0",
        "false",
        "disabled",
    }


def _resolve_interval() -> float:
    raw = os.environ.get(_ENV_INTERVAL)
    if not raw:
        return _DEFAULT_INTERVAL_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_INTERVAL_SECONDS
    if value <= 0:
        return _DEFAULT_INTERVAL_SECONDS
    return value


def _resolve_batch_limit() -> int:
    raw = os.environ.get(_ENV_BATCH_LIMIT)
    if not raw:
        return _DEFAULT_BATCH_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_BATCH_LIMIT
    return max(1, min(200, value))


async def _run_once() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            processed = await process_pending_jobs(session, limit=_resolve_batch_limit())
        except Exception:
            logger.exception("PRD10 worker tick failed")
            return
    if processed:
        logger.info(
            "PRD10 worker drained %d job(s): %s",
            len(processed),
            ",".join(str(job_id) for job_id in processed),
        )


async def _loop(interval: float) -> None:
    assert _stop_event is not None
    logger.info("PRD10 worker loop started (interval=%.1fs)", interval)
    try:
        while not _stop_event.is_set():
            try:
                await _run_once()
            except Exception:
                logger.exception("PRD10 worker iteration failed")
            try:
                await asyncio.wait_for(_stop_event.wait(), timeout=interval)
            except TimeoutError:
                continue
    finally:
        logger.info("PRD10 worker loop stopped")


def start_worker_loop() -> asyncio.Task | None:
    """Start the background worker loop on the running event loop.

    Returns the underlying task (so callers can keep a reference) or ``None``
    if the worker is disabled.
    """

    global _task, _stop_event

    if not is_worker_enabled():
        logger.info("PRD10 worker disabled via %s", _ENV_DISABLE)
        return None
    if _task is not None and not _task.done():
        return _task

    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_loop(_resolve_interval()), name="prd10-worker-loop")
    return _task


async def stop_worker_loop() -> None:
    """Signal the worker loop to exit and wait for it to finish."""

    global _task, _stop_event

    if _stop_event is None or _task is None:
        return

    _stop_event.set()
    try:
        await asyncio.wait_for(_task, timeout=5.0)
    except (TimeoutError, asyncio.CancelledError):
        _task.cancel()
    finally:
        _task = None
        _stop_event = None


__all__ = [
    "is_worker_enabled",
    "start_worker_loop",
    "stop_worker_loop",
]
