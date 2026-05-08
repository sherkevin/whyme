"""Inbox API router.

Provides endpoints for managing raw input items (inbox items).
Inbox items are unprocessed inputs that can be notes, tasks, or resources.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.db.base import get_db
from agent_os.inbox import crud
from agent_os.inbox.schema import (
    InboxErrorResponse,
    InboxItemCreate,
    InboxItemListResponse,
    InboxItemResponse,
    InboxItemStatusUpdate,
    InboxItemUpdate,
)

router = APIRouter(prefix="/api/v1/inbox", tags=["Inbox"])


@router.post(
    "/items",
    response_model=InboxItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": InboxErrorResponse, "description": "Invalid request"}
    }
)
async def create_inbox_item(
    item_data: InboxItemCreate,
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """Create a new inbox item.

    Creates a raw input item in the inbox. This can be a note, task,
    or resource collected from various sources (manual, WeChat, browser extension, etc.).
    """
    # Verify workspace exists (optional, can be skipped for performance)
    from sqlalchemy import select

    from agent_os.items.models import Workspace

    workspace_result = await db.execute(
        select(Workspace).filter(Workspace.id == item_data.workspace_id)
    )
    workspace = workspace_result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace not found"
        )

    # Check user has access to workspace
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this workspace"
        )

    # Create inbox item
    item = await crud.create_inbox_item(
        db=db,
        workspace_id=item_data.workspace_id,
        creator_id=current_user.id,
        title=item_data.title,
        content=item_data.content,
        source_type=item_data.source_type,
        source_meta=item_data.source_meta,
        item_type=item_data.type
    )

    return InboxItemResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        creator_id=item.creator_id,
        type=item.type,
        title=item.title,
        content=item.content,
        summary=item.summary,
        source_type=item.source_type,
        source_meta=item.source_meta or {},
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@router.get(
    "/items",
    response_model=InboxItemListResponse,
    responses={
        401: {"model": InboxErrorResponse, "description": "Not authenticated"}
    }
)
async def list_inbox_items(
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    status: str | None = Query(None, description="Filter by status"),
    type: str | None = Query(None, description="Filter by item type"),
    source_type: str | None = Query(None, description="Filter by source type"),
    search: str | None = Query(None, description="Search in title and content"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """List inbox items with pagination and filters.

    Returns a paginated list of inbox items for the given workspace.
    Supports filtering by status, type, source type, and text search.
    """
    # Verify workspace exists and user has access
    from sqlalchemy import and_, select

    from agent_os.items.models import Workspace

    workspace_result = await db.execute(
        select(Workspace).filter(
            and_(
                Workspace.id == workspace_id,
                Workspace.owner_id == current_user.id
            )
        )
    )
    workspace = workspace_result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )

    # Calculate offset
    offset = (page - 1) * page_size

    # Get items
    items, total = await crud.list_inbox_items(
        db=db,
        workspace_id=workspace_id,
        status=status,
        item_type=type,
        source_type=source_type,
        search=search,
        limit=page_size,
        offset=offset
    )

    # Convert to response models
    item_responses = [
        InboxItemResponse(
            id=item.id,
            workspace_id=item.workspace_id,
            creator_id=item.creator_id,
            type=item.type,
            title=item.title,
            content=item.content,
            summary=item.summary,
            source_type=item.source_type,
            source_meta=item.source_meta or {},
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        for item in items
    ]

    has_more = offset + len(items) < total

    return InboxItemListResponse(
        items=item_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more
    )


@router.get(
    "/items/{item_id}",
    response_model=InboxItemResponse,
    responses={
        401: {"model": InboxErrorResponse, "description": "Not authenticated"},
        404: {"model": InboxErrorResponse, "description": "Item not found"}
    }
)
async def get_inbox_item(
    item_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """Get a specific inbox item by ID.

    Returns detailed information about a single inbox item.
    """
    # Verify workspace access
    from sqlalchemy import and_, select

    from agent_os.items.models import Workspace

    workspace_result = await db.execute(
        select(Workspace).filter(
            and_(
                Workspace.id == workspace_id,
                Workspace.owner_id == current_user.id
            )
        )
    )
    workspace = workspace_result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )

    # Get item
    item = await crud.get_inbox_item(db, item_id, workspace_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )

    return InboxItemResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        creator_id=item.creator_id,
        type=item.type,
        title=item.title,
        content=item.content,
        summary=item.summary,
        source_type=item.source_type,
        source_meta=item.source_meta or {},
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@router.patch(
    "/items/{item_id}/status",
    response_model=InboxItemResponse,
    responses={
        401: {"model": InboxErrorResponse, "description": "Not authenticated"},
        404: {"model": InboxErrorResponse, "description": "Item not found"}
    }
)
async def update_inbox_item_status(
    item_id: uuid.UUID,
    status_update: InboxItemStatusUpdate,
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """Update inbox item status.

    Updates the status of an inbox item (e.g., raw -> processed -> archived).
    """
    # Verify workspace access
    from sqlalchemy import and_, select

    from agent_os.items.models import Workspace

    workspace_result = await db.execute(
        select(Workspace).filter(
            and_(
                Workspace.id == workspace_id,
                Workspace.owner_id == current_user.id
            )
        )
    )
    workspace = workspace_result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )

    # Update item status
    item = await crud.update_inbox_item_status(
        db=db,
        item_id=item_id,
        workspace_id=workspace_id,
        status=status_update.status
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )

    return InboxItemResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        creator_id=item.creator_id,
        type=item.type,
        title=item.title,
        content=item.content,
        summary=item.summary,
        source_type=item.source_type,
        source_meta=item.source_meta or {},
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@router.put(
    "/items/{item_id}",
    response_model=InboxItemResponse,
    responses={
        401: {"model": InboxErrorResponse, "description": "Not authenticated"},
        404: {"model": InboxErrorResponse, "description": "Item not found"}
    }
)
async def update_inbox_item(
    item_id: uuid.UUID,
    item_update: InboxItemUpdate,
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """Update an inbox item.

    Updates title, content, or type of an existing inbox item.
    """
    # Verify workspace access
    from sqlalchemy import and_, select

    from agent_os.items.models import Workspace

    workspace_result = await db.execute(
        select(Workspace).filter(
            and_(
                Workspace.id == workspace_id,
                Workspace.owner_id == current_user.id
            )
        )
    )
    workspace = workspace_result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )

    # Update item
    item = await crud.update_inbox_item(
        db=db,
        item_id=item_id,
        workspace_id=workspace_id,
        title=item_update.title,
        content=item_update.content,
        item_type=item_update.type
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )

    return InboxItemResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        creator_id=item.creator_id,
        type=item.type,
        title=item.title,
        content=item.content,
        summary=item.summary,
        source_type=item.source_type,
        source_meta=item.source_meta or {},
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": InboxErrorResponse, "description": "Not authenticated"},
        404: {"model": InboxErrorResponse, "description": "Item not found"}
    }
)
async def delete_inbox_item(
    item_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """Delete an inbox item.

    Permanently deletes an inbox item from the database.
    """
    # Verify workspace access
    from sqlalchemy import and_, select

    from agent_os.items.models import Workspace

    workspace_result = await db.execute(
        select(Workspace).filter(
            and_(
                Workspace.id == workspace_id,
                Workspace.owner_id == current_user.id
            )
        )
    )
    workspace = workspace_result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )

    # Delete item
    deleted = await crud.delete_inbox_item(
        db=db,
        item_id=item_id,
        workspace_id=workspace_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found"
        )

    return None
