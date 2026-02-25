"""FastAPI router for Knowledge management (Cards only).

Note: InboxItem endpoints are removed since we use PRD4 Item model instead.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from agent_os.db.base import get_db
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.knowledge import crud

# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# =============================================================================
# Card Schemas (simplified - moved from schema.py to avoid InboxItem references)
# =============================================================================

class CardBase(BaseModel):
    """Base schema for Card."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    para_type: str = Field(default="concept", description="Paragraph type (concept, action, reference)")
    tags: List[str] = Field(default_factory=list, description="Tags for the card")


class CardCreate(CardBase):
    """Schema for creating a Card."""
    source_inbox_item_id: Optional[uuid.UUID] = Field(None, description="Source Item ID")


class CardUpdate(BaseModel):
    """Schema for updating a Card."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    para_type: Optional[str] = Field(None, description="Paragraph type")
    tags: Optional[List[str]] = Field(None, description="Tags for the card")


class CardResponse(CardBase):
    """Schema for Card response."""
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    source_inbox_item_id: Optional[uuid.UUID] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CardList(BaseModel):
    """Schema for paginated Card list."""
    items: List[CardResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Card Endpoints
# =============================================================================

@router.post("/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_in: CardCreate,
) -> CardResponse:
    """Create a new card.

    Args:
        db: Database session
        current_user: Authenticated user
        card_in: Card data

    Returns:
        Created card
    """
    # Get user's default workspace
    workspace_id = current_user.id

    card_data = card_in.model_dump()
    card = await crud.create_card(
        db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        obj_in=card_data
    )
    # 自动写入搜索索引
    try:
        from agent_os.search_engine.models import SearchIndex
        search_entry = SearchIndex(
            item_type='card',
            item_id=card.id,
            title=card.title,
            content=card.content,
            tags=card.tags or [],
        )
        db.add(search_entry)
        await db.commit()
    except Exception:
        pass  # 索引失败不影响卡片创建
    return CardResponse(
        id=card.id,
        workspace_id=card.workspace_id,
        user_id=card.user_id,
        title=card.title,
        content=card.content,
        para_type=card.para_type,
        tags=card.tags or [],
        source_inbox_item_id=card.source_inbox_item_id,
        created_at=card.created_at.isoformat(),
        updated_at=card.updated_at.isoformat(),
    )


@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_id: str,
) -> CardResponse:
    """Get a card by ID.

    Args:
        db: Database session
        current_user: Authenticated user
        card_id: Card ID (UUID string)

    Returns:
        Card

    Raises:
        HTTPException 404: If card not found
    """
    card_uuid = uuid.UUID(card_id)
    card = await crud.get_card(db, card_id=card_uuid, user_id=current_user.id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    return CardResponse(
        id=card.id,
        workspace_id=card.workspace_id,
        user_id=card.user_id,
        title=card.title,
        content=card.content,
        para_type=card.para_type,
        tags=card.tags or [],
        source_inbox_item_id=card.source_inbox_item_id,
        created_at=card.created_at.isoformat(),
        updated_at=card.updated_at.isoformat(),
    )


@router.get("/cards", response_model=CardList)
async def list_cards(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    para_type: Optional[str] = Query(None, description="Filter by paragraph type (concept, action, reference)"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Cards per page"),
) -> CardList:
    """List cards with filtering and pagination.

    Args:
        db: Database session
        current_user: Authenticated user
        para_type: Optional paragraph type filter
        tags: Optional tags filter (comma-separated)
        page: Page number (1-indexed)
        page_size: Cards per page

    Returns:
        Paginated list of cards
    """
    # Parse tags if provided
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    skip = (page - 1) * page_size

    # Get user's default workspace
    workspace_id = current_user.id

    cards, total = await crud.get_cards(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        para_type=para_type,
        tags=tag_list,
        skip=skip,
        limit=page_size,
    )

    card_responses = [
        CardResponse(
            id=card.id,
            workspace_id=card.workspace_id,
            user_id=card.user_id,
            title=card.title,
            content=card.content,
            para_type=card.para_type,
            tags=card.tags or [],
            source_inbox_item_id=card.source_inbox_item_id,
            created_at=card.created_at.isoformat(),
            updated_at=card.updated_at.isoformat(),
        )
        for card in cards
    ]

    return CardList(items=card_responses, total=total, page=page, page_size=page_size)

@router.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_id: str,
    card_in: CardUpdate,
) -> CardResponse:
    """Update a card."""
    card_uuid = uuid.UUID(card_id)
    card = await crud.get_card(db, card_id=card_uuid, user_id=current_user.id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    update_data = card_in.model_dump(exclude_unset=True)
    card = await crud.update_card(db, db_obj=card, obj_in=update_data)
    return CardResponse(
        id=card.id,
        workspace_id=card.workspace_id,
        user_id=card.user_id,
        title=card.title,
        content=card.content,
        para_type=card.para_type,
        tags=card.tags or [],
        source_inbox_item_id=card.source_inbox_item_id,
        created_at=card.created_at.isoformat(),
        updated_at=card.updated_at.isoformat(),
    )

@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_id: str,
) -> None:
    """Delete a card.

    Args:
        db: Database session
        current_user: Authenticated user
        card_id: Card ID (UUID string)

    Raises:
        HTTPException 404: If card not found
    """
    card_uuid = uuid.UUID(card_id)
    success = await crud.delete_card(db, card_id=card_uuid, user_id=current_user.id)
    # 删除搜索索引
    try:
        from agent_os.search_engine.models import SearchIndex
        from sqlalchemy import select, and_
        result = await db.execute(
            select(SearchIndex).filter(
                and_(SearchIndex.item_type == 'card', SearchIndex.item_id == card_uuid)
            )
        )
        index_entry = result.scalar_one_or_none()
        if index_entry:
            await db.delete(index_entry)
            await db.commit()
    except Exception:
        pass
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
