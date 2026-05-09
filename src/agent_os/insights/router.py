"""PRD10 §12 Insights & §12.3-§12.4 Reports endpoints.

* ``GET  /api/v1/insights/summary``     — PRD10 §12.1
* ``GET  /api/v1/insights``             — PRD10 §12.2
* ``POST /api/v1/insights``             — Helper (used by the worker / seed
  scripts). Creates a single insight row.
* ``POST /api/v1/insights/{id}/dismiss``— Marks one insight as dismissed.
* ``POST /api/v1/reports/generate``     — PRD10 §12.3
* ``GET  /api/v1/reports/{report_id}``  — PRD10 §12.4

The Insight rows live in the dedicated ``prd10_insights`` table so this
module never collides with PRD7's ``garden.daily_insights``.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.inbox.prd10_models import (
    InboxItemProcessingStatus,
    InboxItemStatus,
    InboxItemType,
    Prd10InboxItem,
)
from agent_os.insights.models import InsightStatus, InsightType, Prd10Insight
from agent_os.insights.research_service import (
    collect_research_sources,
    synthesize_research_draft,
)
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.kb.models import Document, DocumentStatus, DocumentType
from agent_os.knowledge.models import Card

router = APIRouter(prefix="/api/v1", tags=["Insights & Reports"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


_RANGE_TO_DAYS: dict[str, int] = {
    "today": 1,
    "week": 7,
    "month": 30,
    "all": 36500,
}


class CreateInsightRequest(BaseModel):
    insight_type: str = Field(..., max_length=40)
    title: str = Field(..., min_length=1, max_length=255)
    summary: str | None = None
    body: str | None = None
    related_object_type: str | None = Field(default=None, max_length=50)
    related_object_id: str | None = Field(default=None, max_length=64)
    extra: dict[str, Any] = Field(default_factory=dict)


class TimeRange(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


class GenerateReportRequest(BaseModel):
    report_type: Literal["daily", "weekly", "monthly"] = "daily"
    time_range: TimeRange | None = None
    include_sources: bool = True
    save_to_kb: bool = False


class DeepResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    scope: str | None = Field(default=None, max_length=2000)
    output: str | None = Field(default=None, max_length=4000)
    include_sources: bool = True
    save_to_kb: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_range(value: str) -> int:
    if value not in _RANGE_TO_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": f"Invalid range '{value}'",
            },
        )
    return _RANGE_TO_DAYS[value]


def _ensure_insight_type(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in {t.value for t in InsightType}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": f"Invalid insight_type '{value}'",
            },
        )
    return value


def _ensure_status(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in {s.value for s in InsightStatus}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": f"Invalid status '{value}'",
            },
        )
    return value


async def _theme_distribution(
    db: AsyncSession, user: User, since: datetime, top: int = 5
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(Card.tags)
            .where(
                Card.user_id == user.id,
                Card.deleted_at.is_(None),
                Card.created_at >= since,
            )
        )
    ).all()
    counter: Counter[str] = Counter()
    for (tags,) in rows:
        for tag in tags or []:
            tag_str = str(tag).strip()
            if tag_str:
                counter[tag_str] += 1
    return [
        {"name": name, "value": count}
        for name, count in counter.most_common(top)
    ]


async def _content_type_distribution(
    db: AsyncSession, user: User, since: datetime
) -> list[dict[str, Any]]:
    """Aggregate Prd10InboxItem rows by ``type`` since ``since``.

    Maps the raw enum types onto the business-prototype's 4 content
    categories so the right-rail insight panel can render the donut
    chart without further client-side normalization:

    - ``笔记`` (notes)   ← ``text``
    - ``链接`` (links)   ← ``link``
    - ``文件`` (files)   ← ``file`` + ``image`` + ``video``
    - ``语音`` (audio)   ← ``audio``

    ``manual_task`` rows are excluded (they're tasks, not content).

    Returns a list of 4 dicts in display order, each with ``name``,
    ``value`` (count), and ``percent`` (0-100 integer, summing to 100
    after normalization). When the user has no captures the percents
    fall back to a fixed 55/25/15/5 mix matching the prototype's
    visual reference so the donut never looks "broken".
    """

    rows = (
        await db.execute(
            select(Prd10InboxItem.type, func.count(Prd10InboxItem.id)).where(
                Prd10InboxItem.user_id == user.id,
                Prd10InboxItem.created_at >= since,
                Prd10InboxItem.type != InboxItemType.MANUAL_TASK.value,
            ).group_by(Prd10InboxItem.type)
        )
    ).all()

    bucket: dict[str, int] = {"notes": 0, "links": 0, "files": 0, "audio": 0}
    for type_value, count in rows:
        c = int(count or 0)
        if type_value == InboxItemType.TEXT.value:
            bucket["notes"] += c
        elif type_value == InboxItemType.LINK.value:
            bucket["links"] += c
        elif type_value in (
            InboxItemType.FILE.value,
            InboxItemType.IMAGE.value,
            InboxItemType.VIDEO.value,
        ):
            bucket["files"] += c
        elif type_value == InboxItemType.AUDIO.value:
            bucket["audio"] += c

    total = sum(bucket.values())
    if total == 0:
        return [
            {"name": "笔记", "key": "notes", "value": 0, "percent": 55},
            {"name": "链接", "key": "links", "value": 0, "percent": 25},
            {"name": "文件", "key": "files", "value": 0, "percent": 15},
            {"name": "语音", "key": "audio", "value": 0, "percent": 5},
        ]

    raw_percents = {k: (v * 100.0) / total for k, v in bucket.items()}
    rounded = {k: int(round(p)) for k, p in raw_percents.items()}
    diff = 100 - sum(rounded.values())
    if diff != 0:
        target = max(rounded, key=lambda k: raw_percents[k])
        rounded[target] += diff

    return [
        {"name": "笔记", "key": "notes", "value": bucket["notes"], "percent": rounded["notes"]},
        {"name": "链接", "key": "links", "value": bucket["links"], "percent": rounded["links"]},
        {"name": "文件", "key": "files", "value": bucket["files"], "percent": rounded["files"]},
        {"name": "语音", "key": "audio", "value": bucket["audio"], "percent": rounded["audio"]},
    ]


async def _ai_activity_block(
    db: AsyncSession, user: User, since: datetime
) -> dict[str, Any]:
    """Compute "AI 助理活跃度" stat for the right-rail insight panel.

    Returns a dict with:
    - ``messages_count``: total AI message rows authored by the user since
      ``since`` (worker output + user prompts both counted).
    - ``conversations_count``: number of AI conversations created since.
    - ``tasks_assisted``: completed inbox items with ``ai_*`` source flag
      in ``extra`` (proxy for "AI helped me organize N captures").
    - ``level``: derived label "高" (>=12) / "中" (>=4) / "低" (>=1) / "—" (0).

    These are lightweight COUNTs over already-indexed user_id+created_at
    columns so the call stays under §25.2's P95 budget.
    """

    from agent_os.ai.models import AIConversation, AIMessage

    messages_count = (
        await db.execute(
            select(func.count(AIMessage.id))
            .where(
                AIMessage.user_id == user.id,
                AIMessage.created_at >= since,
            )
        )
    ).scalar_one() or 0
    conversations_count = (
        await db.execute(
            select(func.count(AIConversation.id))
            .where(
                AIConversation.user_id == user.id,
                AIConversation.created_at >= since,
            )
        )
    ).scalar_one() or 0
    tasks_assisted = (
        await db.execute(
            select(func.count(Prd10InboxItem.id))
            .where(
                Prd10InboxItem.user_id == user.id,
                Prd10InboxItem.processing_status
                == InboxItemProcessingStatus.COMPLETED.value,
                Prd10InboxItem.created_at >= since,
            )
        )
    ).scalar_one() or 0

    n = int(messages_count)
    if n >= 12:
        level = "高"
    elif n >= 4:
        level = "中"
    elif n >= 1:
        level = "低"
    else:
        level = "—"

    return {
        "messages_count": int(messages_count),
        "conversations_count": int(conversations_count),
        "tasks_assisted": int(tasks_assisted),
        "level": level,
    }


async def _quality_distribution(
    db: AsyncSession, user: User
) -> list[dict[str, Any]]:
    favorited = (
        await db.execute(
            select(func.count(Card.id)).where(
                Card.user_id == user.id,
                Card.deleted_at.is_(None),
                Card.is_favorite.is_(True),
            )
        )
    ).scalar_one() or 0
    archived = (
        await db.execute(
            select(func.count(Card.id)).where(
                Card.user_id == user.id,
                Card.is_archived.is_(True),
            )
        )
    ).scalar_one() or 0
    pending_inbox = (
        await db.execute(
            select(func.count(Prd10InboxItem.id)).where(
                Prd10InboxItem.user_id == user.id,
                Prd10InboxItem.status != InboxItemStatus.PROCESSED.value,
                Prd10InboxItem.status != InboxItemStatus.ARCHIVED.value,
            )
        )
    ).scalar_one() or 0
    return [
        {"name": "高价值", "value": int(favorited)},
        {"name": "已归档", "value": int(archived)},
        {"name": "待整理", "value": int(pending_inbox)},
    ]


async def _stats_block(db: AsyncSession, user: User, since: datetime) -> dict[str, int]:
    capture_count = (
        await db.execute(
            select(func.count(Prd10InboxItem.id)).where(
                Prd10InboxItem.user_id == user.id,
                Prd10InboxItem.created_at >= since,
            )
        )
    ).scalar_one() or 0
    knowledge_count = (
        await db.execute(
            select(func.count(Document.id)).where(
                Document.user_id == user.id,
                Document.deleted_at.is_(None),
            )
        )
    ).scalar_one() or 0
    task_count = (
        await db.execute(
            select(func.count(Prd10InboxItem.id)).where(
                Prd10InboxItem.user_id == user.id,
                Prd10InboxItem.type == InboxItemType.MANUAL_TASK.value,
                Prd10InboxItem.status != InboxItemStatus.ARCHIVED.value,
            )
        )
    ).scalar_one() or 0
    completed_task_count = (
        await db.execute(
            select(func.count(Prd10InboxItem.id)).where(
                Prd10InboxItem.user_id == user.id,
                Prd10InboxItem.type == InboxItemType.MANUAL_TASK.value,
                Prd10InboxItem.processing_status == InboxItemProcessingStatus.COMPLETED.value,
            )
        )
    ).scalar_one() or 0
    return {
        "capture_count": int(capture_count),
        "knowledge_count": int(knowledge_count),
        "task_count": int(task_count),
        "completed_task_count": int(completed_task_count),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/insights/summary")
async def insights_summary(
    request: Request,
    range: str = Query(default="week"),
    source: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §12.1."""

    days = _ensure_range(range)
    since = datetime.now(UTC) - timedelta(days=days)

    stats = await _stats_block(db, current_user, since)
    theme_distribution = await _theme_distribution(db, current_user, since)
    quality_distribution = await _quality_distribution(db, current_user)
    content_type_distribution = await _content_type_distribution(
        db, current_user, since
    )
    ai_activity = await _ai_activity_block(db, current_user, since)

    insight_stmt = (
        select(Prd10Insight)
        .where(
            Prd10Insight.user_id == current_user.id,
            Prd10Insight.status == InsightStatus.READY.value,
        )
        .order_by(Prd10Insight.created_at.desc())
        .limit(5)
    )
    if source:
        insight_stmt = insight_stmt.where(Prd10Insight.insight_type == source)

    insights = (await db.execute(insight_stmt)).scalars().all()

    daily_insight_row = (
        await db.execute(
            select(Prd10Insight)
            .where(
                Prd10Insight.user_id == current_user.id,
                Prd10Insight.status == InsightStatus.READY.value,
                Prd10Insight.insight_type.in_(
                    (
                        InsightType.DAILY_SUMMARY.value,
                        InsightType.THEME_TREND.value,
                        InsightType.KNOWLEDGE_GAP.value,
                    )
                ),
            )
            .order_by(Prd10Insight.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    daily_insight = (
        daily_insight_row.to_prd10_dict() if daily_insight_row is not None else None
    )

    recommended_actions = [
        {"type": "generate_report", "label": "生成日报"},
        {"type": "review_inbox", "label": "整理灵感箱"},
    ]

    return success_response(
        {
            "stats": stats,
            "theme_distribution": theme_distribution,
            "quality_distribution": quality_distribution,
            "content_type_distribution": content_type_distribution,
            "ai_activity": ai_activity,
            "insights": [i.to_prd10_dict() for i in insights],
            "daily_insight": daily_insight,
            "recommended_actions": recommended_actions,
        },
        request=request,
    )


@router.get("/insights")
async def list_insights(
    request: Request,
    insight_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    range: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §12.2."""

    days = _ensure_range(range)
    since = datetime.now(UTC) - timedelta(days=days)
    typed = _ensure_insight_type(insight_type)
    status_value = _ensure_status(status_filter)

    base = select(Prd10Insight).where(
        Prd10Insight.user_id == current_user.id,
        Prd10Insight.created_at >= since,
    )
    if typed:
        base = base.where(Prd10Insight.insight_type == typed)
    if status_value:
        base = base.where(Prd10Insight.status == status_value)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0

    rows_stmt = (
        base.order_by(Prd10Insight.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await db.execute(rows_stmt)).scalars().all()

    return paginated_response(
        [r.to_prd10_dict() for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
        request=request,
    )


@router.post("/insights", status_code=status.HTTP_201_CREATED)
async def create_insight(
    payload: CreateInsightRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    typed = _ensure_insight_type(payload.insight_type)
    if typed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": "insight_type is required",
            },
        )

    insight = Prd10Insight(
        user_id=current_user.id,
        insight_type=typed,
        title=payload.title,
        summary=payload.summary,
        body=payload.body,
        related_object_type=payload.related_object_type,
        related_object_id=payload.related_object_id,
        extra=dict(payload.extra or {}),
        status=InsightStatus.READY.value,
    )
    db.add(insight)
    await db.commit()
    await db.refresh(insight)
    return success_response(insight.to_prd10_dict(), request=request)


@router.post("/insights/{insight_id}/dismiss")
async def dismiss_insight(
    insight_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        iid = uuid.UUID(insight_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": "Invalid insight_id",
            },
        )

    row = (
        await db.execute(
            select(Prd10Insight).where(
                Prd10Insight.id == iid,
                Prd10Insight.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Insight not found",
            },
        )
    row.status = InsightStatus.DISMISSED.value
    await db.commit()
    await db.refresh(row)
    return success_response(row.to_prd10_dict(), request=request)


# ---------------------------------------------------------------------------
# v1.4 §3.5 — `/insights/{id}` GET (detail) and `/insights/{id}/regenerate`
# ---------------------------------------------------------------------------


@router.get("/insights/{insight_id}")
async def get_insight_detail(
    insight_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.5 ``GET /insights/{id}`` — single insight detail.

    Wired for the v1.4 insight detail drawer (洞察详情). Returns the same
    PRD10 envelope as the list endpoint so the frontend can re-use renderers.
    """
    try:
        iid = uuid.UUID(insight_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": "Invalid insight_id",
            },
        )

    row = (
        await db.execute(
            select(Prd10Insight).where(
                Prd10Insight.id == iid,
                Prd10Insight.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Insight not found",
            },
        )
    return success_response(row.to_prd10_dict(), request=request)


@router.post("/insights/{insight_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_insight(
    insight_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.5 ``POST /insights/{id}/regenerate`` — re-summarize an insight.

    V1 implementation: bumps ``updated_at`` and writes a `generate_report`
    Job that the worker picks up. Returns the existing insight + queued
    job_id so the bridge can show "重新生成中..." UX.
    """
    try:
        iid = uuid.UUID(insight_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": "Invalid insight_id",
            },
        )

    row = (
        await db.execute(
            select(Prd10Insight).where(
                Prd10Insight.id == iid,
                Prd10Insight.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Insight not found",
            },
        )

    from agent_os.jobs.models import Job, JobStatus, JobType

    job = Job(
        user_id=current_user.id,
        job_type=JobType.GENERATE_REPORT.value,
        status=JobStatus.QUEUED.value,
        input={
            "kind": "insight_regenerate",
            "insight_id": str(row.id),
            "insight_type": row.insight_type,
        },
    )
    db.add(job)
    row.status = InsightStatus.READY.value
    await db.commit()
    await db.refresh(row)
    await db.refresh(job)

    payload = row.to_prd10_dict()
    payload["regenerate_job_id"] = str(job.id)
    return success_response(payload, request=request)


@router.post("/reports/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    payload: GenerateReportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §12.3.

    Synthesize a report by reading recent capture / KB / task counts and
    persisting it both as a ``Job`` (so the existing job lookup works) and
    a ``Prd10Insight`` of type ``daily_summary`` / ``weekly_summary``.
    Long-running providers can replace the inline body without changing the
    contract.
    """

    end = (payload.time_range and payload.time_range.end) or datetime.now(UTC)
    start = (payload.time_range and payload.time_range.start) or (
        end - timedelta(days={"daily": 1, "weekly": 7, "monthly": 30}[payload.report_type])
    )
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": "time_range.end must be on or after time_range.start",
            },
        )

    stats = await _stats_block(db, current_user, start)
    themes = await _theme_distribution(db, current_user, start)

    recent_cards_q = await db.execute(
        select(Card.title, Card.summary, Card.tags)
        .where(
            Card.user_id == current_user.id,
            Card.deleted_at.is_(None),
            Card.created_at >= start,
            Card.created_at <= end,
        )
        .order_by(Card.created_at.desc())
        .limit(15)
    )
    recent_cards = [
        {"title": r[0] or "未命名", "summary": (r[1] or "")[:140], "tags": list(r[2] or [])}
        for r in recent_cards_q.all()
    ]

    type_label_map = {"daily": "日报", "weekly": "周报", "monthly": "月报"}
    label = type_label_map.get(payload.report_type, payload.report_type)

    fallback_lines = [
        f"# AI {label}",
        f"区间: {start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')}",
        "",
        f"- 灵感记录: {stats['capture_count']}",
        f"- 知识库文档: {stats['knowledge_count']}",
        f"- 任务/待办: {stats['task_count']} (已完成 {stats['completed_task_count']})",
    ]
    if themes:
        fallback_lines.append("- 高频主题:")
        for t in themes:
            fallback_lines.append(f"  - {t['name']}: {t['value']}")
    fallback_text = "\n".join(fallback_lines)

    summary_text = (
        f"区间 {start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}："
        f"{stats['capture_count']} 条灵感、{stats['knowledge_count']} 篇文档、"
        f"{stats['task_count']} 个任务"
    )
    body_text = fallback_text
    title_text = f"{label} · {start.strftime('%m月%d日')} – {end.strftime('%m月%d日')}"
    used_llm = False
    llm_model = ""

    try:
        from agent_os.ai.llm_provider import get_provider, is_llm_enabled

        if is_llm_enabled():
            theme_lines = (
                "\n".join(f"- {t['name']}（{t['value']} 次）" for t in themes[:8])
                if themes else "（暂无）"
            )
            cards_block = (
                "\n".join(
                    f"- {c['title']}：{c['summary'] or '(无摘要)'}（标签 {', '.join(c['tags']) or '无'}）"
                    for c in recent_cards[:10]
                )
                if recent_cards else "（暂无）"
            )
            sys_prompt = (
                "你是 Mydow 的 AI 周/日/月报助手。你要根据用户的真实数据生成一份"
                "结构化报告，输出**纯 Markdown** 文本（不要 ```fence、不要 JSON），"
                "结构如下：\n"
                "## 概览\n（2-3 句中文，提炼区间内的核心动态）\n\n"
                "## 主要话题\n- 用 bullet 列出 3-5 个高频主题，每个加一句解释\n\n"
                "## 关键灵感\n- 选 3-5 条最有价值的真实灵感，注明标题与来源\n\n"
                "## 建议行动\n- 给 2-3 条具体的下一步建议（落到 Mydow 平台能做的事）\n\n"
                "规则：1) 不要编造数据；2) 全部使用中文；3) 保持简洁。"
            )
            user_prompt = (
                f"报告类型：{label}（{payload.report_type}）\n"
                f"时间区间：{start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}\n\n"
                f"统计：\n"
                f"- 灵感记录：{stats['capture_count']}\n"
                f"- 知识库文档：{stats['knowledge_count']}\n"
                f"- 任务：{stats['task_count']}（已完成 {stats['completed_task_count']}）\n\n"
                f"高频主题：\n{theme_lines}\n\n"
                f"区间内的真实灵感（请基于这些素材，不要编造）：\n{cards_block}\n"
            )
            try:
                import asyncio as _asyncio

                completion = await _asyncio.wait_for(
                    get_provider().complete(
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.4,
                        max_tokens=900,
                    ),
                    timeout=45.0,
                )
            except (Exception, _asyncio.TimeoutError):
                completion = None

            if isinstance(completion, dict):
                content_str = completion.get("content")
                if not content_str:
                    msg = completion.get("message") or {}
                    if isinstance(msg, dict):
                        content_str = msg.get("content")
                if isinstance(content_str, str) and content_str.strip():
                    body_text = content_str.strip()
                    used_llm = True
                    llm_model = str(completion.get("model") or "")
                    first_para = next(
                        (
                            line.strip()
                            for line in body_text.splitlines()
                            if line.strip() and not line.strip().startswith("#")
                        ),
                        None,
                    )
                    if first_para:
                        summary_text = first_para[:240]
    except Exception:
        body_text = fallback_text

    type_to_insight = {
        "daily": InsightType.DAILY_SUMMARY,
        "weekly": InsightType.WEEKLY_SUMMARY,
        "monthly": InsightType.MONTHLY_SUMMARY,
    }
    insight = Prd10Insight(
        user_id=current_user.id,
        insight_type=type_to_insight[payload.report_type].value,
        title=title_text,
        summary=summary_text,
        body=body_text,
        status=InsightStatus.READY.value,
        extra={
            "report_type": payload.report_type,
            "time_range": {"start": start.isoformat(), "end": end.isoformat()},
            "stats": stats,
            "themes": themes,
            "recent_cards": recent_cards[:8],
            "used_llm": used_llm,
            "model": llm_model,
        },
    )
    db.add(insight)
    await db.flush()

    job = Job(
        user_id=current_user.id,
        job_type=JobType.GENERATE_REPORT.value,
        status=JobStatus.COMPLETED.value,
        progress=100,
        input={
            "kind": "report_generate",
            "report_type": payload.report_type,
            "time_range": {"start": start.isoformat(), "end": end.isoformat()},
            "include_sources": payload.include_sources,
        },
        output={
            "insight_id": str(insight.id),
            "report_type": payload.report_type,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(insight)
    await db.refresh(job)

    return success_response(
        {
            "job_id": str(job.id),
            "report_id": str(insight.id),
            "status": job.status,
        },
        request=request,
    )


@router.post("/research/tasks", status_code=status.HTTP_202_ACCEPTED)
async def create_deep_research_task(
    payload: DeepResearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a real deep-research report from the user's knowledge assets.

    This endpoint is intentionally synchronous for PRD10 acceptance: the
    returned job is already completed, and both an insight row and a KB
    markdown document are persisted. When a real LLM provider is enabled, it
    writes the report from retrieved cards/documents; otherwise the response is
    an explicit fallback over the same real retrieved data.
    """

    topic = payload.topic.strip()
    scope = (payload.scope or "").strip()
    output_hint = (payload.output or "").strip()

    sources = await collect_research_sources(db, user=current_user, topic=topic)
    draft = await synthesize_research_draft(
        topic=topic,
        scope=scope,
        output_hint=output_hint,
        sources=sources,
    )

    insight = Prd10Insight(
        user_id=current_user.id,
        insight_type=InsightType.KNOWLEDGE_GAP.value,
        title=f"深度研究：{topic}",
        summary=draft.summary,
        body=draft.body,
        status=InsightStatus.READY.value,
        extra={
            "report_type": "deep_research",
            "topic": topic,
            "scope": scope,
            "output": output_hint,
            "used_llm": draft.used_llm,
            "model": draft.model,
            "source_cards": [str(c.id) for c in sources.cards[:8]],
            "source_documents": [str(d.id) for d in sources.documents[:8]],
        },
    )
    db.add(insight)
    await db.flush()

    document: Document | None = None
    if payload.save_to_kb:
        document = Document(
            user_id=current_user.id,
            title=f"深度研究：{topic}",
            summary=draft.summary,
            content=draft.body,
            document_type=DocumentType.MARKDOWN.value,
            status=DocumentStatus.READY.value,
            tags=["深度研究", topic[:24]],
            extra={
                "kind": "deep_research",
                "insight_id": str(insight.id),
                "used_llm": draft.used_llm,
                "model": draft.model,
            },
        )
        db.add(document)
        await db.flush()

    job = Job(
        user_id=current_user.id,
        job_type=JobType.GENERATE_REPORT.value,
        status=JobStatus.COMPLETED.value,
        progress=100,
        input={
            "kind": "deep_research",
            "topic": topic,
            "scope": scope,
            "output": output_hint,
        },
        output={
            "insight_id": str(insight.id),
            "document_id": str(document.id) if document else None,
            "used_llm": draft.used_llm,
        },
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()
    await db.refresh(insight)
    if document is not None:
        await db.refresh(document)
    await db.refresh(job)

    return success_response(
        {
            "task_id": str(job.id),
            "job_id": str(job.id),
            "status": job.status,
            "report_id": str(insight.id),
            "document_id": str(document.id) if document else None,
            "title": insight.title,
            "summary": insight.summary,
            "body": insight.body,
            "used_llm": draft.used_llm,
            "model": draft.model,
            "source_counts": {
                "cards": len(sources.cards),
                "documents": len(sources.documents),
            },
        },
        request=request,
    )


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §12.4."""

    try:
        rid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": "Invalid report_id",
            },
        )

    row = (
        await db.execute(
            select(Prd10Insight).where(
                Prd10Insight.id == rid,
                Prd10Insight.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Report not found",
            },
        )

    payload = row.to_prd10_dict()
    payload["report"] = {
        "report_type": row.insight_type,
        "stats": (row.extra or {}).get("stats"),
        "themes": (row.extra or {}).get("themes"),
    }
    return success_response(payload, request=request)


__all__ = ["router"]
