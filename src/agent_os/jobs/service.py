"""Helpers for creating and updating PRD10 ``Job`` rows.

This module is the single write surface that capture / KB / AI domains use to
record jobs. Keeping it small avoids duplicate transitions.

PRD10 §12.7 (todo-tasks.md) — failure retry + dead-letter queue:

* When a materializer raises (or marks a job ``failed`` because of a
  transient validation issue), we re-enqueue the job up to ``max_retries``
  times with exponential backoff (``next_attempt_at`` stamped on
  ``Job.input``); past that the job stays in the dead-letter set with
  ``error.code="MAX_RETRIES_EXCEEDED"``.
* ``process_pending_jobs`` skips rows whose ``next_attempt_at`` is still in
  the future so the backoff actually pauses the worker rather than
  burning the CPU.
* The retry counter lives on ``Job.input.retry_count`` so the model
  schema doesn't need a migration; this is the same pattern Agent 2 used
  for ``input.kind`` to extend the schema without ALTER TABLE.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.inbox.prd10_models import (
    InboxItemPriority,
    InboxItemProcessingStatus,
    InboxItemStatus,
    InboxItemType,
    Prd10InboxItem,
)
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.kb.models import Chunk, Document, DocumentStatus, DocumentType
from agent_os.notifications.models import NotificationType
from agent_os.notifications.service import create_notification
from agent_os.skills.runs import SkillRun, SkillRunStatus
from agent_os.stage3.models import Skill
from agent_os.tasks.models import PRD10Task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# §12.7 — retry / dead-letter knobs
# ---------------------------------------------------------------------------


_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE_SECONDS = 5  # 5s, 25s, 125s by default (5 ** retry_count)


def _max_retries() -> int:
    raw = os.environ.get("AGENTOS_JOB_MAX_RETRIES")
    try:
        v = int(raw) if raw is not None else _DEFAULT_MAX_RETRIES
    except (TypeError, ValueError):
        return _DEFAULT_MAX_RETRIES
    return max(0, v)


def _backoff_seconds(retry_count: int) -> int:
    raw = os.environ.get("AGENTOS_JOB_BACKOFF_BASE_SECONDS")
    try:
        base = int(raw) if raw is not None else _DEFAULT_BACKOFF_BASE_SECONDS
    except (TypeError, ValueError):
        base = _DEFAULT_BACKOFF_BASE_SECONDS
    base = max(1, base)
    # Exponential backoff capped at 24h so the dead-letter check eventually
    # fires regardless of how big retry_count gets.
    return min(24 * 3600, base ** max(1, retry_count))


def _is_terminal(status: str) -> bool:
    return status in (
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELED.value,
    )


def _retry_count(job: Job) -> int:
    payload = job.input or {}
    raw = payload.get("retry_count") if isinstance(payload, dict) else None
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _next_attempt_at(job: Job) -> datetime | None:
    payload = job.input or {}
    raw = payload.get("next_attempt_at") if isinstance(payload, dict) else None
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when


def _bump_retry(job: Job, *, error: dict[str, Any] | None) -> tuple[int, datetime]:
    """Mutate ``job`` for a retryable failure and return ``(retry_count, next_attempt_at)``."""

    payload = dict(job.input or {})
    retry_count = _retry_count(job) + 1
    next_attempt = datetime.now(UTC) + timedelta(
        seconds=_backoff_seconds(retry_count)
    )
    payload["retry_count"] = retry_count
    payload["next_attempt_at"] = next_attempt.isoformat()
    if error is not None:
        payload["last_error"] = error
    job.input = payload
    job.status = JobStatus.QUEUED.value
    job.progress = 0
    job.started_at = None
    job.completed_at = None
    job.error = None
    return retry_count, next_attempt


async def create_job(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_type: JobType | str,
    workspace_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> Job:
    """Insert a new ``queued`` job and flush so callers see ``job.id``."""

    job = Job(
        user_id=user_id,
        workspace_id=workspace_id,
        job_type=job_type.value if isinstance(job_type, JobType) else job_type,
        status=JobStatus.QUEUED.value,
        progress=0,
        input=payload or {},
        correlation_id=correlation_id,
    )
    db.add(job)
    await db.flush()
    return job


async def mark_job_completed(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    output: dict[str, Any] | None = None,
) -> Job | None:
    """Move a job to ``completed`` (no-op if already in a terminal state)."""

    job = await _load(db, job_id)
    if job is None or job.status in (
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELED.value,
    ):
        return job

    job.status = JobStatus.COMPLETED.value
    job.progress = 100
    job.output = output or job.output
    job.completed_at = datetime.now(UTC)
    await db.flush()
    return job


async def mark_job_failed(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    error: dict[str, Any] | None = None,
    retryable: bool = True,
) -> Job | None:
    """Mark a job as failed (or, when retryable + retry budget left, requeue it).

    When the failure is ``retryable`` (default) and the current attempt
    count is still below ``AGENTOS_JOB_MAX_RETRIES`` (default 3), the job
    moves back to ``queued`` with an exponential backoff stamped on
    ``input.next_attempt_at`` so :func:`process_pending_jobs` skips it
    until the next attempt window is open. Once we exhaust the retry
    budget — or a caller passes ``retryable=False`` — the job stays in
    ``failed`` with a dead-letter ``error.code``.
    """

    job = await _load(db, job_id)
    if job is None:
        return None
    if _is_terminal(job.status):
        return job

    err_payload = error or {"code": "JOB_FAILED", "message": "Unknown failure"}
    retry_count = _retry_count(job)
    max_retries = _max_retries()
    if retryable and retry_count < max_retries:
        next_count, next_at = _bump_retry(job, error=err_payload)
        await db.flush()
        logger.info(
            "[jobs] job %s requeued (retry %d/%d, next_at=%s)",
            job.id,
            next_count,
            max_retries,
            next_at.isoformat(),
        )
        return job

    # Dead-letter: retries exhausted (or caller forced it).
    if retry_count >= max_retries:
        original_code = (err_payload or {}).get("code")
        err_payload = dict(err_payload)
        err_payload["code"] = "MAX_RETRIES_EXCEEDED"
        err_payload["retry_count"] = retry_count
        err_payload["max_retries"] = max_retries
        if original_code and original_code != "MAX_RETRIES_EXCEEDED":
            err_payload["original_code"] = original_code
    job.status = JobStatus.FAILED.value
    job.error = err_payload
    job.completed_at = datetime.now(UTC)
    await db.flush()
    logger.warning(
        "[jobs] job %s dead-lettered after %d retries (code=%s)",
        job.id,
        retry_count,
        err_payload.get("code"),
    )
    return job


async def process_job_once(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    """Process one queued PRD10 job if this module owns its materialization.

    V1 endpoints already create durable ``prd10_jobs`` rows. This helper is
    the first product-data worker slice: it materializes AI assistant output
    saved to the knowledge base into ``kb_documents`` and ``kb_chunks``.
    Unsupported jobs are left untouched so other domain workers can consume
    them later.

    PRD10 §12.7 — unexpected exceptions thrown by the materializer are
    caught here so we can re-enqueue with backoff (instead of crashing the
    whole worker tick).
    """

    job = await _load(db, job_id)
    if job is None:
        return None
    if _is_terminal(job.status):
        return job

    # §12.7: enforce backoff window for retried jobs.
    next_at = _next_attempt_at(job)
    if next_at is not None and next_at > datetime.now(UTC):
        return job

    payload = job.input or {}
    kind = payload.get("kind")
    try:
        if job.job_type == JobType.PARSE_FILE.value and kind == "ai_message_to_kb":
            return await _materialize_ai_message_to_kb(db, job)
        if job.job_type == JobType.GENERATE_REPORT.value and kind == "ai_message_to_tasks":
            return await _materialize_ai_message_to_tasks(db, job)
        if job.job_type == JobType.SKILL_RUN.value:
            return await _materialize_skill_run(db, job)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("[jobs] materializer crashed for job %s", job.id)
        return await mark_job_failed(
            db,
            job.id,
            error={"code": "JOB_RUNTIME_ERROR", "message": str(exc)},
            retryable=True,
        )

    return job


async def list_dead_letter_jobs(
    db: AsyncSession,
    *,
    limit: int = 50,
    user_id: uuid.UUID | None = None,
) -> list[Job]:
    """PRD10 §12.7 helper — list jobs that exhausted the retry budget."""

    stmt = (
        select(Job)
        .where(Job.status == JobStatus.FAILED.value)
        .order_by(Job.completed_at.desc().nulls_last())
        .limit(limit)
    )
    if user_id is not None:
        stmt = stmt.where(Job.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        job
        for job in rows
        if isinstance(job.error, dict)
        and job.error.get("code") == "MAX_RETRIES_EXCEEDED"
    ]


async def _materialize_ai_message_to_kb(db: AsyncSession, job: Job) -> Job:
    payload = job.input or {}
    content = str(payload.get("content") or "").strip()
    if not content:
        # PRD10 §12.7 — validation errors go through the retry budget so a
        # transient row-write race (e.g. job created before AI streaming
        # finishes pushing the assistant content) can self-heal; only after
        # max_retries the worker dead-letters with ``MAX_RETRIES_EXCEEDED``.
        return await mark_job_failed(
            db,
            job.id,
            error={
                "code": "VALIDATION_ERROR",
                "message": "AI message content is empty",
            },
            retryable=True,
        )

    job.status = JobStatus.RUNNING.value
    job.progress = 30
    job.started_at = datetime.now(UTC)
    await db.flush()

    title = str(payload.get("title") or "AI 输出").strip() or "AI 输出"
    folder_id = _uuid_or_none(payload.get("folder_id"))
    tags = list(payload.get("tags") or [])

    document = Document(
        user_id=job.user_id,
        workspace_id=job.workspace_id,
        folder_id=folder_id,
        title=title,
        summary=_summary(content),
        content=content,
        document_type=DocumentType.NOTE.value,
        status=DocumentStatus.READY.value,
        tags=tags,
        word_count=len(content),
        extra={
            "source": "ai_message",
            "message_id": payload.get("message_id"),
            "conversation_id": payload.get("conversation_id"),
            "job_id": str(job.id),
        },
    )
    db.add(document)
    await db.flush()

    db.add(
        Chunk(
            document_id=document.id,
            user_id=job.user_id,
            source_id=document.source_id,
            chunk_index=0,
            content=content,
            token_count=_token_count(content),
            extra={"source": "ai_message", "job_id": str(job.id)},
        )
    )

    completed = await mark_job_completed(
        db,
        job.id,
        output={
            "kind": "ai_message_to_kb",
            "document_id": str(document.id),
            "chunk_count": 1,
        },
    )

    await create_notification(
        db,
        user_id=job.user_id,
        workspace_id=job.workspace_id,
        type=NotificationType.AI_OUTPUT_SAVED,
        title="AI 输出已保存到知识库",
        content=document.title,
        object_type="document",
        object_id=str(document.id),
    )

    return completed


async def _materialize_ai_message_to_tasks(db: AsyncSession, job: Job) -> Job:
    payload = job.input or {}
    raw_tasks = payload.get("tasks") or []
    tasks: list[dict[str, Any]] = []
    for entry in raw_tasks:
        if isinstance(entry, dict):
            tasks.append(entry)
        elif isinstance(entry, str) and entry.strip():
            tasks.append({"title": entry.strip()})

    if not tasks:
        # Same as the KB path: a permanent validation problem skips retry.
        return await mark_job_failed(
            db,
            job.id,
            error={
                "code": "VALIDATION_ERROR",
                "message": "tasks must be a non-empty list",
            },
            retryable=False,
        )

    job.status = JobStatus.RUNNING.value
    job.progress = 30
    job.started_at = datetime.now(UTC)
    await db.flush()

    task_ids: list[str] = []
    inbox_ids: list[str] = []
    for task in tasks:
        title = str(task.get("title") or "").strip()
        if not title:
            continue
        priority = task.get("priority") or "medium"
        if priority == InboxItemPriority.NORMAL.value:
            priority = "medium"
        if priority not in {"low", "medium", "high", "urgent"}:
            priority = "medium"
        prd10_task = PRD10Task(
            user_id=job.user_id,
            workspace_id=job.workspace_id,
            title=title,
            description=str(task.get("description") or "") or None,
            status="todo",
            priority=priority,
            source_type="ai",
            source_id=str(payload.get("message_id") or ""),
            tags=list(task.get("tags") or []),
            extra={
                "source": "ai_message",
                "message_id": payload.get("message_id"),
                "conversation_id": payload.get("conversation_id"),
                "job_id": str(job.id),
            },
        )
        db.add(prd10_task)
        await db.flush()
        task_ids.append(str(prd10_task.id))

        inbox_priority = task.get("priority") or InboxItemPriority.NORMAL.value
        if inbox_priority not in {p.value for p in InboxItemPriority}:
            inbox_priority = InboxItemPriority.NORMAL.value
        item = Prd10InboxItem(
            user_id=job.user_id,
            workspace_id=job.workspace_id,
            type=InboxItemType.MANUAL_TASK.value,
            title=title,
            raw_content=str(task.get("description") or "") or None,
            status=InboxItemStatus.RECEIVED.value,
            processing_status=InboxItemProcessingStatus.COMPLETED.value,
            priority=inbox_priority,
            auto_process=False,
            tags=list(task.get("tags") or []),
            extra={
                "source": "ai_message",
                "task_id": str(prd10_task.id),
                "message_id": payload.get("message_id"),
                "conversation_id": payload.get("conversation_id"),
                "job_id": str(job.id),
            },
            job_id=job.id,
        )
        db.add(item)
        await db.flush()
        inbox_ids.append(str(item.id))

    if not task_ids:
        return await mark_job_failed(
            db,
            job.id,
            error={
                "code": "VALIDATION_ERROR",
                "message": "tasks must include a non-empty title",
            },
            retryable=False,
        )

    completed = await mark_job_completed(
        db,
        job.id,
        output={
            "kind": "ai_message_to_tasks",
            "task_count": len(task_ids),
            "task_ids": task_ids,
            "inbox_item_ids": inbox_ids,
        },
    )

    await create_notification(
        db,
        user_id=job.user_id,
        workspace_id=job.workspace_id,
        type=NotificationType.AI_OUTPUT_SAVED,
        title="AI 已生成任务",
        content=f"已添加 {len(inbox_ids)} 个待办任务",
        object_type="inbox_item",
        object_id=inbox_ids[0] if inbox_ids else None,
    )

    return completed


async def process_pending_jobs(
    db: AsyncSession,
    *,
    limit: int = 25,
) -> list[uuid.UUID]:
    """Drain a small batch of queued PRD10 jobs the worker knows how to run.

    Designed to be called from a startup loop or a cron-like scheduler. It is
    side-effect-free for unsupported job kinds: it only touches rows whose
    ``(job_type, input.kind)`` pair has a materializer registered above.
    The caller controls ``limit`` to stay polite under load.

    PRD10 §12.7 — rows whose ``input.next_attempt_at`` is still in the
    future are skipped here so the exponential backoff actually pauses
    the worker rather than tight-looping the same row every tick.
    """

    supported_types = (
        JobType.PARSE_FILE.value,
        JobType.GENERATE_REPORT.value,
        JobType.SKILL_RUN.value,
    )
    rows = (
        await db.execute(
            select(Job)
            .where(
                Job.status == JobStatus.QUEUED.value,
                Job.job_type.in_(supported_types),
            )
            .order_by(Job.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    now = datetime.now(UTC)
    processed: list[uuid.UUID] = []
    for job in rows:
        when = _next_attempt_at(job)
        if when is not None and when > now:
            # Backoff window not yet open — leave row for the next tick.
            continue
        result = await process_job_once(db, job.id)
        if result is None or result.status == JobStatus.QUEUED.value:
            continue
        processed.append(job.id)

    if processed:
        await db.commit()
    return processed


async def _load(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


def _summary(content: str) -> str:
    return content[:160]


def _token_count(content: str) -> int:
    return max(1, len(content.split()) or len(content))


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


# ---------------------------------------------------------------------------
# §16 — Skills real execution worker
# ---------------------------------------------------------------------------


_AGENT_ACTION_PROMPTS: dict[str, str] = {
    "extract_insights": (
        "你是访谈洞察分析师。从用户提供的访谈记录中提炼："
        "1) 三条核心洞察（每条 1 句）；"
        "2) 三句最有代表性的引用（保留原文）；"
        "3) 五项可立即跟进的行动。用 Markdown 输出。"
    ),
    "weekly_report": (
        "你是周报助理。基于用户提供的本周记录、卡片或要点，生成周报："
        "1) 本周成果（3-5 条）；2) 学到 / 发现（2-3 条）；3) 下周重点 / 风险。"
        "用中文 Markdown 输出，不超过 600 字。"
    ),
    "research_expand": (
        "你是研究助理。围绕用户给出的主题给出："
        "1) 五个值得深入的子方向；2) 每个方向 2 条关键资料 / 概念 / 案例；"
        "3) 一段 80 字以内的总览。用 Markdown 输出。"
    ),
    "markdown_polish": (
        "你是文字编辑。把用户提交的草稿润色为高质量 Markdown："
        "1) 标题层级 H2/H3；2) 适当代码块 / 引用 / 列表；"
        "3) 不改变原意；保留中文语气；末尾保留原信息密度。"
    ),
    "rate_ideas": (
        "你是产品评审。对用户给出的多条想法，按可行性 / 影响力 / 创新度三维度"
        "（1-10 分）逐条打分并给出 1 句点评，最后给出推荐执行顺序。"
        "用 Markdown 表格输出。"
    ),
    "meeting_minutes": (
        "你是会议秘书。从用户提供的会议文字稿中生成 5W1H 纪要："
        "1) 时间 / 地点 / 出席者；2) 议题与决策；3) 待办清单（含负责人 / 截止）。"
    ),
    "competitor_compare": (
        "你是竞品分析师。给用户列出的 3-5 个竞品做：功能 / 价格 / 用户评价 / "
        "差异点四列对比。用 Markdown 表格输出，最后给一段 80 字内总结。"
    ),
    "knowledge_cards": (
        "你是知识卡片设计师。从用户文本中提炼 3 张可独立阅读的卡片，类型分别为："
        "概念卡 / 案例卡 / 金句卡；每张含 标题、要点（2-3 句）、关联标签。"
    ),
    "code_review": (
        "你是高级工程师。对用户提交的代码做 Review："
        "1) 可读性；2) 性能；3) 安全；4) 测试覆盖。每项给 1 条具体建议，"
        "最后给出整体评分（A/B/C）。用 Markdown 输出。"
    ),
    "email_polish": (
        "你是商务文书编辑。把用户的邮件草稿润色为专业版："
        "1) 称呼合适；2) 段落结构清晰（背景/目的/请求/感谢）；"
        "3) 保留中文语气；4) 末尾给签名行。"
    ),
    "okr_breakdown": (
        "你是 OKR 教练。把用户的目标拆成 3-5 个 KR，每个 KR 配 2-3 条 Action。"
        "KR 必须可量化、可验证；用 Markdown 列表输出。"
    ),
    "interview_outline": (
        "你是用户调研专家。围绕调研主题生成 8-12 个访谈问题，"
        "包含 5 个开放式问题 + 3 个量化问题 + 2 个跟进问题。用 Markdown 编号列表。"
    ),
    "summarize": (
        "你是 Mydow AI。把输入整理为：1) 一句话摘要；2) 3-5 个要点；3) 下一步建议。"
    ),
}


def _build_skill_prompt(skill: Skill, user_input: dict[str, Any]) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for a skill run."""

    steps = list(skill.steps or [])
    primary_action = "summarize"
    if steps and isinstance(steps[0], dict):
        primary_action = (
            steps[0].get("agent_action")
            or steps[0].get("name")
            or "summarize"
        )

    system_prompt = _AGENT_ACTION_PROMPTS.get(
        primary_action, _AGENT_ACTION_PROMPTS["summarize"]
    )
    system_prompt = (
        f"{system_prompt}\n\n"
        f"Skill 名称: {skill.name}\nSkill 描述: {skill.description or ''}"
    )

    instruction = str(user_input.get("instruction") or "").strip()
    target = str(user_input.get("target") or "").strip()
    text = str(user_input.get("text") or "").strip()
    body_parts = []
    if instruction:
        body_parts.append(f"用户指令: {instruction}")
    if target:
        body_parts.append(f"目标对象: {target}")
    if text:
        body_parts.append(f"待处理内容:\n{text}")
    if not body_parts:
        body_parts.append(
            "（用户未提供具体内容，请基于 Skill 描述给出可复用的示例输出。）"
        )

    return system_prompt, "\n\n".join(body_parts)


