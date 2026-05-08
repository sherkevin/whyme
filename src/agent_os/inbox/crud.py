"""CRUD operations for Inbox module.

Inbox items are Items with type='inbox' or other raw input types.
This module provides specialized CRUD operations for inbox management.
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item


async def create_inbox_item(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    creator_id: uuid.UUID,
    title: str | None,
    content: str | None,
    source_type: str = "manual",
    source_meta: dict[str, Any] = None,
    item_type: str = "note"
) -> Item:
    """Create a new inbox item.

    Args:
        db: Database session
        workspace_id: Workspace ID
        creator_id: User ID who creates this item
        title: Item title
        content: Item content
        source_type: Source type (manual, wechat, chrome_extension, etc.)
        source_meta: Source metadata
        item_type: Item type (note, task, resource)

    Returns:
        Created item object
    """
    if source_meta is None:
        source_meta = {}

    item = Item(
        workspace_id=workspace_id,
        creator_id=creator_id,
        type=item_type,
        title=title,
        content=content,
        source_type=source_type,
        source_meta=source_meta,
        status="active"
    )

    db.add(item)
    await db.commit()
    await db.refresh(item)

    return item


async def get_inbox_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    workspace_id: uuid.UUID
) -> Item | None:
    """Get an inbox item by ID.

    Args:
        db: Database session
        item_id: Item ID
        workspace_id: Workspace ID (for access control)

    Returns:
        Item object or None
    """
    result = await db.execute(
        select(Item)
        .filter(
            and_(
                Item.id == item_id,
                Item.workspace_id == workspace_id
            )
        )
    )
    return result.scalar_one_or_none()


async def list_inbox_items(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    status: str | None = None,
    item_type: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0
) -> tuple[list[Item], int]:
    """List inbox items with filters.

    Args:
        db: Database session
        workspace_id: Workspace ID
        status: Filter by status
        item_type: Filter by item type
        source_type: Filter by source type
        search: Search in title and content
        limit: Max items to return
        offset: Offset for pagination

    Returns:
        Tuple of (items list, total count)
    """
    # Build query
    conditions = [Item.workspace_id == workspace_id]

    if status:
        conditions.append(Item.status == status)

    if item_type:
        conditions.append(Item.type == item_type)

    if source_type:
        conditions.append(Item.source_type == source_type)

    if search:
        search_term = f"%{search}%"
        conditions.append(
            or_(
                Item.title.ilike(search_term),
                Item.content.ilike(search_term)
            )
        )

    # Get total count
    count_query = select(Item.id).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Get items with pagination
    query = (
        select(Item)
        .where(and_(*conditions))
        .order_by(Item.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    items = result.scalars().all()

    return list(items), total


async def update_inbox_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    workspace_id: uuid.UUID,
    title: str | None = None,
    content: str | None = None,
    item_type: str | None = None
) -> Item | None:
    """Update an inbox item.

    Args:
        db: Database session
        item_id: Item ID
        workspace_id: Workspace ID
        title: New title
        content: New content
        item_type: New item type

    Returns:
        Updated item object or None
    """
    # Get item
    item = await get_inbox_item(db, item_id, workspace_id)
    if not item:
        return None

    # Update fields
    if title is not None:
        item.title = title
    if content is not None:
        item.content = content
    if item_type is not None:
        item.type = item_type

    await db.commit()
    await db.refresh(item)

    return item


async def update_inbox_item_status(
    db: AsyncSession,
    item_id: uuid.UUID,
    workspace_id: uuid.UUID,
    status: str
) -> Item | None:
    """Update inbox item status.

    Args:
        db: Database session
        item_id: Item ID
        workspace_id: Workspace ID
        status: New status (active, archived, deleted)

    Returns:
        Updated item object or None
    """
    # Get item
    item = await get_inbox_item(db, item_id, workspace_id)
    if not item:
        return None

    # Update status
    item.status = status

    await db.commit()
    await db.refresh(item)

    return item


async def delete_inbox_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    workspace_id: uuid.UUID
) -> bool:
    """Delete an inbox item.

    Args:
        db: Database session
        item_id: Item ID
        workspace_id: Workspace ID

    Returns:
        True if deleted, False otherwise
    """
    # Get item
    item = await get_inbox_item(db, item_id, workspace_id)
    if not item:
        return False

    # Delete item
    await db.delete(item)
    await db.commit()

    return True
