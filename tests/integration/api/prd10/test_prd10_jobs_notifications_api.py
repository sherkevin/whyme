"""PRD10 §15/§16 jobs + notifications endpoint tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from agent_os.inbox.prd10_models import InboxItemType, Prd10InboxItem
from agent_os.jobs import JobType, create_job
from agent_os.jobs.models import JobStatus
from agent_os.jobs.service import process_job_once, process_pending_jobs
from agent_os.kb.models import Chunk, Document
from agent_os.notifications.models import Notification, NotificationType
from agent_os.tasks.models import PRD10Task

pytestmark = pytest.mark.asyncio


async def _capture_text(client) -> dict:
    response = await client.post(
        "/api/v1/capture/text",
        json={"content": "需要一个 job 进行测试"},
    )
    response.raise_for_status()
    return response.json()["data"]


async def test_get_job_returns_prd10_envelope(prd10_client):
    captured = await _capture_text(prd10_client)
    job_id = captured["job"]["id"]

    resp = await prd10_client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == job_id
    assert body["data"]["status"] == "completed"
    assert body["data"]["progress"] == 100


async def test_cancel_completed_job_returns_validation_error(prd10_client):
    captured = await _capture_text(prd10_client)
    job_id = captured["job"]["id"]

    resp = await prd10_client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


async def test_get_unknown_job_returns_404(prd10_client):
    resp = await prd10_client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_other_user_cannot_see_my_job(prd10_client, prd10_other_client):
    captured = await _capture_text(prd10_client)
    job_id = captured["job"]["id"]

    resp = await prd10_other_client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 404


async def test_notifications_listing_pagination_and_total(prd10_client):
    for _ in range(3):
        await _capture_text(prd10_client)

    resp = await prd10_client.get(
        "/api/v1/notifications", params={"page": 1, "page_size": 2}
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert len(body["items"]) == 2
    assert body["pagination"]["total"] >= 3
    assert body["pagination"]["has_more"] is True


async def test_mark_notification_read_and_unread_count_drops(prd10_client):
    await _capture_text(prd10_client)

    listing = await prd10_client.get(
        "/api/v1/notifications", params={"is_read": False}
    )
    items = listing.json()["data"]["items"]
    assert items, "expected at least one unread notification"
    notif_id = items[0]["id"]

    before = (await prd10_client.get("/api/v1/notifications/unread-count")).json()["data"]["count"]

    read = await prd10_client.post(f"/api/v1/notifications/{notif_id}/read")
    assert read.status_code == 200
    assert read.json()["data"]["is_read"] is True

    after = (await prd10_client.get("/api/v1/notifications/unread-count")).json()["data"]["count"]
    assert after == before - 1


async def test_read_all_marks_everything(prd10_client):
    for _ in range(2):
        await _capture_text(prd10_client)

    response = await prd10_client.post("/api/v1/notifications/read-all")
    assert response.status_code == 200
    assert response.json()["data"]["updated"] >= 2

    unread = await prd10_client.get("/api/v1/notifications/unread-count")
    assert unread.json()["data"]["count"] == 0


async def test_process_ai_message_to_kb_job_creates_document_and_chunk(
    prd10_sessionmaker,
    prd10_user,
):
    async with prd10_sessionmaker() as session:
        job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "ai_message_to_kb",
                "message_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "title": "AI 总结",
                "tags": ["AI输出", "总结"],
                "content": "这是一段应该被保存到知识库的 AI 输出。",
            },
        )
        await session.commit()
        job_id = job.id

        processed = await process_job_once(session, job_id)
        await session.commit()

        assert processed is not None
        assert processed.status == JobStatus.COMPLETED.value
        assert processed.progress == 100
        document_id = processed.output["document_id"]

        document = (
            await session.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
        ).scalar_one()
        assert document.user_id == prd10_user.id
        assert document.title == "AI 总结"
        assert document.content == "这是一段应该被保存到知识库的 AI 输出。"
        assert document.tags == ["AI输出", "总结"]
        assert document.extra["source"] == "ai_message"

        chunk = (
            await session.execute(select(Chunk).where(Chunk.document_id == document.id))
        ).scalar_one()
        assert chunk.chunk_index == 0
        assert chunk.content == document.content


async def test_process_ai_message_to_kb_job_fails_empty_content(
    prd10_sessionmaker,
    prd10_user,
    monkeypatch,
):
    # PRD10 §12.7 — validation errors go through the retry budget; with
    # max_retries=0 the very first attempt dead-letters and keeps the
    # original ``VALIDATION_ERROR`` code (under ``original_code``) plus
    # ``MAX_RETRIES_EXCEEDED`` on the outer envelope. Production keeps
    # max_retries=3, so a real transient empty-content race self-heals.
    monkeypatch.setenv("AGENTOS_JOB_MAX_RETRIES", "0")

    async with prd10_sessionmaker() as session:
        job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "ai_message_to_kb",
                "title": "空内容",
                "content": "",
            },
        )
        await session.commit()
        job_id = job.id

        processed = await process_job_once(session, job_id)
        await session.commit()

        assert processed is not None
        assert processed.status == JobStatus.FAILED.value
        # Outer code is the dead-letter envelope; ``original_code`` carries
        # the materializer's verdict so callers can distinguish failure
        # modes (validation vs runtime crash).
        assert processed.error["code"] == "MAX_RETRIES_EXCEEDED"
        assert processed.error.get("original_code") == "VALIDATION_ERROR"


async def test_process_ai_message_to_tasks_creates_prd10_tasks_and_compat_inbox_items(
    prd10_sessionmaker,
    prd10_user,
):
    async with prd10_sessionmaker() as session:
        job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.GENERATE_REPORT,
            payload={
                "kind": "ai_message_to_tasks",
                "message_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "tasks": [
                    {"title": "整理周报", "priority": "high", "tags": ["AI输出"]},
                    {"title": "复盘上周", "description": "重点回顾 PRD10 收尾"},
                    "  ",
                ],
            },
        )
        await session.commit()
        job_id = job.id

        processed = await process_job_once(session, job_id)
        await session.commit()

        assert processed is not None
        assert processed.status == JobStatus.COMPLETED.value
        assert processed.output["task_count"] == 2
        assert len(processed.output["task_ids"]) == 2

        prd10_tasks = (
            await session.execute(
                select(PRD10Task).where(PRD10Task.user_id == prd10_user.id)
            )
        ).scalars().all()
        task_titles = sorted(item.title for item in prd10_tasks)
        assert task_titles == ["复盘上周", "整理周报"]
        for item in prd10_tasks:
            assert item.extra["source"] == "ai_message"
            assert item.source_type == "ai"
            assert item.status == "todo"

        inbox_items = (
            await session.execute(
                select(Prd10InboxItem).where(
                    Prd10InboxItem.user_id == prd10_user.id,
                    Prd10InboxItem.type == InboxItemType.MANUAL_TASK.value,
                )
            )
        ).scalars().all()
        titles = sorted(item.title for item in inbox_items)
        assert titles == ["复盘上周", "整理周报"]
        for item in inbox_items:
            assert item.extra["source"] == "ai_message"
            assert item.extra["task_id"] in processed.output["task_ids"]
            assert item.job_id == job_id
            assert item.auto_process is False


async def test_process_ai_message_to_tasks_fails_empty_payload(
    prd10_sessionmaker,
    prd10_user,
):
    async with prd10_sessionmaker() as session:
        job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.GENERATE_REPORT,
            payload={
                "kind": "ai_message_to_tasks",
                "tasks": [],
            },
        )
        await session.commit()

        processed = await process_job_once(session, job.id)
        await session.commit()

        assert processed is not None
        assert processed.status == JobStatus.FAILED.value
        assert processed.error["code"] == "VALIDATION_ERROR"


async def test_worker_writes_ai_output_saved_notification(
    prd10_sessionmaker,
    prd10_user,
):
    async with prd10_sessionmaker() as session:
        job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "ai_message_to_kb",
                "title": "AI 总结",
                "content": "通知联动测试",
            },
        )
        await session.commit()

        await process_job_once(session, job.id)
        await session.commit()

        notification = (
            await session.execute(
                select(Notification).where(
                    Notification.user_id == prd10_user.id,
                    Notification.type == NotificationType.AI_OUTPUT_SAVED.value,
                )
            )
        ).scalar_one()
        assert notification.title == "AI 输出已保存到知识库"
        assert notification.object_type == "document"
        assert notification.is_read is False


async def test_process_pending_jobs_drains_supported_kinds(
    prd10_sessionmaker,
    prd10_user,
):
    async with prd10_sessionmaker() as session:
        kb_job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "ai_message_to_kb",
                "title": "批处理-KB",
                "content": "调度器路径的 KB 测试内容",
            },
        )
        tasks_job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.GENERATE_REPORT,
            payload={
                "kind": "ai_message_to_tasks",
                "tasks": [{"title": "调度器路径的任务"}],
            },
        )
        # An unsupported job kind must remain queued; the worker is
        # intentionally narrow.
        unsupported_job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={"kind": "capture_text", "inbox_item_id": str(uuid.uuid4())},
        )
        await session.commit()

        processed = await process_pending_jobs(session, limit=10)

        assert {kb_job.id, tasks_job.id} == set(processed)
        assert unsupported_job.id not in processed

        await session.refresh(unsupported_job)
        assert unsupported_job.status == JobStatus.QUEUED.value


# ---------------------------------------------------------------------------
# §12.7 — retry / dead-letter coverage
# ---------------------------------------------------------------------------


async def test_failed_job_requeues_with_backoff_until_max_retries(
    prd10_sessionmaker, prd10_user, monkeypatch
):
    """A job that fails ``VALIDATION_ERROR`` must bounce back to ``queued``
    until ``max_retries`` is reached, then dead-letter with
    ``MAX_RETRIES_EXCEEDED``."""

    monkeypatch.setenv("AGENTOS_JOB_MAX_RETRIES", "2")
    monkeypatch.setenv("AGENTOS_JOB_BACKOFF_BASE_SECONDS", "1")

    async with prd10_sessionmaker() as session:
        # Empty content forces the materializer to call mark_job_failed
        # with a VALIDATION_ERROR — the deterministic retryable failure.
        job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={"kind": "ai_message_to_kb", "content": ""},
        )
        await session.commit()
        job_id = job.id

        # Attempt 1 → requeued (retry_count=1).
        from agent_os.jobs.models import Job
        from agent_os.jobs.service import process_job_once

        await process_job_once(session, job_id)
        await session.commit()
        await session.refresh(job)
        assert job.status == JobStatus.QUEUED.value
        assert int((job.input or {}).get("retry_count") or 0) == 1
        assert (job.input or {}).get("next_attempt_at")

    # Force the backoff window open before the next attempt by reaching
    # into the row directly (simulates real-time clock advance).
    async with prd10_sessionmaker() as session:
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        payload = dict(job.input or {})
        payload["next_attempt_at"] = "2000-01-01T00:00:00+00:00"
        job.input = payload
        await session.commit()

    async with prd10_sessionmaker() as session:
        from agent_os.jobs.models import Job
        from agent_os.jobs.service import process_job_once

        # Attempt 2 → requeued (retry_count=2 == max_retries).
        await process_job_once(session, job_id)
        await session.commit()
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert job.status == JobStatus.QUEUED.value
        assert int((job.input or {}).get("retry_count") or 0) == 2

    async with prd10_sessionmaker() as session:
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        payload = dict(job.input or {})
        payload["next_attempt_at"] = "2000-01-01T00:00:00+00:00"
        job.input = payload
        await session.commit()

    async with prd10_sessionmaker() as session:
        from agent_os.jobs.models import Job
        from agent_os.jobs.service import process_job_once

        # Attempt 3 → dead-letter (retry budget exhausted).
        await process_job_once(session, job_id)
        await session.commit()
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()
        assert job.status == JobStatus.FAILED.value
        assert (job.error or {}).get("code") == "MAX_RETRIES_EXCEEDED"
        assert (job.error or {}).get("retry_count") == 2
        assert (job.error or {}).get("max_retries") == 2


async def test_process_pending_jobs_skips_jobs_inside_backoff_window(
    prd10_sessionmaker, prd10_user
):
    """``process_pending_jobs`` must skip rows whose ``next_attempt_at``
    is in the future (so backoff actually pauses)."""


    async with prd10_sessionmaker() as session:
        future_job = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "ai_message_to_kb",
                "title": "future",
                "content": "this body is fine",
                "retry_count": 1,
                "next_attempt_at": "2999-01-01T00:00:00+00:00",
            },
        )
        await session.commit()

        processed = await process_pending_jobs(session, limit=10)
        assert future_job.id not in processed
        await session.refresh(future_job)
        assert future_job.status == JobStatus.QUEUED.value


async def test_dead_letter_listing_returns_only_max_retries_exhausted(
    prd10_sessionmaker, prd10_user
):
    """``list_dead_letter_jobs`` returns only rows that exhausted retries."""

    from agent_os.jobs.service import (
        list_dead_letter_jobs,
        mark_job_failed,
    )

    async with prd10_sessionmaker() as session:
        dead = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "ai_message_to_kb",
                "content": "x",
                "retry_count": 99,
            },
        )
        # Failure path: retry_count >= max_retries → dead-letter.
        await mark_job_failed(
            session,
            dead.id,
            error={"code": "JOB_FAILED", "message": "exhausted"},
            retryable=True,
        )
        # And a still-fresh failure that should NOT show up.
        fresh = await create_job(
            session,
            user_id=prd10_user.id,
            job_type=JobType.PARSE_FILE,
            payload={"kind": "ai_message_to_kb", "content": "x"},
        )
        await mark_job_failed(
            session,
            fresh.id,
            error={"code": "VALIDATION_ERROR", "message": "still retryable"},
            retryable=True,
        )
        await session.commit()

        rows = await list_dead_letter_jobs(session, user_id=prd10_user.id)
        ids = {row.id for row in rows}
        assert dead.id in ids
        assert fresh.id not in ids