async def _materialize_skill_run(db: AsyncSession, job: Job) -> Job:
    """§16 — Run a Skill end-to-end: LLM call + persist output."""

    payload = job.input or {}
    skill_id = _uuid_or_none(payload.get("skill_id"))
    if skill_id is None:
        return await mark_job_failed(
            db,
            job.id,
            error={"code": "VALIDATION_ERROR", "message": "skill_id missing"},
            retryable=False,
        )

    skill = (
        await db.execute(select(Skill).where(Skill.id == skill_id))
    ).scalar_one_or_none()
    if skill is None:
        return await mark_job_failed(
            db,
            job.id,
            error={"code": "NOT_FOUND", "message": "Skill not found"},
            retryable=False,
        )

    skill_run = (
        await db.execute(select(SkillRun).where(SkillRun.job_id == job.id))
    ).scalar_one_or_none()

    job.status = JobStatus.RUNNING.value
    job.progress = 30
    job.started_at = datetime.now(UTC)
    if skill_run is not None:
        skill_run.status = SkillRunStatus.RUNNING.value
        skill_run.started_at = datetime.now(UTC)
    await db.flush()

    user_input: dict[str, Any] = dict(payload.get("input") or {})

    doc_for_transform: Document | None = None
    tgt_doc_uuid = _uuid_or_none(user_input.get("document_id"))
    output_mode = str(
        user_input.get("output_mode")
        or user_input.get("output_disposition")
        or "generate"
    ).strip().lower()

    if tgt_doc_uuid is not None:
        doc_row = (
            await db.execute(
                select(Document).where(
                    Document.id == tgt_doc_uuid,
                    Document.user_id == job.user_id,
                    Document.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if doc_row is None:
            return await mark_job_failed(
                db,
                job.id,
                error={"code": "NOT_FOUND", "message": "document_id invalid"},
                retryable=False,
            )
        doc_for_transform = doc_row
        merged_head = (
            user_input.get("instruction")
            or user_input.get("text")
            or ""
        ).strip()
        base_doc = (doc_row.content or "").strip()
        merged = (
            f"{merged_head}\n\n---\n【知识库原文】《{doc_row.title or '文档'}》\n{base_doc}"
            if base_doc
            else merged_head
        )
        user_input["target"] = f"document:{doc_row.id}"
        user_input["text"] = merged

    system_prompt, user_prompt = _build_skill_prompt(skill, user_input)

    from agent_os.ai.llm_provider import get_provider, is_llm_enabled

    if not is_llm_enabled():
        content = (
            f"# {skill.name} 输出（占位）\n\n"
            "由于当前未启用真实 LLM（设置 AGENTOS_AI_LLM=on 启用），"
            "下面是基于 Skill 描述的占位输出：\n\n"
            f"- {skill.description or ''}\n"
            f"- 用户指令: {user_input.get('instruction', '（未提供）')}"
        )
        usage: dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": len(content),
        }
    else:
        provider = get_provider()
        try:
            result = await provider.complete(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("[jobs] skill_run LLM call failed")
            return await mark_job_failed(
                db,
                job.id,
                error={"code": "AI_PROVIDER_ERROR", "message": str(exc)},
                retryable=True,
            )
        content = (result or {}).get("content") or ""
        usage = (result or {}).get("usage") or {}

    output_payload: dict[str, Any] = {
        "kind": "skill_run",
        "skill_id": str(skill.id),
        "skill_name": skill.name,
        "content": content,
        "usage": usage,
    }

    save_output = payload.get("save_output")
    save_kind: str | None = None
    if isinstance(save_output, str):
        save_kind = save_output.strip().lower() or None
    elif save_output is True:
        save_kind = "kb"

    extra_artifacts: dict[str, Any] = {}
    if save_kind == "kb" and content:
        from agent_os.capture.pipeline import _index_search_object

        async def _index_skill_doc(
            *,
            object_id: uuid.UUID,
            title: str,
            summary: str | None,
            tags_list: list[str],
        ) -> None:
            try:
                await _index_search_object(
                    db,
                    user_id=job.user_id,
                    workspace_id=job.workspace_id,
                    object_type="document",
                    object_id=object_id,
                    title=title,
                    summary=summary,
                    content=content,
                    tags=tags_list,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[jobs] skill_run SearchIndex upsert skipped (non-fatal): %s",
                    exc,
                )

        patch_existing = (
            doc_for_transform is not None and output_mode == "transform"
        )
        if patch_existing:
            primary = doc_for_transform
            primary.content = content
            primary.summary = _summary(content)
            primary.word_count = len(content)
            ex = dict(primary.extra or {})
            ex.update(
                {
                    "source": "skill_run_transform",
                    "skill_id": str(skill.id),
                    "job_id": str(job.id),
                }
            )
            primary.extra = ex  # type: ignore[assignment]
            await db.flush()
            chk = (
                await db.execute(
                    select(Chunk).where(
                        Chunk.document_id == primary.id,
                        Chunk.chunk_index == 0,
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if chk is None:
                db.add(
                    Chunk(
                        document_id=primary.id,
                        user_id=job.user_id,
                        source_id=primary.source_id,
                        chunk_index=0,
                        content=content,
                        token_count=_token_count(content),
                        extra={
                            "source": "skill_run_transform",
                            "job_id": str(job.id),
                        },
                    )
                )
            else:
                chk.content = content
                chk.source_id = primary.source_id
                chk.token_count = _token_count(content)
                cex = dict(chk.extra or {})
                cex.update(
                    {"source": "skill_run_transform", "job_id": str(job.id)}
                )
                chk.extra = cex  # type: ignore[assignment]
            await _index_skill_doc(
                object_id=primary.id,
                title=primary.title or skill.name,
                summary=primary.summary,
                tags_list=list(primary.tags or []),
            )
            extra_artifacts["document_id"] = str(primary.id)
            extra_artifacts["transformed"] = True
        else:
            document = Document(
                user_id=job.user_id,
                workspace_id=job.workspace_id,
                folder_id=getattr(doc_for_transform, "folder_id", None),
                title=(
                    f"{skill.name} · "
                    f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"
                ),
                summary=_summary(content),
                content=content,
                document_type=DocumentType.NOTE.value,
                status=DocumentStatus.READY.value,
                tags=["skill", skill.category or "skill", skill.name],
                word_count=len(content),
                extra={
                    "source": "skill_run",
                    "skill_id": str(skill.id),
                    "job_id": str(job.id),
                },
            )
            db.add(document)
            await db.flush()
            db.add(
                Chunk(
                    document_id=document.id,
                    user_id=job.user_id,
                    source_id=document.source_id,
                    chunk_index=0,
                    content=content,
                    token_count=_token_count(content),
                    extra={"source": "skill_run", "job_id": str(job.id)},
                )
            )
            await _index_skill_doc(
                object_id=document.id,
                title=document.title or skill.name,
                summary=document.summary,
                tags_list=list(document.tags or []),
            )
            extra_artifacts["document_id"] = str(document.id)

    job.progress = 90
    if skill_run is not None:
        skill_run.status = SkillRunStatus.COMPLETED.value
        # SkillRun.output should mirror what the user sees in the result
        # drawer: real LLM content + token usage + the artifact id when we
        # successfully wrote a Document. v1.4 frontend `/skills/runs/{id}`
        # poll renders these directly.
        skill_run.output = {**output_payload, **extra_artifacts}
        if extra_artifacts.get("document_id"):
            skill_run.output_object_type = "document"
            skill_run.output_object_id = extra_artifacts["document_id"]
        skill_run.completed_at = datetime.now(UTC)

    completed = await mark_job_completed(
        db,
        job.id,
        output={**output_payload, **extra_artifacts},
    )

    notif_obj_id: str | None = str(skill_run.id) if skill_run else None
    notif_title = f"Skill 运行完成 · {skill.name}"
    notif_body = (content[:160] + "…") if len(content) > 160 else content
    await create_notification(
        db,
        user_id=job.user_id,
        workspace_id=job.workspace_id,
        type=NotificationType.AI_OUTPUT_SAVED,
        title=notif_title,
        content=notif_body,
        object_type="skill_run",
        object_id=notif_obj_id,
    )

    return completed
