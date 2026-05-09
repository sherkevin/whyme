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

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.knowledge.models import Card

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
