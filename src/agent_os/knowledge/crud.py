"""CRUD operations for Knowledge management (Cards)."""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import uuid

from agent_os.knowledge.models import Card


# =============================================================================
# Card CRUD Operations
# =============================================================================

async def create_card(db: AsyncSession, *, user_id: uuid.UUID, workspace_id: uuid.UUID, obj_in: Dict[str, Any]) -> Card:
    """Create a new card.

    Args:
        db: Database session
        user_id: User ID
        workspace_id: Workspace ID
        obj_in: Card creation data

    Returns:
        Created Card
    """
    db_obj = Card(
        user_id=user_id,
        workspace_id=workspace_id,
        title=obj_in.get("title", "Untitled"),
        content=obj_in.get("content", ""),
        para_type=obj_in.get("para_type", "concept"),
        tags=obj_in.get("tags", []),
        source_inbox_item_id=obj_in.get("source_inbox_item_id"),
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_card(db: AsyncSession, *, card_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Card]:
    """Get card by ID.

    Args:
        db: Database session
        card_id: Card ID
        user_id: User ID (for ownership check)

    Returns:
        Card if found and belongs to user, None otherwise
    """
    result = await db.execute(
        select(Card).filter(
            and_(Card.id == card_id, Card.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def get_cards(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    para_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[List[Card], int]:
    """Get cards with filtering and pagination.

    Args:
        db: Database session
        workspace_id: Workspace ID
        user_id: User ID
        para_type: Filter by paragraph type (concept, action, reference)
        tags: Filter by tags (any match)
        skip: Number of cards to skip
        limit: Max number of cards to return

    Returns:
        Tuple of (list of Cards, total count)
    """
    # Build conditions
    conditions = [Card.workspace_id == workspace_id, Card.user_id == user_id]
    if para_type:
        conditions.append(Card.para_type == para_type)
    if tags:
        # Filter cards that have ANY of the specified tags (OR logic)
        # Use JSON contains for PostgreSQL/SQLite compatibility
        tag_conditions = [Card.tags.contains(tag) for tag in tags]
        conditions.append(or_(*tag_conditions))

    # Get total count
    count_result = await db.execute(
        select(func.count(Card.id)).filter(and_(*conditions))
    )
    total = count_result.scalar()

    # Get cards with pagination and ordering
    result = await db.execute(
        select(Card)
        .filter(and_(*conditions))
        .order_by(Card.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    cards = result.scalars().all()

    return list(cards), total


async def update_card(
    db: AsyncSession,
    *,
    db_obj: Card,
    obj_in: Dict[str, Any],
) -> Card:
    """Update a card.

    Args:
        db: Database session
        db_obj: Existing Card
        obj_in: Update data

    Returns:
        Updated Card
    """
    # Update fields
    for field, value in obj_in.items():
        if hasattr(db_obj, field):
            setattr(db_obj, field, value)

    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_card(db: AsyncSession, *, card_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Delete a card.

    Args:
        db: Database session
        card_id: Card ID
        user_id: User ID (for ownership check)

    Returns:
        True if deleted, False if not found
    """
    db_obj = await get_card(db, card_id=card_id, user_id=user_id)
    if not db_obj:
        return False

    await db.delete(db_obj)
    await db.commit()
    return True


async def get_cards_by_inbox_source(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    inbox_item_id: uuid.UUID,
) -> List[Card]:
    """Get all cards that originated from a specific inbox item.

    Args:
        db: Database session
        workspace_id: Workspace ID
        user_id: User ID
        inbox_item_id: Source inbox item ID

    Returns:
        List of Cards
    """
    result = await db.execute(
        select(Card).filter(
            and_(
                Card.workspace_id == workspace_id,
                Card.user_id == user_id,
                Card.source_inbox_item_id == inbox_item_id
            )
        )
    )
    return list(result.scalars().all())
