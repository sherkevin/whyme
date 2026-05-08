"""Today API router.

Provides the Today view - an aggregated view of items needing user attention.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import get_db
from agent_os.items.models import Workspace
from agent_os.today import crud
from agent_os.today.schema import (
    DailyInsightResponse,
    InsightSource,
    TodayErrorResponse,
    TodayInsightListResponse,
    TodayItem,
    TodayViewResponse,
)

router = APIRouter(prefix="/api/v1/today", tags=["Today"])


@router.get(
    "/legacy",
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


@router.get(
    "/insight",
    response_model=TodayInsightListResponse,
    responses={
        401: {"model": TodayErrorResponse, "description": "Not authenticated"},
        404: {"model": TodayErrorResponse, "description": "Workspace not found"}
    }
)
async def get_today_insights(
    day: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format"),
    theme: str | None = Query(None, description="Optional theme filter"),
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get today's insights.

    Returns structured insights for the specified date with:
    - claim: Main claim/statement
    - rationale: Reasoning/explanation
    - implications: List of implications
    - sources: Supporting source items

    **Required fields**: claim, rationale, implications, sources
    """
    from agent_os.garden.models import DailyInsight
    from agent_os.items.models import Item

    # Verify workspace access
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

    # Parse day parameter
    try:
        from datetime import date
        target_date = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )

    # Query insights for the specified day
    # Filter by status='stable' and level >= 2 for quality insights
    stmt = select(DailyInsight).where(
        and_(
            DailyInsight.workspace_id == workspace_id,
            DailyInsight.user_id == current_user.id,
            DailyInsight.status == "stable",
            DailyInsight.level >= 2,
            func.date(DailyInsight.created_at) == target_date
        )
    ).order_by(DailyInsight.created_at.desc())

    # Apply theme filter if provided
    if theme:
        stmt = stmt.where(DailyInsight.content.ilike(f"%{theme}%"))

    result = await db.execute(stmt)
    insights = result.scalars().all()

    # Convert to response models with required fields
    insight_responses = []
    for insight in insights:
        # Parse source_item_ids if available
        sources = []
        if insight.source_item_ids:
            import json
            try:
                source_ids = json.loads(insight.source_item_ids)
                # Fetch source items
                source_result = await db.execute(
                    select(Item).where(Item.id.in_(source_ids[:5]))  # Limit to 5 sources
                )
                source_items = source_result.scalars().all()
                sources = [
                    InsightSource(
                        id=item.id,
                        title=item.title,
                        item_type=item.type
                    )
                    for item in source_items
                ]
            except (json.JSONDecodeError, TypeError):
                pass

        # Build response with required fields
        # Use title as claim, content as rationale, generate implications from content
        insight_responses.append(DailyInsightResponse(
            id=insight.id,
            claim=insight.title or "Insight",
            rationale=insight.content or "",
            implications=[insight.content[:100]] if insight.content else [],
            level=insight.level,
            status=insight.status,
            evidence_count=insight.evidence_count or 1,
            sources=sources,
            created_at=insight.created_at,
            updated_at=insight.updated_at
        ))

    return TodayInsightListResponse(
        data=insight_responses,
        day=day,
        total=len(insight_responses)
    )
