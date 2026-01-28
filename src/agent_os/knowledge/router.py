"""FastAPI router for Knowledge management (Inbox and Cards)."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.base import get_db
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.knowledge import crud
from agent_os.knowledge.schema import (
    InboxItemCreate,
    InboxItemUpdate,
    InboxItemResponse,
    InboxItemList,
    CardCreate,
    CardUpdate,
    CardResponse,
    CardList,
)
from agent_os.knowledge.vector_search import search_cards_by_text, VectorSearchService


# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# =============================================================================
# Inbox Endpoints
# =============================================================================

@router.post("/inbox", response_model=InboxItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inbox_item(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_in: InboxItemCreate,
) -> InboxItemResponse:
    """Create a new inbox item.

    Args:
        db: Database session
        current_user: Authenticated user
        item_in: Inbox item data

    Returns:
        Created inbox item
    """
    item = await crud.create_inbox_item(db, user_id=current_user.id, obj_in=item_in)
    return item


@router.get("/inbox/{item_id}", response_model=InboxItemResponse)
async def get_inbox_item(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_id: int,
) -> InboxItemResponse:
    """Get an inbox item by ID.

    Args:
        db: Database session
        current_user: Authenticated user
        item_id: Inbox item ID

    Returns:
        Inbox item

    Raises:
        HTTPException 404: If item not found
    """
    item = await crud.get_inbox_item(db, item_id=item_id, user_id=current_user.id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )
    return item


@router.get("/inbox", response_model=InboxItemList)
async def list_inbox_items(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status (raw, processed, archived)"),
    source: Optional[str] = Query(None, description="Filter by source (manual, api, import)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> InboxItemList:
    """List inbox items with filtering and pagination.

    Args:
        db: Database session
        current_user: Authenticated user
        status: Optional status filter
        source: Optional source filter
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Paginated list of inbox items
    """
    skip = (page - 1) * page_size
    items, total = await crud.get_inbox_items(
        db,
        user_id=current_user.id,
        status=status,
        source=source,
        skip=skip,
        limit=page_size,
    )
    return InboxItemList(items=items, total=total, page=page, page_size=page_size)


@router.put("/inbox/{item_id}", response_model=InboxItemResponse)
async def update_inbox_item(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_id: int,
    item_in: InboxItemUpdate,
) -> InboxItemResponse:
    """Update an inbox item.

    Args:
        db: Database session
        current_user: Authenticated user
        item_id: Inbox item ID
        item_in: Update data

    Returns:
        Updated inbox item

    Raises:
        HTTPException 404: If item not found
    """
    db_obj = await crud.get_inbox_item(db, item_id=item_id, user_id=current_user.id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )

    updated_item = await crud.update_inbox_item(db, db_obj=db_obj, obj_in=item_in)
    return updated_item


@router.patch("/inbox/{item_id}/status", response_model=InboxItemResponse)
async def update_inbox_item_status(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_id: int,
    new_status: str = Query(..., description="New status (raw, processed, archived)"),
) -> InboxItemResponse:
    """Update inbox item status.

    Args:
        db: Database session
        current_user: Authenticated user
        item_id: Inbox item ID
        new_status: New status value

    Returns:
        Updated inbox item

    Raises:
        HTTPException 404: If item not found
        HTTPException 400: If status is invalid
    """
    # Validate status
    valid_statuses = ["raw", "processed", "archived"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    updated_item = await crud.update_inbox_item_status(
        db,
        item_id=item_id,
        user_id=current_user.id,
        status=new_status,
    )

    if not updated_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )

    return updated_item


@router.delete("/inbox/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inbox_item(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_id: int,
) -> None:
    """Delete an inbox item.

    Args:
        db: Database session
        current_user: Authenticated user
        item_id: Inbox item ID

    Raises:
        HTTPException 404: If item not found
    """
    success = await crud.delete_inbox_item(db, item_id=item_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )


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
    card = await crud.create_card(db, user_id=current_user.id, obj_in=card_in)
    return card


@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_id: int,
) -> CardResponse:
    """Get a card by ID.

    Args:
        db: Database session
        current_user: Authenticated user
        card_id: Card ID

    Returns:
        Card

    Raises:
        HTTPException 404: If card not found
    """
    card = await crud.get_card(db, card_id=card_id, user_id=current_user.id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    return card


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
    cards, total = await crud.get_cards(
        db,
        user_id=current_user.id,
        para_type=para_type,
        tags=tag_list,
        skip=skip,
        limit=page_size,
    )
    return CardList(items=cards, total=total, page=page, page_size=page_size)


@router.put("/cards/{card_id}", response_model=CardResponse)
async def update_card(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_id: int,
    card_in: CardUpdate,
) -> CardResponse:
    """Update a card.

    Args:
        db: Database session
        current_user: Authenticated user
        card_id: Card ID
        card_in: Update data

    Returns:
        Updated card

    Raises:
        HTTPException 404: If card not found
    """
    db_obj = await crud.get_card(db, card_id=card_id, user_id=current_user.id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )

    updated_card = await crud.update_card(db, db_obj=db_obj, obj_in=card_in)
    return updated_card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_id: int,
) -> None:
    """Delete a card.

    Args:
        db: Database session
        current_user: Authenticated user
        card_id: Card ID

    Raises:
        HTTPException 404: If card not found
    """
    success = await crud.delete_card(db, card_id=card_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )


# =============================================================================
# Vector Search Endpoints
# =============================================================================

class VectorSearchRequest(BaseModel):
    """Request schema for vector search."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query text")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    para_type: Optional[str] = Field(None, description="Filter by paragraph type")


