"""PRD10 ``/api/v1/feed`` and ``/api/v1/cards/*`` endpoints (§9).

Cards are the unit of the home feed. Soft delete is the default.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.ai.llm_provider import is_llm_enabled
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.capture.llm_pipeline import enrich_capture_with_llm
from agent_os.common import ApiErrorCode, paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.kb.models import Document
from agent_os.knowledge.models import Card
from agent_os.search_engine.models import SearchIndex

router = APIRouter(prefix="/api/v1", tags=["Feed"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CardCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    summary: str | None = None
    content: str = Field(..., min_length=1)
    content_type: str = Field(default="note", max_length=50)
    tags: list[str] = Field(default_factory=list)
    folder_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    inbox_item_id: uuid.UUID | None = None


class CardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = None
    content: str | None = Field(default=None, min_length=1)
    content_type: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
    folder_id: uuid.UUID | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None


class FavoriteRequest(BaseModel):
    is_favorite: bool = True


# ---------------------------------------------------------------------------
# Feed endpoint
# ---------------------------------------------------------------------------


@router.get("/feed")
async def get_feed(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    view: Literal["card", "list", "table"] = Query(default="card"),
    type: str | None = Query(default=None),
    sort_by: Literal["created_at", "updated_at"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    tag: str | None = Query(default=None),
    date_range: Literal["today", "week", "month", "all"] = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    base_filters = [
        Card.user_id == current_user.id,
        Card.is_archived.is_(False),
        Card.deleted_at.is_(None),
    ]
    base = select(Card).where(*base_filters)
    count_base = select(func.count(Card.id)).where(*base_filters)

    if type:
        base = base.where(Card.content_type == type)
        count_base = count_base.where(Card.content_type == type)

    if date_range != "all":
        cutoff = _date_range_to_cutoff(date_range)
        base = base.where(Card.created_at >= cutoff)
        count_base = count_base.where(Card.created_at >= cutoff)

    if tag:
        # Cross-database safe: cast tags JSON to text and use LIKE.
        from sqlalchemy import String, cast

        base = base.where(cast(Card.tags, String).ilike(f"%{tag}%"))
        count_base = count_base.where(cast(Card.tags, String).ilike(f"%{tag}%"))

    sort_column = getattr(Card, sort_by)
    base = base.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())

    total = (await db.execute(count_base)).scalar_one() or 0
    rows = (
        await db.execute(base.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    facets = await _compute_facets(db, current_user.id)

    return paginated_response(
        [card.to_feed_dict() for card in rows],
        page=page,
        page_size=page_size,
        total=int(total),
        extra={"facets": facets, "view": view},
        request=request,
    )


# ---------------------------------------------------------------------------
# Card endpoints
# ---------------------------------------------------------------------------


@router.get("/cards/{card_id}")
async def get_card(
    card_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await _load_owned_card(db, card_id, current_user.id)
    payload = card.to_prd10_dict()
    payload["content"] = card.content
    payload["ai_summary"] = await _card_ai_summary_meta(db, card)
    return success_response(payload, request=request)


@router.post("/cards/{card_id}/ai-summary")
async def generate_card_ai_summary(
    card_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate a card title/summary/tags through the real LLM path.

    This endpoint exists specifically to prevent the UI from presenting a
    copied raw-content prefix as an "AI summary". When LLM is unavailable we
    return a visible failure instead of fabricating a fallback summary.
    """

    if not is_llm_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "LLM_DISABLED",
                "message": "LLM API is not configured; cannot generate a real AI summary.",
            },
        )

    card = await _load_owned_card(db, card_id, current_user.id)
    enrichment = await enrich_capture_with_llm(
        db,
        user_id=current_user.id,
        content=card.content or card.summary or card.title,
        fallback_title=card.title,
        hint_tags=list(card.tags or []),
        target_folder_id=card.folder_id,
    )
    if not getattr(enrichment, "used_llm", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "LLM_UNAVAILABLE",
                "message": "LLM provider did not return a real summary.",
            },
        )

    card.title = enrichment.title or card.title
    card.summary = enrichment.summary or card.summary
    card.tags = enrichment.tags or card.tags
    card.entities = enrichment.entities or card.entities
    if enrichment.folder_id is not None:
        card.folder_id = enrichment.folder_id
    if enrichment.content_type in {"note", "task", "question", "decision", "insight"}:
        card.content_type = enrichment.content_type

    for doc in await _find_card_documents(db, card):
        doc.title = enrichment.title or doc.title
        doc.summary = enrichment.summary or doc.summary
        doc.tags = enrichment.tags or doc.tags
        if enrichment.folder_id is not None:
            doc.folder_id = enrichment.folder_id
        extra = dict(doc.extra or {})
        extra.update(
            {
                "llm_used": True,
                "model": getattr(enrichment, "model", "") or "",
                "summary_source": "llm",
            }
        )
        doc.extra = extra

    index_rows = (
        await db.execute(
            select(SearchIndex).where(
                SearchIndex.user_id == current_user.id,
                SearchIndex.item_type.in_(["card", "document"]),
            )
        )
    ).scalars().all()
    doc_ids = {str(d.id) for d in await _find_card_documents(db, card)}
    for row in index_rows:
        if str(row.item_id) == str(card.id) or str(row.item_id) in doc_ids:
            row.title = card.title
            row.summary = card.summary
            row.tags = list(card.tags or [])

    await db.commit()
    await db.refresh(card)
    payload = card.to_prd10_dict()
    payload["content"] = card.content
    payload["ai_summary"] = {
        "used_llm": True,
        "model": getattr(enrichment, "model", "") or "",
        "source": "llm",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return success_response(payload, request=request)


@router.post("/cards", status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: CardCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = Card(
        user_id=current_user.id,
        title=payload.title,
        content=payload.content,
        summary=payload.summary,
        content_type=payload.content_type,
        tags=list(payload.tags or []),
        folder_id=payload.folder_id,
        source_id=payload.source_id,
        inbox_item_id=payload.inbox_item_id,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    out = card.to_prd10_dict()
    out["content"] = card.content
    return success_response(out, request=request)


@router.patch("/cards/{card_id}")
async def update_card(
    card_id: uuid.UUID,
    payload: CardUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await _load_owned_card(db, card_id, current_user.id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(card, key, value)
    await db.commit()
    await db.refresh(card)
    out = card.to_prd10_dict()
    out["content"] = card.content
    return success_response(out, request=request)


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await _load_owned_card(db, card_id, current_user.id)
    card.deleted_at = datetime.now(UTC)
    await db.commit()
    return success_response({"id": str(card.id), "deleted": True}, request=request)


@router.post("/cards/{card_id}/favorite")
async def favorite_card(
    card_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    payload: FavoriteRequest = Body(default=FavoriteRequest()),
):
    card = await _load_owned_card(db, card_id, current_user.id)
    card.is_favorite = payload.is_favorite
    await db.commit()
    await db.refresh(card)
    return success_response(card.to_prd10_dict(), request=request)


class CardMoveRequest(BaseModel):
    target_folder_id: uuid.UUID | None = None


@router.post("/cards/{card_id}/move")
async def move_card(
    card_id: uuid.UUID,
    payload: CardMoveRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Move a card to another folder (or out of any folder when ``target_folder_id`` is null).

    Validates that the destination folder belongs to the same user. Mirrors
    PRD10 §10.4 / §9 contract used by the SPA's drag-and-drop and folder
    sidebar quick actions.
    """

    from agent_os.kb.models import Folder

    card = await _load_owned_card(db, card_id, current_user.id)
    if payload.target_folder_id is not None:
        folder = (
            await db.execute(
                select(Folder).where(
                    Folder.id == payload.target_folder_id,
                    Folder.user_id == current_user.id,
                    Folder.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if folder is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NOT_FOUND",
                    "message": "Target folder not found",
                },
            )
    card.folder_id = payload.target_folder_id
    await db.commit()
    await db.refresh(card)
    out = card.to_prd10_dict()
    out["content"] = card.content
    return success_response(out, request=request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_owned_card(
    db: AsyncSession,
    card_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Card:
    card = (
        await db.execute(
            select(Card).where(
                Card.id == card_id,
                Card.user_id == user_id,
                Card.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Card not found",
            },
        )
    return card


async def _find_card_documents(db: AsyncSession, card: Card) -> list[Document]:
    """Best-effort mirror lookup for KB documents created from a feed card."""

    rows = (
        await db.execute(
            select(Document).where(
                Document.user_id == card.user_id,
                Document.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    matches: list[Document] = []
    card_content = (card.content or "").strip()
    for doc in rows:
        extra = doc.extra or {}
        by_inbox = card.inbox_item_id and str(extra.get("inbox_item_id") or "") == str(card.inbox_item_id)
        by_source = card.source_id and doc.source_id == card.source_id
        by_content = card_content and (doc.content or "").strip() == card_content
        if by_inbox or by_source or by_content:
            matches.append(doc)
    return matches


async def _card_ai_summary_meta(db: AsyncSession, card: Card) -> dict:
    docs = await _find_card_documents(db, card)
    used_llm = False
    model = ""
    source = "unknown"
    for doc in docs:
        extra = doc.extra or {}
        if bool(extra.get("llm_used")) or extra.get("summary_source") == "llm":
            used_llm = True
            model = str(extra.get("model") or "")
            source = "llm"
            break
    return {"used_llm": used_llm, "model": model, "source": source}


async def _compute_facets(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """PRD10 §9.1 ``facets`` block: type counts (and a placeholder for tags)."""

    type_rows = (
        await db.execute(
            select(Card.content_type, func.count(Card.id))
            .where(
                Card.user_id == user_id,
                Card.is_archived.is_(False),
                Card.deleted_at.is_(None),
            )
            .group_by(Card.content_type)
        )
    ).all()

    type_facets = [
        {"value": row[0] or "note", "label": row[0] or "note", "count": int(row[1])}
        for row in type_rows
    ]
    tag_rows = (
        await db.execute(
            select(Card.tags).where(
                Card.user_id == user_id,
                Card.is_archived.is_(False),
                Card.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    tag_counts: dict[str, int] = {}
    for tags in tag_rows:
        tags_iter = [tags] if isinstance(tags, str) else list(tags or [])
        for raw_tag in tags_iter:
            tag = str(raw_tag or "").strip()
            if not tag:
                continue
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    tag_facets = [
        {"value": tag, "label": tag, "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {"types": type_facets, "tags": tag_facets}


def _date_range_to_cutoff(value: str) -> datetime:
    now = datetime.now(UTC)
    if value == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if value == "week":
        return now - timedelta(days=7)
    if value == "month":
        return now - timedelta(days=30)
    return now - timedelta(days=365 * 100)


__all__ = ["router"]
