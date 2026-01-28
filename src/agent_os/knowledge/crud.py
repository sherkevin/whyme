"""CRUD operations for Knowledge management (Inbox and Cards)."""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update

from agent_os.knowledge.models import InboxItem, Card, PGVECTOR_AVAILABLE
from agent_os.knowledge.schema import (
    InboxItemCreate,
    InboxItemUpdate,
    CardCreate,
    CardUpdate,
)
from agent_os.knowledge.embeddings import generate_embedding_for_card


# =============================================================================
# Inbox CRUD Operations
# =============================================================================

async def create_inbox_item(db: AsyncSession, *, user_id: int, obj_in: InboxItemCreate) -> InboxItem:
    """Create a new inbox item.

    Args:
        db: Database session
        user_id: User ID
        obj_in: InboxItemCreate schema

    Returns:
        Created InboxItem
    """
    db_obj = InboxItem(
        user_id=user_id,
        content=obj_in.content,
        source=obj_in.source,
        extra_data=obj_in.extra_data,
        status="raw",  # Default status
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_inbox_item(db: AsyncSession, *, item_id: int, user_id: int) -> Optional[InboxItem]:
    """Get inbox item by ID.

    Args:
        db: Database session
        item_id: Inbox item ID
        user_id: User ID (for ownership check)

    Returns:
        InboxItem if found and belongs to user, None otherwise
    """
    result = await db.execute(
        select(InboxItem).filter(
            and_(InboxItem.id == item_id, InboxItem.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def get_inbox_items(
    db: AsyncSession,
    *,
    user_id: int,
    status: Optional[str] = None,
    source: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[List[InboxItem], int]:
    """Get inbox items with filtering and pagination.

    Args:
        db: Database session
        user_id: User ID
        status: Filter by status (raw, processed, archived)
        source: Filter by source (manual, api, import)
        skip: Number of items to skip
        limit: Max number of items to return

    Returns:
        Tuple of (list of InboxItems, total count)
    """
    # Build base query
    conditions = [InboxItem.user_id == user_id]
    if status:
        conditions.append(InboxItem.status == status)
    if source:
        conditions.append(InboxItem.source == source)

    # Get total count
    count_result = await db.execute(
        select(func.count(InboxItem.id)).filter(and_(*conditions))
    )
    total = count_result.scalar()

    # Get items with pagination and ordering
    result = await db.execute(
        select(InboxItem)
        .filter(and_(*conditions))
        .order_by(InboxItem.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()

    return list(items), total


async def update_inbox_item(
    db: AsyncSession,
    *,
    db_obj: InboxItem,
    obj_in: InboxItemUpdate | Dict[str, Any],
) -> InboxItem:
    """Update an inbox item.

    Args:
        db: Database session
        db_obj: Existing InboxItem
        obj_in: InboxItemUpdate schema or dict

    Returns:
        Updated InboxItem
    """
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if hasattr(db_obj, field):
            setattr(db_obj, field, value)

    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_inbox_item_status(
    db: AsyncSession,
    *,
    item_id: int,
    user_id: int,
    status: str,
) -> Optional[InboxItem]:
    """Update inbox item status.

    Args:
        db: Database session
        item_id: Inbox item ID
        user_id: User ID
        status: New status (raw, processed, archived)

    Returns:
        Updated InboxItem if found, None otherwise
    """
    db_obj = await get_inbox_item(db, item_id=item_id, user_id=user_id)
    if not db_obj:
        return None

    return await update_inbox_item(db, db_obj=db_obj, obj_in={"status": status})


async def delete_inbox_item(db: AsyncSession, *, item_id: int, user_id: int) -> bool:
    """Delete an inbox item.

    Args:
        db: Database session
        item_id: Inbox item ID
        user_id: User ID (for ownership check)

    Returns:
        True if deleted, False if not found
    """
    db_obj = await get_inbox_item(db, item_id=item_id, user_id=user_id)
    if not db_obj:
        return False

    await db.delete(db_obj)
    await db.commit()
    return True


# =============================================================================
# Card CRUD Operations
# =============================================================================

async def create_card(db: AsyncSession, *, user_id: int, obj_in: CardCreate) -> Card:
    """Create a new card with automatic embedding generation.

    Args:
        db: Database session
        user_id: User ID
        obj_in: CardCreate schema

    Returns:
        Created Card
    """
    # Generate embedding for the card
    embedding = None
    if PGVECTOR_AVAILABLE:
        embedding = generate_embedding_for_card(obj_in.title, obj_in.content)
        if embedding:
            import logging
            logging.info(f"Generated embedding for card: {obj_in.title}")

    db_obj = Card(
        user_id=user_id,
        title=obj_in.title,
        content=obj_in.content,
        para_type=obj_in.para_type,
        tags=obj_in.tags or [],
        source_inbox_item_id=obj_in.source_inbox_item_id,
        embedding=embedding,  # Set embedding
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_card(db: AsyncSession, *, card_id: int, user_id: int) -> Optional[Card]:
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
    user_id: int,
    para_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[List[Card], int]:
    """Get cards with filtering and pagination.

    Args:
        db: Database session
        user_id: User ID
        para_type: Filter by paragraph type (concept, action, reference)
        tags: Filter by tags (any match)
        skip: Number of cards to skip
        limit: Max number of cards to return

    Returns:
        Tuple of (list of Cards, total count)
    """
    # Build conditions
    conditions = [Card.user_id == user_id]
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
    obj_in: CardUpdate | Dict[str, Any],
) -> Card:
    """Update a card with automatic embedding regeneration.

    Args:
        db: Database session
        db_obj: Existing Card
        obj_in: CardUpdate schema or dict

    Returns:
        Updated Card
    """
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.model_dump(exclude_unset=True)

    # Check if title or content is being updated
    should_regenerate_embedding = False
    if "title" in update_data or "content" in update_data:
        should_regenerate_embedding = True

    # Update fields
    for field, value in update_data.items():
        if hasattr(db_obj, field):
            setattr(db_obj, field, value)

    # Regenerate embedding if title or content changed
    if should_regenerate_embedding and PGVECTOR_AVAILABLE:
        new_embedding = generate_embedding_for_card(db_obj.title, db_obj.content)
        if new_embedding:
            db_obj.embedding = new_embedding
            import logging
            logging.info(f"Regenerated embedding for card: {db_obj.title}")

    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_card(db: AsyncSession, *, card_id: int, user_id: int) -> bool:
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
    user_id: int,
    inbox_item_id: int,
) -> List[Card]:
    """Get all cards that originated from a specific inbox item.

    Args:
        db: Database session
        user_id: User ID
        inbox_item_id: Source inbox item ID

    Returns:
        List of Cards
    """
    result = await db.execute(
        select(Card).filter(
            and_(
                Card.user_id == user_id,
                Card.source_inbox_item_id == inbox_item_id
            )
        )
    )
    return list(result.scalars().all())
