"""Tests for the PRD10 background worker loop scheduling layer."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from agent_os.jobs import JobType, create_job
from agent_os.jobs.models import Job, JobStatus
from agent_os.jobs.worker_loop import (
    is_worker_enabled,
    start_worker_loop,
    stop_worker_loop,
)


@contextmanager
def _env(name: str, value: str | None) -> Iterator[None]:
    previous = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def test_is_worker_enabled_default_on():
    with _env("AGENTOS_PRD10_WORKER", None):
        assert is_worker_enabled() is True


def test_is_worker_enabled_respects_off_switch():
    for value in ("off", "0", "false", "DISABLED"):
        with _env("AGENTOS_PRD10_WORKER", value):
            assert is_worker_enabled() is False


@pytest.mark.asyncio
async def test_start_worker_loop_returns_none_when_disabled():
    with _env("AGENTOS_PRD10_WORKER", "off"):
        task = start_worker_loop()
        assert task is None


@pytest.mark.asyncio
async def test_worker_loop_drains_jobs_when_enabled(
    monkeypatch,
    prd10_engine,
    prd10_sessionmaker,
    prd10_user,
):
    """The loop should pick up a queued AI-to-KB job within one tick."""

    monkeypatch.setattr(
        "agent_os.jobs.worker_loop.get_sessionmaker",
        lambda: prd10_sessionmaker,
    )

    async with prd10_sessionmaker() as session:
        job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "ai_message_to_kb",
                "title": "loop test",
                "content": "由 worker loop 处理的 AI 输出",
            },
        )
        await session.commit()
        job_id = job.id

    with _env("AGENTOS_PRD10_WORKER", "on"), _env(
        "AGENTOS_PRD10_WORKER_INTERVAL", "0.1"
    ):
        task = start_worker_loop()
        assert task is not None
        try:
            for _ in range(50):
                await asyncio.sleep(0.05)
                async with prd10_sessionmaker() as session:
                    refreshed = await session.get(Job, job_id)
                    if (
                        refreshed is not None
                        and refreshed.status == JobStatus.COMPLETED.value
                    ):
                        break
            else:
                pytest.fail("worker loop did not process job within timeout")
        finally:
            await stop_worker_loop()
