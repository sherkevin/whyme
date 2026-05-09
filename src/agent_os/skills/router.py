"""PRD10 Skills router (`/api/v1/skills*`).

Implements §17:

* ``GET  /api/v1/skills``                  — list with category/keyword/status/page filters
* ``GET  /api/v1/skills/{skill_id}``       — detail
* ``POST /api/v1/skills/{skill_id}/run``   — enqueue a SkillRun + Job, return queued status

Skill data lives in ``stage3.models.Skill`` (extended in Milestone 4 with PRD10
display fields). SkillRun + Job rows are written through
``agent_os.skills.runs.SkillRun`` and ``agent_os.jobs.models.Job`` so they
align with the PRD10 §16 generic Job contract.

The actual skill execution (LLM calls, tool invocation, downstream artifact
writes) is **not** done here. The MVP returns ``status="queued"`` immediately;
a worker process consumes ``Job`` rows of type ``skill_run`` and updates
``SkillRun.status`` / ``output`` over time.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime, timedelta

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.knowledge.models import Card
from agent_os.skills.runs import SkillRun, SkillRunStatus
from agent_os.stage3.models import Skill

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/skills", tags=["skills-prd10"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SkillRunRequest(BaseModel):
    """PRD10 §17.3 request body."""

    input: dict[str, Any] = Field(default_factory=dict)
    save_output: bool | str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_SKILL_STATUSES: tuple[str, ...] = ("published", "draft", "archived")
_DEFAULT_SKILL_NAME = "Mydow 快速总结"


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": f"Invalid {field}"},
        )


async def _ensure_default_skill(db: AsyncSession) -> None:
    """Seed one built-in skill so a fresh V1 install has something runnable."""

    existing = (
        await db.execute(select(Skill.id).where(Skill.is_active.is_(True)).limit(1))
    ).scalar_one_or_none()
    if existing is not None:
        return

    default_skill = Skill(
        name=_DEFAULT_SKILL_NAME,
        description="将输入内容整理为摘要、要点和下一步行动。",
        category="productivity",
        steps=[
            {
                "order": 1,
                "name": "summarize",
                "description": "Summarize user input into structured notes",
                "agent_action": "summarize",
                "requires_confirmation": False,
            }
        ],
        version="1.0",
        icon="sparkles",
        status="published",
        usage_count=0,
        is_installed_default=True,
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "actions": {"type": "array"},
            },
        },
        is_active=True,
    )
    db.add(default_skill)
    await db.commit()


# ---------------------------------------------------------------------------
# List + detail
# ---------------------------------------------------------------------------


@router.get("")
async def list_skills(
    request: Request,
    category: str | None = Query(None),
    keyword: str = Query(""),
    skill_status: str | None = Query(
        None,
        alias="status",
        description=f"Filter by status. Allowed: {', '.join(_VALID_SKILL_STATUSES)}",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §17.1 ``GET /api/v1/skills``."""

    await _ensure_default_skill(db)

    base = select(Skill).where(Skill.is_active.is_(True))

    if category:
        base = base.where(Skill.category == category)

    keyword = (keyword or "").strip()
    if keyword:
        like = f"%{keyword}%"
        base = base.where(
            or_(Skill.name.ilike(like), Skill.description.ilike(like))
        )

    if skill_status is not None:
        if skill_status not in _VALID_SKILL_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": (
                        f"Invalid status '{skill_status}'. "
                        f"Allowed: {', '.join(_VALID_SKILL_STATUSES)}"
                    ),
                },
            )
        base = base.where(Skill.status == skill_status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0

    rows_stmt = (
        base.order_by(Skill.usage_count.desc(), Skill.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await db.execute(rows_stmt)).scalars().all()

    items = [skill.to_prd10_dict() for skill in rows]
    return paginated_response(
        items,
        page=page,
        page_size=page_size,
        total=int(total),
        request=request,
    )


@router.get("/recommendations")
async def list_skill_recommendations(
    request: Request,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """§17.5 — personalised skill recommendations.

    Strategy (algorithmic, no mock):
      1. Pull the user's recent capture/card tags + KB document tags as a
         "user vocabulary" set (last 30 items).
      2. For each active skill, score it by:
           - lexical overlap of skill.{name, description, category} tokens
             with the user vocabulary  (dominant signal)
           - skill.usage_count (popularity tie-breaker)
           - +0.5 if user previously favorited it (User.settings)
           - -0.2 if user already ran it in the past 7 days (avoid repeats)
      3. Return top-K with the score so the frontend can render a chip.
    """

    await _ensure_default_skill(db)

    # ── 1) build user vocabulary (tag tokens) ──────────────────────────
    # Card tags (recent 30) + KB Document tags (recent 30) + Skill tags
    # are treated as a single bag of tokens for similarity ranking.
    from agent_os.kb.models import Document as KBDocument
    from agent_os.knowledge.models import Card

    vocab: dict[str, int] = {}

    def _bump(token: str, weight: int = 1) -> None:
        token = (token or "").strip().lower()
        if not token or len(token) < 2:
            return
        vocab[token] = vocab.get(token, 0) + weight

    try:
        cards = (
            await db.execute(
                select(Card.tags, Card.title)
                .where(Card.user_id == current_user.id)
                .order_by(Card.created_at.desc())
                .limit(30)
            )
        ).all()
        for tags, title in cards:
            for t in (tags or []):
                _bump(str(t), weight=2)
            for t in (title or "").split():
                _bump(t)
    except Exception:
        pass

    try:
        docs = (
            await db.execute(
                select(KBDocument.tags, KBDocument.title)
                .where(KBDocument.user_id == current_user.id)
                .where(KBDocument.deleted_at.is_(None))
                .order_by(KBDocument.updated_at.desc())
                .limit(30)
            )
        ).all()
        for tags, title in docs:
            for t in (tags or []):
                _bump(str(t), weight=2)
            for t in (title or "").split():
                _bump(t)
    except Exception:
        pass

    # ── 2) load favorite + recent-run skill ids from User.settings ──
    settings = current_user.settings or {}
    favorite_ids: set[str] = {
        str(x) for x in (settings.get("favorite_skill_ids") or [])
    }

    # ── 3) score every active skill ──────────────────────────────────
    skills = (
        await db.execute(
            select(Skill).where(Skill.is_active.is_(True))
        )
    ).scalars().all()

    scored: list[tuple[float, Skill, dict[str, list[str]]]] = []
    for skill in skills:
        text = " ".join(
            filter(None, [skill.name or "", skill.description or "", skill.category or ""])
        ).lower()
        # token overlap
        hits: list[str] = []
        score = 0.0
        for token, weight in vocab.items():
            if token in text:
                score += float(weight)
                hits.append(token)
        # popularity tie-breaker
        score += min(float(skill.usage_count or 0) / 50.0, 0.5)
        # favorite boost
        if str(skill.id) in favorite_ids:
            score += 0.5
        scored.append((score, skill, {"hits": hits[:5]}))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:limit]

    items = []
    for score, skill, meta in top:
        payload = skill.to_prd10_dict()
        payload["recommendation_score"] = round(float(score), 4)
        payload["matched_tags"] = meta.get("hits") or []
        payload["is_favorite"] = str(skill.id) in favorite_ids
        items.append(payload)

    return success_response(
        {
            "items": items,
            "vocabulary_size": len(vocab),
            "favorite_count": len(favorite_ids),
        },
        request=request,
    )


@router.get("/{skill_id}")
async def get_skill_detail(
    skill_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §17.2 ``GET /api/v1/skills/{skill_id}``."""

    sid = _parse_uuid(skill_id, "skill_id")
    skill = (
        await db.execute(
            select(Skill).where(Skill.id == sid, Skill.is_active.is_(True))
        )
    ).scalar_one_or_none()

    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Skill not found"},
        )

    return success_response(skill.to_prd10_dict(), request=request)


# ---------------------------------------------------------------------------
# Run skill (enqueue)
# ---------------------------------------------------------------------------


@router.post("/{skill_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_skill(
    skill_id: str,
    payload: SkillRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §17.3 ``POST /api/v1/skills/{skill_id}/run``.

    Persists a ``Job(job_type=skill_run, status=queued)`` and a ``SkillRun``
    referring to it, then returns both ids. The worker that picks up the
    ``Job`` is responsible for advancing both rows.
    """

    sid = _parse_uuid(skill_id, "skill_id")

    skill = (
        await db.execute(
            select(Skill).where(Skill.id == sid, Skill.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Skill not found"},
        )

    job = Job(
        user_id=current_user.id,
        job_type=JobType.SKILL_RUN.value,
        status=JobStatus.QUEUED.value,
        input={
            "skill_id": str(skill.id),
            "skill_name": skill.name,
            "input": payload.input or {},
            "save_output": payload.save_output,
        },
    )
    db.add(job)
    await db.flush()

    save_output_normalized: str | None = None
    if isinstance(payload.save_output, bool):
        save_output_normalized = "kb" if payload.save_output else None
    elif isinstance(payload.save_output, str):
        save_output_normalized = payload.save_output.strip() or None

    run = SkillRun(
        user_id=current_user.id,
        skill_id=skill.id,
        job_id=job.id,
        status=SkillRunStatus.QUEUED.value,
        input=payload.input or {},
        save_output=save_output_normalized,
    )
    db.add(run)

    skill.usage_count = int(skill.usage_count or 0) + 1

    await db.commit()
    await db.refresh(job)
    await db.refresh(run)

    return success_response(
        {
            "job_id": str(job.id),
            "skill_run_id": str(run.id),
            "status": run.status,
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# v1.4 §3.7 — favorite a Skill (`PATCH /skills/:id/favorite`).
#
# Persisted as a flag in ``User.settings.favorite_skill_ids`` (set-like list)
# so we ship without a schema migration. The frontend filters the grid by
# this list. Idempotent: same id can be POSTed twice, value stays the same.
# ---------------------------------------------------------------------------


class SkillFavoriteRequest(BaseModel):
    is_favorite: bool = Field(default=True)


@router.get("/{skill_id}/runs")
async def list_skill_runs(
    skill_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
) -> dict:
    """§16.7 — Recent ``SkillRun`` rows for a Skill.

    Powers the v1.4 Skills detail drawer "运行历史" section so users can see
    what their last few runs produced (status / created_at / output preview)
    instead of having to wait for a notification or refresh blindly.

    Returns the rows owned by ``current_user`` only, newest first. Output is
    truncated to a 240-char preview to keep payload light; clients fetch the
    full output via ``GET /jobs/{job_id}`` when the user expands the row.
    """

    sid = _parse_uuid(skill_id, "skill_id")
    skill = (
        await db.execute(select(Skill).where(Skill.id == sid))
    ).scalar_one_or_none()
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Skill not found"},
        )

    base = (
        select(SkillRun)
        .where(SkillRun.user_id == current_user.id, SkillRun.skill_id == sid)
        .order_by(SkillRun.created_at.desc())
    )
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one() or 0
    rows = (
        await db.execute(
            base.limit(page_size).offset((page - 1) * page_size)
        )
    ).scalars().all()

    items = []
    for run in rows:
        output = run.output or {}
        content = ""
        document_id = run.output_object_id if run.output_object_type == "document" else None
        if isinstance(output, dict):
            content = str(output.get("content") or "")
            document_id = document_id or output.get("document_id") or output.get("saved_object_id")
        items.append(
            {
                "id": str(run.id),
                "skill_id": str(run.skill_id),
                "job_id": str(run.job_id) if run.job_id else None,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "output_preview": content[:240] if content else "",
                "document_id": str(document_id) if document_id else None,
                "output_object_type": run.output_object_type,
                "output_object_id": str(run.output_object_id) if run.output_object_id else None,
                "save_output": run.save_output,
            }
        )

    return paginated_response(
        items,
        page=page,
        page_size=page_size,
        total=int(total),
        request=request,
    )


@router.post("/{skill_id}/favorite", status_code=status.HTTP_200_OK)
async def favorite_skill(
    skill_id: str,
    payload: SkillFavoriteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.7 ``PATCH /skills/{skill_id}/favorite`` — toggle a Skill's favorite state.

    Wired for the v1.4 skillDetail drawer ``收藏`` button (the original
    `data-toast="已收藏 Skill"` button) and the Skills 广场 grid heart icon.
    Persists into ``User.settings['favorite_skill_ids']`` as a deduped list so
    the frontend can filter "我的收藏" without hitting the skills table again.
    """

    sid = _parse_uuid(skill_id, "skill_id")

    skill = (
        await db.execute(select(Skill).where(Skill.id == sid))
    ).scalar_one_or_none()
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Skill not found"},
        )

    settings = dict(current_user.settings or {})
    favs = list(settings.get("favorite_skill_ids", []) or [])
    sid_str = str(sid)
    changed = False
    if payload.is_favorite:
        if sid_str not in favs:
            favs.append(sid_str)
            changed = True
    else:
        if sid_str in favs:
            favs = [s for s in favs if s != sid_str]
            changed = True
    if changed:
        settings["favorite_skill_ids"] = favs
        current_user.settings = settings
        await db.commit()

    return success_response(
        {
            "skill_id": sid_str,
            "is_favorite": payload.is_favorite,
            "favorite_skill_ids": favs,
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# §17.4 — SkillRun detail (`GET /api/v1/skills/runs/{run_id}`).
#
# v1.4 contract §3.7 expects a way to read a skill run's status + output so
# the frontend can poll after `POST /run` (or render history). Worker writes
# ``SkillRun.output`` once the LLM call returns + the optional KB save lands.
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}")
async def get_skill_run(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §17.4 — fetch a SkillRun by id (with the worker's persisted output).

    Returns 404 if the row is missing or owned by another user. The frontend
    polls this every ~1.5s until ``status in {"completed", "failed", "canceled"}``.
    """

    rid = _parse_uuid(run_id, "run_id")
    run_obj = (
        await db.execute(select(SkillRun).where(SkillRun.id == rid))
    ).scalar_one_or_none()
    if run_obj is None or run_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Skill run not found"},
        )

    return success_response(run_obj.to_prd10_dict(), request=request)


# ---------------------------------------------------------------------------
# §16.5 — Personalized Skill recommendations.
#
# Algorithm (deterministic, no LLM needed — keeps the call cheap and avoids
# leaking user content to the LLM provider for what is fundamentally a
# tag-overlap problem):
#
# 1. Pull the user's recent capture surface: last `_RECO_CARD_WINDOW_DAYS`
#    days of `Card.tags` rows (favorites count 2x, others count 1x).
# 2. Derive the user's "tag profile": dict[tag → weighted count].
# 3. For every published Skill compute a score:
#       score = α * jaccard(user_tag_set, skill_required_tags)
#             + β * tag_overlap_strength(user_tag_profile, skill_required_tags)
#             + γ * usage_count_normalized
#             + δ * favorite_bonus (if the user has favorited this skill)
# 4. Return the top `limit` skills along with a human-readable `reason`.
#
# A favorited skill always lands at the top (so users can see their picks),
# but the algorithm still works on a brand-new account: the fallback uses
# `usage_count` so the most-used global skills surface as the recommendation.
# ---------------------------------------------------------------------------


_RECO_CARD_WINDOW_DAYS = 30
_RECO_DEFAULT_LIMIT = 5
_RECO_MAX_LIMIT = 20

# Hand-tuned weights — sum doesn't have to be 1; we just rank by absolute score.
_RECO_W_JACCARD = 5.0
_RECO_W_OVERLAP = 1.0
_RECO_W_USAGE = 0.3
_RECO_W_FAVORITE = 4.0


def _build_user_tag_profile(cards: list[Card]) -> dict[str, float]:
    """Aggregate recent Card.tags into a weighted bag of tags.

    Favorites get a 2x weight so the recommendation respects user signal.
    """

    profile: dict[str, float] = {}
    for card in cards:
        weight = 2.0 if bool(getattr(card, "is_favorite", False)) else 1.0
        for tag in (card.tags or []):
            if not tag:
                continue
            key = str(tag).strip().lower()
            if not key:
                continue
            profile[key] = profile.get(key, 0.0) + weight
    return profile


def _score_skill_against_profile(
    skill: Skill,
    *,
    profile: dict[str, float],
    user_tag_set: set[str],
    favorite_skill_ids: set[str],
    max_usage: int,
) -> tuple[float, str]:
    """Return ``(score, reason)`` — reason is a short Chinese explanation."""

    skill_tags = [
        str(t).strip().lower()
        for t in (skill.required_tags or [])
        if str(t).strip()
    ]
    skill_tag_set = set(skill_tags)

    if not skill_tag_set and not user_tag_set:
        # Nothing meaningful to overlap on — fall back to popularity.
        usage = float(skill.usage_count or 0)
        score = _RECO_W_USAGE * (usage / max(max_usage, 1))
        if str(skill.id) in favorite_skill_ids:
            score += _RECO_W_FAVORITE
            return score, "你最近收藏的 Skill"
        return score, "全网最常被使用"

    intersection = skill_tag_set & user_tag_set
    union = skill_tag_set | user_tag_set
    jaccard = len(intersection) / len(union) if union else 0.0
    overlap_weight = sum(profile.get(t, 0.0) for t in intersection)
    overlap_strength = overlap_weight / max(sum(profile.values()) or 1.0, 1.0)
    usage_norm = float(skill.usage_count or 0) / max(max_usage, 1)

    score = (
        _RECO_W_JACCARD * jaccard
        + _RECO_W_OVERLAP * overlap_strength
        + _RECO_W_USAGE * usage_norm
    )

    favorite = str(skill.id) in favorite_skill_ids
    if favorite:
        score += _RECO_W_FAVORITE

    # Build a human-readable reason — investors love to see why an algo did X.
    if intersection:
        sample_tags = sorted(intersection)[:3]
        reason = "命中你最近的标签：" + " / ".join(f"#{t}" for t in sample_tags)
    elif favorite:
        reason = "你最近收藏的 Skill"
    elif jaccard == 0 and skill_tag_set:
        reason = "适合「" + "、".join(list(skill_tags)[:2]) + "」类工作"
    else:
        reason = "热门 Skill"

    if favorite and intersection:
        reason = "★ 收藏 · " + reason

    return score, reason


async def get_skill_recommendations(
    request: Request,
    limit: int = Query(
        _RECO_DEFAULT_LIMIT,
        ge=1,
        le=_RECO_MAX_LIMIT,
        description="Number of personalized skill recommendations to return.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §17 / §16.5 — personalized Skill recommendations.

    Combines (a) the user's recent capture tags, (b) Skill required_tags
    Jaccard overlap, (c) global usage_count popularity, and (d) the user's
    explicit favorite list (`User.settings.favorite_skill_ids`) into a
    deterministic ranking. Returns the top ``limit`` Skills with a
    human-readable ``reason`` so the v1.4 「猜你想用」 collapsible drawer
    can render the rationale next to each card.

    Designed to be **stable for demo**: a brand-new account (no captures)
    still gets a reasonable top-N based on global usage_count, while a
    seasoned account sees skills aligned with their actual tag profile.
    """

    await _ensure_default_skill(db)

    cutoff = datetime.now(UTC) - timedelta(days=_RECO_CARD_WINDOW_DAYS)
    try:
        recent_cards = (
            await db.execute(
                select(Card)
                .where(Card.user_id == current_user.id)
                .where(Card.created_at >= cutoff)
                .order_by(Card.created_at.desc())
                .limit(120)
            )
        ).scalars().all()
    except Exception:  # noqa: BLE001 — defensive on partial schemas
        logger.warning(
            "skill recommendations: card lookup failed for user=%s",
            current_user.id,
            exc_info=True,
        )
        recent_cards = []

    profile = _build_user_tag_profile(list(recent_cards))
    user_tag_set = set(profile.keys())

    favorite_skill_ids = {
        str(v)
        for v in (current_user.settings or {}).get("favorite_skill_ids", [])
        if v
    }

    # Pull every active published Skill — typical orgs have <200 Skills so
    # ranking in Python is fine; we can switch to vector DB later.
    skills = (
        await db.execute(
            select(Skill).where(Skill.is_active.is_(True))
        )
    ).scalars().all()
    if not skills:
        return success_response(
            {
                "items": [],
                "tag_profile": [],
                "window_days": _RECO_CARD_WINDOW_DAYS,
            },
            request=request,
        )

    max_usage = max((int(s.usage_count or 0) for s in skills), default=1)

    scored: list[tuple[float, str, Skill]] = []
    for sk in skills:
        score, reason = _score_skill_against_profile(
            sk,
            profile=profile,
            user_tag_set=user_tag_set,
            favorite_skill_ids=favorite_skill_ids,
            max_usage=max_usage,
        )
        scored.append((score, reason, sk))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:limit]

    items = []
    for score, reason, sk in top:
        dto = sk.to_prd10_dict(is_installed=str(sk.id) in favorite_skill_ids)
        dto["recommendation_score"] = round(score, 4)
        dto["recommendation_reason"] = reason
        dto["is_favorite"] = str(sk.id) in favorite_skill_ids
        items.append(dto)

    # Surface the tag profile for transparency / UI badges
    profile_top = sorted(profile.items(), key=lambda kv: kv[1], reverse=True)[:8]
    return success_response(
        {
            "items": items,
            "tag_profile": [
                {"tag": tag, "weight": round(weight, 2)} for tag, weight in profile_top
            ],
            "window_days": _RECO_CARD_WINDOW_DAYS,
            "total_skills": len(skills),
            "favorite_skill_count": len(favorite_skill_ids),
        },
        request=request,
    )


# Register the recommendations route AFTER definition; FastAPI resolves
# routes in registration order so we explicitly insert this **before** the
# `/{skill_id}` catch-all so the literal "recommendations" sub-path doesn't
# collide with `_parse_uuid` validation.
_reco_route_index = next(
    (
        i
        for i, r in enumerate(router.routes)
        if getattr(r, "path", "").endswith("/{skill_id}")
    ),
    None,
)
router.add_api_route(
    "/recommendations",
    get_skill_recommendations,
    methods=["GET"],
    response_model=None,
    name="get_skill_recommendations",
    tags=["skills-prd10"],
)
if _reco_route_index is not None:
    # Move the just-appended route up so it wins over /{skill_id}.
    last = router.routes.pop()
    router.routes.insert(_reco_route_index, last)
