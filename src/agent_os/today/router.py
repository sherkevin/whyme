"""Today API router.

Provides the Today view - an aggregated view of items needing user attention.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from agent_os.db.base import get_db
from agent_os.today import crud
from agent_os.today.schema import (
    TodayViewResponse,
    TodayItem,
    TodayErrorResponse,
)
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.items.models import Workspace

router = APIRouter(prefix="/api/v1/today", tags=["Today"])


@router.get(
    "",
    response_model=TodayViewResponse,
    responses={
        401: {"model": TodayErrorResponse, "description": "Not authenticated"},
        404: {"model": TodayErrorResponse, "description": "Workspace not found"}
    }
)
async def get_today_view(
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return"),
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """Get the Today view.

    Returns an aggregated view of items that need user's attention today.
    Includes active tasks, recent notes, and items requiring follow-up.
    """
    # Verify workspace exists and user has access
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

    # Get today view data
    items, summary = await crud.get_today_view(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        limit=limit
    )

    # Convert to response models
    today_items = [
        TodayItem(
            id=item.id,
            type=item.item_type.value if item.item_type else "unknown",  # Use item_type instead of type
            title=item.title,
            content=item.content,
            status=item.status.value if item.status else "unknown",  # Convert enum to string
            created_at=item.created_at,
            updated_at=item.updated_at,
            source_type="inbox"  # Items come from the inbox after agent processing
        )
        for item in items
    ]

    return TodayViewResponse(
        workspace_id=workspace_id,
        user_id=current_user.id,
        items=today_items,
        summary=summary,
        generated_at=datetime.now()
    )
