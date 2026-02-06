"""Unified Items API Routes - PRD4 Implementation."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from agent_os.db.session import get_db
from agent_os.items import crud
from agent_os.items.schema import (
    # Workspaces
    WorkspaceCreate, WorkspaceResponse,
    # Areas
    AreaCreate, AreaResponse,
    # Projects
    ProjectCreate, ProjectResponse,
    # Items
    ItemCreate, ItemUpdate, ItemResponse, ItemListResponse,
    # Task Extensions
    TaskExtensionCreate, TaskExtensionResponse,
    # Decision Points
    DecisionPointCreate, DecisionPointResponse, DecisionConfirm,
    # Ledger Events
    LedgerEventCreate, LedgerEventResponse,
    # Graph Edges
    GraphEdgeCreate, GraphEdgeResponse, GraphConnectionResponse
)


router = APIRouter(prefix="/prd4", tags=["PRD4 - Unified Items"])


# ============================================================================
# Workspace Endpoints
# ============================================================================

@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    workspace: WorkspaceCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Workspace"""
    return await crud.create_workspace(db, workspace)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取 Workspace"""
    workspace = await crud.get_workspace(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/workspaces", response_model=List[WorkspaceResponse])
async def list_workspaces(
    owner_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """列出 Workspaces"""
    return await crud.list_workspaces(db, owner_id, skip, limit)


# ============================================================================
# Area Endpoints
# ============================================================================

@router.post("/areas", response_model=AreaResponse, status_code=201)
async def create_area(
    area: AreaCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Area"""
    return await crud.create_area(db, area)


@router.get("/areas/{area_id}", response_model=AreaResponse)
async def get_area(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取 Area"""
    area = await crud.get_area(db, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    return area


@router.get("/areas", response_model=List[AreaResponse])
async def list_areas(
    workspace_id: uuid.UUID,
    parent_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db)
):
    """列出 Areas"""
    return await crud.list_areas(db, workspace_id, parent_id)


@router.get("/areas/{workspace_id}/tree", response_model=List[AreaResponse])
async def get_area_tree(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取 Area 树形结构"""
    return await crud.get_area_tree(db, workspace_id)


@router.put("/areas/{area_id}", response_model=AreaResponse)
async def update_area(
    area_id: uuid.UUID,
    area_update: dict,
    db: AsyncSession = Depends(get_db)
):
    """更新 Area"""
    area = await crud.update_area(db, area_id, area_update)
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    return area


@router.delete("/areas/{area_id}", status_code=204)
async def delete_area(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """删除 Area"""
    success = await crud.delete_area(db, area_id)
    if not success:
        raise HTTPException(status_code=404, detail="Area not found")


# ============================================================================
# Project Endpoints
# ============================================================================

@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Project"""
    return await crud.create_project(db, project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取 Project"""
    project = await crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    workspace_id: uuid.UUID,
    area_id: Optional[uuid.UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """列出 Projects"""
    return await crud.list_projects(db, workspace_id, area_id, skip, limit)


# ============================================================================
# Item Endpoints
# ============================================================================

@router.post("/items", response_model=ItemResponse, status_code=201)
async def create_item(
    item: ItemCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Item"""
    return await crud.create_item(db, item)


@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取 Item"""
    item = await crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: uuid.UUID,
    item_update: ItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新 Item"""
    item = await crud.update_item(db, item_id, item_update)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """删除 Item (软删除)"""
    success = await crud.delete_item(db, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")


@router.get("/items", response_model=ItemListResponse)
async def list_items(
    workspace_id: uuid.UUID,
    type: Optional[str] = Query(None),
    area_id: Optional[uuid.UUID] = None,
    project_id: Optional[uuid.UUID] = None,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """列出 Items (带分页)"""
    skip = (page - 1) * page_size
    items, total = await crud.list_items(
        db, workspace_id, type, area_id, project_id, status, skip, page_size
    )
    return ItemListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


# ============================================================================
# Task Extension Endpoints
# ============================================================================

@router.post("/task-extensions", response_model=TaskExtensionResponse, status_code=201)
async def create_task_extension(
    extension: TaskExtensionCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Task Extension"""
    return await crud.create_task_extension(db, extension)


@router.get("/task-extensions/{item_id}", response_model=TaskExtensionResponse)
async def get_task_extension(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取 Task Extension"""
    extension = await crud.get_task_extension(db, item_id)
    if not extension:
        raise HTTPException(status_code=404, detail="Task extension not found")
    return extension


# ============================================================================
# Decision Point Endpoints
# ============================================================================

@router.post("/decision-points", response_model=DecisionPointResponse, status_code=201)
async def create_decision_point(
    decision: DecisionPointCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Decision Point"""
    return await crud.create_decision_point(db, decision)


@router.get("/decision-points/{task_id}", response_model=List[DecisionPointResponse])
async def get_decision_points(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取任务的所有 Decision Points"""
    return await crud.get_decision_points(db, task_id)


@router.post("/decision-points/{decision_id}/confirm", response_model=DecisionPointResponse)
async def confirm_decision(
    decision_id: uuid.UUID,
    confirm: DecisionConfirm,
    db: AsyncSession = Depends(get_db)
):
    """确认决策"""
    decision = await crud.confirm_decision(db, decision_id, confirm.option_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision point not found")
    return decision


# ============================================================================
# Ledger Event Endpoints
# ============================================================================

@router.post("/ledger-events", response_model=LedgerEventResponse, status_code=201)
async def create_ledger_event(
    event: LedgerEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Ledger Event (审计日志)"""
    return await crud.create_ledger_event(db, event)


@router.get("/ledger-events/{task_id}", response_model=List[LedgerEventResponse])
async def get_task_ledger(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取任务的完整审计日志"""
    return await crud.get_task_ledger(db, task_id)


# ============================================================================
# Graph Edge Endpoints
# ============================================================================

@router.post("/connections/edges", response_model=GraphEdgeResponse, status_code=201)
async def create_edge(
    edge: GraphEdgeCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 Graph Edge (连接)"""
    return await crud.create_edge(db, edge)


@router.get("/connections/{node_id}", response_model=List[GraphEdgeResponse])
async def get_edges(
    node_id: uuid.UUID,
    strong_only: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """查询节点的所有连接"""
    return await crud.get_edges(db, node_id, strong_only)


@router.get("/connections/{node_id}/strong", response_model=List[GraphEdgeResponse])
async def get_strong_connections(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """仅查询强连接 (Neural Connections)"""
    return await crud.get_strong_connections(db, node_id)


@router.delete("/connections/edges/{edge_id}", status_code=204)
async def delete_edge(
    edge_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """删除连接"""
    success = await crud.delete_edge(db, edge_id)
    if not success:
        raise HTTPException(status_code=404, detail="Edge not found")
