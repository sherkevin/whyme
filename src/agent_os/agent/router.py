"""Agent API routes for PA 1.0 Stage 2.

This module provides API endpoints for agent processing.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_os.agent import (
    agent_tick,
    process_inbox_item,
    ProcessingResult
)
from agent_os.db.base import get_db
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ============================================================================
# Request/Response Schemas
# ============================================================================

class AgentTickRequest(BaseModel):
    """Agent Tick 请求"""
    max_items: int = Field(
        default=10,
        ge=1,
        le=100,
        description="最多处理的 Item 数量"
    )
    force_reprocess: bool = Field(
        default=False,
        description="是否强制重新处理已处理的 items"
    )


class AgentTickResponse(BaseModel):
    """Agent Tick 响应"""
    processed: int = Field(description="处理的 Item 总数")
    succeeded: int = Field(description="成功处理的数量")
    failed: int = Field(description="失败的数量")
    skipped: int = Field(description="跳过的数量（已处理）")
    results: list = Field(description="每个 Item 的处理结果详情")


class ProcessItemRequest(BaseModel):
    """处理单个 Item 请求"""
    force_reprocess: bool = Field(
        default=False,
        description="是否强制重新处理"
    )


class ProcessItemResponse(BaseModel):
    """处理单个 Item 响应"""
    success: bool
    item_id: str
    from_status: Optional[str]
    to_status: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    item_type: Optional[str]
    error: Optional[str]
    processed_at: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/tick", response_model=AgentTickResponse)
async def agent_tick_endpoint(
    request: AgentTickRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """触发一次 Agent Tick

    处理所有 raw 状态的 InboxItems，将它们转换为 processed 状态。
    处理过程包括：
    - 生成标题
    - 生成摘要
    - 分类内容类型

    Args:
        request: Agent Tick 请求参数
        db: 数据库会话
        current_user: 当前用户

    Returns:
        AgentTickResponse: 处理结果摘要
    """
    # 调用 agent_tick
    result = await agent_tick(
        db,
        max_items=request.max_items,
        force_reprocess=request.force_reprocess
    )

    return AgentTickResponse(**result)


@router.post("/process/{item_id}", response_model=ProcessItemResponse)
async def process_item_endpoint(
    item_id: str,
    request: ProcessItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """处理指定的单个 InboxItem

    将单个 InboxItem 从 raw 状态转换为 processed 状态。

    Args:
        item_id: Item ID
        request: 处理请求参数
        db: 数据库会话
        current_user: 当前用户

    Returns:
        ProcessItemResponse: 处理结果

    Raises:
        HTTPException: 如果 Item 不存在或处理失败
    """
    # 调用 process_inbox_item
    result = await process_inbox_item(
        db,
        item_id,
        force_reprocess=request.force_reprocess
    )

    # 转换为响应格式
    response_data = result.to_dict()
    response_data["processed_at"] = result.processed_at.isoformat()

    return ProcessItemResponse(**response_data)


@router.get("/status")
async def get_agent_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Agent 处理状态

    返回当前系统中 raw 状态的 Item 数量和统计信息。

    Args:
        db: 数据库会话
        current_user: 当前用户

    Returns:
        Agent 状态统计信息
    """
    from agent_os.agent.processor import get_raw_items
    from agent_os.items.models import Item, ItemStatus
    from sqlalchemy import select, func

    # 获取当前用户的 raw items 数量
    stmt = select(func.count(Item.id)).where(
        Item.user_id == current_user.id,
        Item.status == ItemStatus.RAW
    )
    result = await db.execute(stmt)
    raw_count = result.scalar() or 0

    # 获取已处理的 items 数量
    stmt = select(func.count(Item.id)).where(
        Item.user_id == current_user.id,
        Item.status == ItemStatus.PROCESSED
    )
    result = await db.execute(stmt)
    processed_count = result.scalar() or 0

    # 获取最近的 raw items
    raw_items = await get_raw_items(db, limit=5)

    return {
        "raw_count": raw_count,
        "processed_count": processed_count,
        "recent_raw_items": [
            {
                "id": str(item.id),
                "title": item.title or "(Untitled)",
                "created_at": item.created_at.isoformat()
            }
            for item in raw_items
        ]
    }