class VectorSearchResultItem(BaseModel):
    """Single search result item."""
    card_id: int
    title: str
    content: str
    para_type: str
    similarity: float = Field(..., ge=0.0, le=1.0)


class VectorSearchResponse(BaseModel):
    """Response schema for vector search."""
    query: str
    results: List[VectorSearchResultItem]
    total: int


@router.post("/cards/search", response_model=VectorSearchResponse)
async def vector_search_cards(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search_req: VectorSearchRequest,
) -> VectorSearchResponse:
    """Search cards using vector similarity.

    Performs semantic search using vector embeddings to find cards
    that are semantically similar to the query text.

    Args:
        db: Database session
        current_user: Authenticated user
        search_req: Search request with query and filters

    Returns:
        Search results with similarity scores

    Example:
        ```python
        {
            "query": "python async programming",
            "limit": 10,
            "para_type": null
        }
        ```
    """
    # Perform vector search
    results = await search_cards_by_text(
        db,
        user_id=current_user.id,
        query_text=search_req.query,
        limit=search_req.limit,
        para_type_filter=search_req.para_type,
    )

    # Convert to response format
    result_items = [
        VectorSearchResultItem(
            card_id=r.card_id,
            title=r.title,
            content=r.content,
            para_type=r.para_type,
            similarity=r.similarity,
        )
        for r in results
    ]

    return VectorSearchResponse(
        query=search_req.query,
        results=result_items,
        total=len(result_items),
    )


@router.get("/cards/{card_id}/similar", response_model=VectorSearchResponse)
async def find_similar_cards(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_id: int,
    limit: int = Query(5, ge=1, le=20, description="Maximum number of similar cards"),
) -> VectorSearchResponse:
    """Find cards similar to a given card.

    Uses vector embeddings to find cards that are semantically
    similar to the specified card.

    Args:
        db: Database session
        current_user: Authenticated user
        card_id: Reference card ID
        limit: Maximum number of results

    Returns:
        Similar cards with similarity scores

    Raises:
        HTTPException 404: If reference card not found
    """
    # Get reference card
    reference_card = await crud.get_card(db, card_id=card_id, user_id=current_user.id)
    if not reference_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reference card not found"
        )

    # Find similar cards
    results = await VectorSearchService.search_similar_cards(
        db,
        card_id=card_id,
        user_id=current_user.id,
        limit=limit,
    )

    # Convert to response format
    result_items = [
        VectorSearchResultItem(
            card_id=r.card_id,
            title=r.title,
            content=r.content,
            para_type=r.para_type,
            similarity=r.similarity,
        )
        for r in results
    ]

    return VectorSearchResponse(
        query=f"Similar to card: {reference_card.title}",
        results=result_items,
        total=len(result_items),
    )
