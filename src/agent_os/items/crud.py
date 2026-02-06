"""Unified Items CRUD Operations - PRD4 Implementation."""

import uuid
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from agent_os.items.models import (
    Item, Workspace, Area, Project,
    TaskExtension, DecisionPoint, LedgerEvent, GraphEdge,
    ItemType, ItemStatus
)
from agent_os.items.schema import (
    ItemCreate, ItemUpdate, ItemResponse,
    WorkspaceCreate, WorkspaceResponse,
    AreaCreate, AreaResponse,
    ProjectCreate, ProjectResponse,
    TaskExtensionCreate, TaskExtensionResponse,
    DecisionPointCreate, DecisionPointResponse,
    LedgerEventCreate, LedgerEventResponse,
    GraphEdgeCreate, GraphEdgeResponse
)


# ============================================================================
# Workspace CRUD
# ============================================================================

async def create_workspace(
    db: AsyncSession,
    workspace: WorkspaceCreate
) -> WorkspaceResponse:
    """创建 Workspace"""
    db_workspace = Workspace(**workspace.model_dump())
    db.add(db_workspace)
    await db.commit()
    await db.refresh(db_workspace)
    return WorkspaceResponse.model_validate(db_workspace)


async def get_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID
) -> Optional[WorkspaceResponse]:
    """获取 Workspace"""
    result = await db.execute(
        select(Workspace).filter(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace:
        return WorkspaceResponse.model_validate(workspace)
    return None


async def list_workspaces(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100
) -> List[WorkspaceResponse]:
    """列出 Workspaces"""
    result = await db.execute(
        select(Workspace)
        .filter(Workspace.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
    )
    workspaces = result.scalars().all()
    return [WorkspaceResponse.model_validate(w) for w in workspaces]


# ============================================================================
# Area CRUD
# ============================================================================

async def create_area(
    db: AsyncSession,
    area: AreaCreate
) -> AreaResponse:
    """创建 Area"""
    db_area = Area(**area.model_dump())
    db.add(db_area)
    await db.commit()
    await db.refresh(db_area)
    return AreaResponse.model_validate(db_area)


async def get_area(
    db: AsyncSession,
    area_id: uuid.UUID
) -> Optional[AreaResponse]:
    """获取 Area"""
    result = await db.execute(
        select(Area).filter(Area.id == area_id)
    )
    area = result.scalar_one_or_none()
    if area:
        return AreaResponse.model_validate(area)
    return None


async def list_areas(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    parent_id: Optional[uuid.UUID] = None
) -> List[AreaResponse]:
    """列出 Areas"""
    conditions = [Area.workspace_id == workspace_id]
    if parent_id is not None:
        conditions.append(Area.parent_id == parent_id)
    else:
        conditions.append(Area.parent_id.is_(None))

    result = await db.execute(
        select(Area)
        .filter(and_(*conditions))
        .order_by(Area.sort_order)
    )
    areas = result.scalars().all()
    return [AreaResponse.model_validate(a) for a in areas]


async def get_area_tree(
    db: AsyncSession,
    workspace_id: uuid.UUID
) -> List[AreaResponse]:
    """获取 Area 树形结构 (递归查询)"""
    # 先获取所有顶级 Area
    top_areas = await list_areas(db, workspace_id, None)

    # 递归加载子 Area
    async def load_children(area_id: uuid.UUID) -> List[AreaResponse]:
        children = await list_areas(db, workspace_id, area_id)
        for child in children:
            # 这里可以递归加载更深层次,但目前只加载一层
            pass
        return children

    # 为每个顶级 Area 加载子 Area
    for area in top_areas:
        children = await load_children(area.id)
        # 可以在 Response 中添加 children 字段

    return top_areas


async def update_area(
    db: AsyncSession,
    area_id: uuid.UUID,
    area_update: dict
) -> Optional[AreaResponse]:
    """更新 Area"""
    result = await db.execute(
        select(Area).filter(Area.id == area_id)
    )
    area = result.scalar_one_or_none()
    if area:
        for key, value in area_update.items():
            setattr(area, key, value)
        await db.commit()
        await db.refresh(area)
        return AreaResponse.model_validate(area)
    return None


async def delete_area(
    db: AsyncSession,
    area_id: uuid.UUID
) -> bool:
    """删除 Area"""
    result = await db.execute(
        select(Area).filter(Area.id == area_id)
    )
    area = result.scalar_one_or_none()
    if area:
        await db.delete(area)
        await db.commit()
        return True
    return False


# ============================================================================
# Project CRUD
# ============================================================================

async def create_project(
    db: AsyncSession,
    project: ProjectCreate
) -> ProjectResponse:
    """创建 Project"""
    db_project = Project(**project.model_dump())
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return ProjectResponse.model_validate(db_project)


async def get_project(
    db: AsyncSession,
    project_id: uuid.UUID
) -> Optional[ProjectResponse]:
    """获取 Project"""
    result = await db.execute(
        select(Project).filter(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project:
        return ProjectResponse.model_validate(project)
    return None


async def list_projects(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    area_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[ProjectResponse]:
    """列出 Projects"""
    conditions = [Project.workspace_id == workspace_id]
    if area_id:
        conditions.append(Project.area_id == area_id)

    result = await db.execute(
        select(Project)
        .filter(and_(*conditions))
        .offset(skip)
        .limit(limit)
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


# ============================================================================
# Item CRUD
# ============================================================================

async def create_item(
    db: AsyncSession,
    item: ItemCreate
) -> ItemResponse:
    """创建 Item"""
    db_item = Item(**item.model_dump())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return ItemResponse.model_validate(db_item)


async def get_item(
    db: AsyncSession,
    item_id: uuid.UUID
) -> Optional[ItemResponse]:
    """获取 Item"""
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.area))
        .options(selectinload(Item.project))
        .filter(Item.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item:
        return ItemResponse.model_validate(item)
    return None


async def update_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    item_update: ItemUpdate
) -> Optional[ItemResponse]:
    """更新 Item"""
    result = await db.execute(
        select(Item).filter(Item.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item:
        update_data = item_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        await db.commit()
        await db.refresh(item)
        return ItemResponse.model_validate(item)
    return None


async def delete_item(
    db: AsyncSession,
    item_id: uuid.UUID
) -> bool:
    """删除 Item (软删除)"""
    result = await db.execute(
        select(Item).filter(Item.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item:
        item.status = ItemStatus.DELETED
        await db.commit()
        return True
    return False


async def list_items(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    type: Optional[ItemType] = None,
    area_id: Optional[uuid.UUID] = None,
    project_id: Optional[uuid.UUID] = None,
    status: Optional[ItemStatus] = None,
    skip: int = 0,
    limit: int = 20
) -> Tuple[List[ItemResponse], int]:
    """列出 Items (带分页)"""
    conditions = [
        Item.workspace_id == workspace_id,
        Item.status != ItemStatus.DELETED
    ]

    if type:
        conditions.append(Item.type == type.value)
    if area_id:
        conditions.append(Item.area_id == area_id)
    if project_id:
        conditions.append(Item.project_id == project_id)
    if status:
        conditions.append(Item.status == status.value)

    # Count total
    count_result = await db.execute(
        select(func.count(Item.id)).filter(and_(*conditions))
    )
    total = count_result.scalar()

    # Fetch items
    result = await db.execute(
        select(Item)
        .filter(and_(*conditions))
        .order_by(Item.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return [ItemResponse.model_validate(i) for i in items], total


# ============================================================================
# Task Extension CRUD
# ============================================================================

async def create_task_extension(
    db: AsyncSession,
    extension: TaskExtensionCreate
) -> TaskExtensionResponse:
    """创建 Task Extension"""
    db_extension = TaskExtension(**extension.model_dump())
    db.add(db_extension)
    await db.commit()
    await db.refresh(db_extension)
    return TaskExtensionResponse.model_validate(db_extension)


async def get_task_extension(
    db: AsyncSession,
    item_id: uuid.UUID
) -> Optional[TaskExtensionResponse]:
    """获取 Task Extension"""
    result = await db.execute(
        select(TaskExtension).filter(TaskExtension.item_id == item_id)
    )
    extension = result.scalar_one_or_none()
    if extension:
        return TaskExtensionResponse.model_validate(extension)
    return None


# ============================================================================
# Decision Point CRUD
# ============================================================================

async def create_decision_point(
    db: AsyncSession,
    decision: DecisionPointCreate
) -> DecisionPointResponse:
    """创建 Decision Point"""
    db_decision = DecisionPoint(**decision.model_dump())
    db.add(db_decision)
    await db.commit()
    await db.refresh(db_decision)
    return DecisionPointResponse.model_validate(db_decision)


async def get_decision_points(
    db: AsyncSession,
    task_id: uuid.UUID
) -> List[DecisionPointResponse]:
    """获取任务的所有 Decision Points"""
    result = await db.execute(
        select(DecisionPoint)
        .filter(DecisionPoint.task_id == task_id)
        .order_by(DecisionPoint.created_at)
    )
    decisions = result.scalars().all()
    return [DecisionPointResponse.model_validate(d) for d in decisions]


async def confirm_decision(
    db: AsyncSession,
    decision_id: uuid.UUID,
    option_id: uuid.UUID
) -> Optional[DecisionPointResponse]:
    """确认决策"""
    result = await db.execute(
        select(DecisionPoint).filter(DecisionPoint.id == decision_id)
    )
    decision = result.scalar_one_or_none()
    if decision:
        decision.user_choice = option_id
        decision.confirmed_at = func.now()
        await db.commit()
        await db.refresh(decision)
        return DecisionPointResponse.model_validate(decision)
    return None


# ============================================================================
# Ledger Event CRUD
# ============================================================================

async def record_agent_suggestion(
    db: AsyncSession,
    task_id: uuid.UUID,
    suggestion: dict
) -> LedgerEventResponse:
    """记录 Agent 建议"""
    event = LedgerEventCreate(
        task_id=task_id,
        event_type="agent_suggested",
        snapshot=suggestion
    )
    return await create_ledger_event(db, event)


async def record_user_confirmation(
    db: AsyncSession,
    task_id: uuid.UUID,
    decision: dict
) -> LedgerEventResponse:
    """记录用户确认"""
    event = LedgerEventCreate(
        task_id=task_id,
        event_type="user_confirmed",
        snapshot=decision
    )
    return await create_ledger_event(db, event)


async def record_deliverable_generated(
    db: AsyncSession,
    task_id: uuid.UUID,
    deliverable: dict
) -> LedgerEventResponse:
    """记录交付物生成"""
    event = LedgerEventCreate(
        task_id=task_id,
        event_type="deliverable_generated",
        snapshot=deliverable
    )
    return await create_ledger_event(db, event)


async def create_ledger_event(
    db: AsyncSession,
    event: LedgerEventCreate
) -> LedgerEventResponse:
    """创建 Ledger Event"""
    db_event = LedgerEvent(**event.model_dump())
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    return LedgerEventResponse.model_validate(db_event)


async def get_task_ledger(
    db: AsyncSession,
    task_id: uuid.UUID
) -> List[LedgerEventResponse]:
    """获取任务的审计日志"""
    result = await db.execute(
        select(LedgerEvent)
        .filter(LedgerEvent.task_id == task_id)
        .order_by(LedgerEvent.created_at)
    )
    events = result.scalars().all()
    return [LedgerEventResponse.model_validate(e) for e in events]


# ============================================================================
# Graph Edge CRUD
# ============================================================================

async def create_edge(
    db: AsyncSession,
    edge: GraphEdgeCreate
) -> GraphEdgeResponse:
    """创建 Graph Edge"""
    db_edge = GraphEdge(**edge.model_dump())
    db.add(db_edge)
    await db.commit()
    await db.refresh(db_edge)
    return GraphEdgeResponse.model_validate(db_edge)


async def get_edges(
    db: AsyncSession,
    node_id: uuid.UUID,
    strong_only: bool = False
) -> List[GraphEdgeResponse]:
    """查询节点的所有连接"""
    conditions = or_(
        GraphEdge.from_node_id == node_id,
        GraphEdge.to_node_id == node_id
    )

    if strong_only:
        conditions = and_(conditions, GraphEdge.is_strong == True)

    result = await db.execute(
        select(GraphEdge)
        .filter(conditions)
        .order_by(GraphEdge.weight.desc())
    )
    edges = result.scalars().all()
    return [GraphEdgeResponse.model_validate(e) for e in edges]


async def get_strong_connections(
    db: AsyncSession,
    node_id: uuid.UUID
) -> List[GraphEdgeResponse]:
    """仅查询强连接"""
    return await get_edges(db, node_id, strong_only=True)


async def delete_edge(
    db: AsyncSession,
    edge_id: uuid.UUID
) -> bool:
    """删除连接"""
    result = await db.execute(
        select(GraphEdge).filter(GraphEdge.id == edge_id)
    )
    edge = result.scalar_one_or_none()
    if edge:
        await db.delete(edge)
        await db.commit()
        return True
    return False
