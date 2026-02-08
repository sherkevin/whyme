"""PRD4 Unified Items - Unit Tests."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import (
    Workspace, Area, Project, Item,
    TaskExtension, DecisionPoint, LedgerEvent, GraphEdge,
    ItemType, ItemStatus
)
from agent_os.items import crud
from agent_os.items.schema import (
    WorkspaceCreate, AreaCreate, ProjectCreate,
    ItemCreate, ItemUpdate, TaskExtensionCreate,
    DecisionPointCreate, LedgerEventCreate, GraphEdgeCreate
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
async def test_workspace(db_session: AsyncSession):
    """创建测试 Workspace"""
    workspace = Workspace(
        name="Test Workspace",
        description="Test Description",
        owner_id=uuid.uuid4()
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def test_area(db_session: AsyncSession, test_workspace: Workspace):
    """创建测试 Area"""
    area = Area(
        workspace_id=test_workspace.id,
        name="Test Area",
        color="#FF5733",
        sort_order=1
    )
    db_session.add(area)
    await db_session.commit()
    await db_session.refresh(area)
    return area


@pytest.fixture
async def test_project(db_session: AsyncSession, test_workspace: Workspace, test_area: Area):
    """创建测试 Project"""
    project = Project(
        workspace_id=test_workspace.id,
        area_id=test_area.id,
        name="Test Project",
        status="active"
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_item(db_session: AsyncSession, test_workspace: Workspace, test_user_id: uuid.UUID):
    """创建测试 Item"""
    item = Item(
        workspace_id=test_workspace.id,
        creator_id=test_user_id,
        type=ItemType.NOTE,
        title="Test Note",
        content="Test Content",
        status=ItemStatus.ACTIVE
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """测试用户 ID"""
    return uuid.uuid4()


# ============================================================================
# Workspace CRUD Tests
# ============================================================================

class TestWorkspaceCRUD:
    """Workspace CRUD 测试"""

    async def test_create_workspace(self, db_session: AsyncSession, test_user_id: uuid.UUID):
        """测试创建 Workspace"""
        workspace_data = WorkspaceCreate(
            name="New Workspace",
            description="New Description",
            owner_id=test_user_id
        )
        workspace = await crud.create_workspace(db_session, workspace_data)

        assert workspace.id is not None
        assert workspace.name == "New Workspace"
        assert workspace.owner_id == test_user_id

    async def test_get_workspace(self, db_session: AsyncSession, test_workspace: Workspace):
        """测试获取 Workspace"""
        workspace = await crud.get_workspace(db_session, test_workspace.id)
        assert workspace is not None
        assert workspace.id == test_workspace.id
        assert workspace.name == test_workspace.name

    async def test_list_workspaces(self, db_session: AsyncSession, test_workspace: Workspace):
        """测试列出 Workspaces"""
        workspaces = await crud.list_workspaces(
            db_session,
            test_workspace.owner_id,
            skip=0,
            limit=100
        )
        assert len(workspaces) >= 1
        assert test_workspace.id in [w.id for w in workspaces]


# ============================================================================
# Area CRUD Tests
# ============================================================================

class TestAreaCRUD:
    """Area CRUD 测试"""

    async def test_create_area(self, db_session: AsyncSession, test_workspace: Workspace):
        """测试创建 Area"""
        area_data = AreaCreate(
            workspace_id=test_workspace.id,
            name="New Area",
            color="#00FF00"
        )
        area = await crud.create_area(db_session, area_data)

        assert area.id is not None
        assert area.name == "New Area"
        assert area.color == "#00FF00"

    async def test_get_area(self, db_session: AsyncSession, test_area: Area):
        """测试获取 Area"""
        area = await crud.get_area(db_session, test_area.id)
        assert area is not None
        assert area.id == test_area.id

    async def test_list_areas(self, db_session: AsyncSession, test_workspace: Workspace):
        """测试列出 Areas"""
        # 在测试中创建 Area 确保数据存在
        area_data = AreaCreate(
            workspace_id=test_workspace.id,
            name="Test Area for List"
        )
        await crud.create_area(db_session, area_data)

        areas = await crud.list_areas(db_session, test_workspace.id)
        assert len(areas) >= 1

    async def test_update_area(self, db_session: AsyncSession, test_area: Area):
        """测试更新 Area"""
        updated_area = await crud.update_area(
            db_session,
            test_area.id,
            {"name": "Updated Area", "color": "#0000FF"}
        )
        assert updated_area is not None
        assert updated_area.name == "Updated Area"
        assert updated_area.color == "#0000FF"

    async def test_delete_area(self, db_session: AsyncSession, test_area: Area):
        """测试删除 Area"""
        success = await crud.delete_area(db_session, test_area.id)
        assert success is True

        # 验证已删除
        area = await crud.get_area(db_session, test_area.id)
        assert area is None


# ============================================================================
# Project CRUD Tests
# ============================================================================

class TestProjectCRUD:
    """Project CRUD 测试"""

    async def test_create_project(self, db_session: AsyncSession, test_workspace: Workspace, test_area: Area):
        """测试创建 Project"""
        project_data = ProjectCreate(
            workspace_id=test_workspace.id,
            area_id=test_area.id,
            name="New Project"
        )
        project = await crud.create_project(db_session, project_data)

        assert project.id is not None
        assert project.name == "New Project"
        assert project.area_id == test_area.id

    async def test_get_project(self, db_session: AsyncSession, test_project: Project):
        """测试获取 Project"""
        project = await crud.get_project(db_session, test_project.id)
        assert project is not None
        assert project.id == test_project.id

    async def test_list_projects(self, db_session: AsyncSession, test_workspace: Workspace, test_area: Area):
        """测试列出 Projects"""
        # 创建一个 Project 确保数据存在
        project_data = ProjectCreate(
            workspace_id=test_workspace.id,
            area_id=test_area.id,
            name="Test Project for List"
        )
        await crud.create_project(db_session, project_data)

        projects = await crud.list_projects(db_session, test_workspace.id)
        assert len(projects) >= 1


# ============================================================================
# Item CRUD Tests
# ============================================================================

class TestItemCRUD:
    """Item CRUD 测试"""

    async def test_create_item(self, db_session: AsyncSession, test_workspace: Workspace, test_user_id: uuid.UUID):
        """测试创建 Item"""
        item_data = ItemCreate(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="New Note",
            content="New Content"
        )
        item = await crud.create_item(db_session, item_data)

        assert item.id is not None
        assert item.type == ItemType.NOTE
        assert item.title == "New Note"

    async def test_get_item(self, db_session: AsyncSession, test_item: Item):
        """测试获取 Item"""
        item = await crud.get_item(db_session, test_item.id)
        assert item is not None
        assert item.id == test_item.id
        assert item.title == test_item.title

    async def test_update_item(self, db_session: AsyncSession, test_item: Item):
        """测试更新 Item"""
        item_update = ItemUpdate(
            title="Updated Title",
            content="Updated Content"
        )
        updated_item = await crud.update_item(db_session, test_item.id, item_update)

        assert updated_item is not None
        assert updated_item.title == "Updated Title"
        assert updated_item.content == "Updated Content"

    async def test_delete_item(self, db_session: AsyncSession, test_item: Item):
        """测试删除 Item (软删除)"""
        success = await crud.delete_item(db_session, test_item.id)
        assert success is True

        # 验证状态已更新
        item = await crud.get_item(db_session, test_item.id)
        assert item.status == ItemStatus.DELETED

    async def test_list_items_with_filters(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user_id: uuid.UUID
    ):
        """测试列出 Items (带过滤)"""
        # 先创建一个 Item 确保数据存在
        item_data = ItemCreate(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="Test Note for List"
        )
        await crud.create_item(db_session, item_data)

        # 按类型过滤
        items, total = await crud.list_items(
            db_session,
            test_workspace.id,
            type=ItemType.NOTE
        )
        assert len(items) >= 1
        assert all(i.type == ItemType.NOTE for i in items)

        # 分页测试 (使用 skip/limit 而不是 page/page_size)
        items2, total2 = await crud.list_items(
            db_session,
            test_workspace.id,
            skip=0,
            limit=10
        )
        assert len(items2) <= 10
        assert total2 >= 1


# ============================================================================
# Task Extension Tests
# ============================================================================

class TestTaskExtension:
    """Task Extension 测试"""

    async def test_create_task_extension(self, db_session: AsyncSession, test_item: Item):
        """测试创建 Task Extension"""
        ext_data = TaskExtensionCreate(
            item_id=test_item.id,
            goal="Complete the task",
            constraints="Time limited",
            risk_level="medium"
        )
        extension = await crud.create_task_extension(db_session, ext_data)

        assert extension.id is not None
        assert extension.goal == "Complete the task"
        assert extension.risk_level == "medium"

    async def test_get_task_extension(self, db_session: AsyncSession, test_item: Item):
        """测试获取 Task Extension"""
        # 先创建
        ext_data = TaskExtensionCreate(item_id=test_item.id)
        await crud.create_task_extension(db_session, ext_data)

        # 再获取
        extension = await crud.get_task_extension(db_session, test_item.id)
        assert extension is not None
        assert extension.item_id == test_item.id


# ============================================================================
# Decision Point Tests
# ============================================================================

class TestDecisionPoint:
    """Decision Point 测试"""

    async def test_create_decision_point(self, db_session: AsyncSession, test_item: Item):
        """测试创建 Decision Point"""
        decision_data = DecisionPointCreate(
            task_id=test_item.id,
            type="selection",
            options=[
                {"summary": "Option A", "risks": "Low", "cost": 100},
                {"summary": "Option B", "risks": "High", "cost": 50}
            ]
        )
        decision = await crud.create_decision_point(db_session, decision_data)

        assert decision.id is not None
        assert decision.type == "selection"
        assert len(decision.options) == 2

    async def test_confirm_decision(self, db_session: AsyncSession, test_item: Item):
        """测试确认决策"""
        # 创建决策点
        decision_data = DecisionPointCreate(
            task_id=test_item.id,
            type="selection",
            options=[{"summary": "Option A"}]
        )
        decision = await crud.create_decision_point(db_session, decision_data)

        # 确认决策
        option_id = uuid.uuid4()
        confirmed = await crud.confirm_decision(db_session, decision.id, option_id)

        assert confirmed is not None
        assert confirmed.user_choice == option_id
        assert confirmed.confirmed_at is not None


# ============================================================================
# Ledger Event Tests
# ============================================================================

class TestLedgerEvent:
    """Ledger Event 测试"""

    async def test_record_agent_suggestion(self, db_session: AsyncSession, test_item: Item):
        """测试记录 Agent 建议"""
        suggestion = {"action": "analyze", "params": {}}
        event = await crud.record_agent_suggestion(db_session, test_item.id, suggestion)

        assert event.id is not None
        assert event.event_type == "agent_suggested"
        assert event.snapshot == suggestion

    async def test_record_user_confirmation(self, db_session: AsyncSession, test_item: Item):
        """测试记录用户确认"""
        option_id = uuid.uuid4()
        decision = {"option_id": str(option_id)}  # UUID 转字符串
        event = await crud.record_user_confirmation(db_session, test_item.id, decision)

        assert event.event_type == "user_confirmed"
        assert event.snapshot == decision

    async def test_get_task_ledger(self, db_session: AsyncSession, test_item: Item):
        """测试获取任务审计日志"""
        # 创建多个事件
        await crud.record_agent_suggestion(db_session, test_item.id, {"suggestion": "test"})
        await crud.record_user_confirmation(db_session, test_item.id, {"decision": "test"})

        # 获取日志
        events = await crud.get_task_ledger(db_session, test_item.id)

        assert len(events) >= 2
        assert all(e.task_id == test_item.id for e in events)


# ============================================================================
# Graph Edge Tests
# ============================================================================

class TestGraphEdge:
    """Graph Edge 测试"""

    async def test_create_edge(self, db_session: AsyncSession, test_workspace: Workspace, test_user_id: uuid.UUID):
        """测试创建 Graph Edge"""
        # 创建两个节点
        item1 = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="Node 1"
        )
        item2 = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="Node 2"
        )
        db_session.add_all([item1, item2])
        await db_session.commit()
        await db_session.refresh(item1)
        await db_session.refresh(item2)

        # 创建连接
        edge_data = GraphEdgeCreate(
            from_node_id=item1.id,
            to_node_id=item2.id,
            weight=0.85,
            relation_type="topic",
            is_strong=True
        )
        edge = await crud.create_edge(db_session, edge_data)

        assert edge.id is not None
        assert edge.weight == 0.85
        assert edge.is_strong is True

    async def test_get_edges(self, db_session: AsyncSession, test_workspace: Workspace, test_user_id: uuid.UUID):
        """测试查询连接"""
        # 创建节点和连接
        item1 = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="Node 1"
        )
        item2 = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="Node 2"
        )
        db_session.add_all([item1, item2])
        await db_session.commit()

        edge_data = GraphEdgeCreate(
            from_node_id=item1.id,
            to_node_id=item2.id,
            weight=0.9,
            relation_type="topic",
            is_strong=True
        )
        await crud.create_edge(db_session, edge_data)

        # 查询连接
        edges = await crud.get_edges(db_session, item1.id)
        assert len(edges) >= 1
        assert edges[0].weight == 0.9

    async def test_get_strong_connections(self, db_session: AsyncSession, test_workspace: Workspace, test_user_id: uuid.UUID):
        """测试仅查询强连接"""
        # 创建节点
        item1 = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="Node 1"
        )
        item2 = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.NOTE,
            title="Node 2"
        )
        db_session.add_all([item1, item2])
        await db_session.commit()

        # 创建强连接
        edge_data = GraphEdgeCreate(
            from_node_id=item1.id,
            to_node_id=item2.id,
            weight=0.8,
            relation_type="topic",
            is_strong=True
        )
        await crud.create_edge(db_session, edge_data)

        # 查询强连接
        strong_edges = await crud.get_strong_connections(db_session, item1.id)
        assert len(strong_edges) >= 1
        assert all(e.is_strong for e in strong_edges)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """集成测试"""

    async def test_full_item_lifecycle(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_area: Area,
        test_project: Project,
        test_user_id: uuid.UUID
    ):
        """测试 Item 完整生命周期"""
        # 1. 创建 Item
        item_data = ItemCreate(
            workspace_id=test_workspace.id,
            creator_id=test_user_id,
            type=ItemType.TASK,
            title="Test Task",
            content="Task Description",
            area_id=test_area.id,
            project_id=test_project.id
        )
        item = await crud.create_item(db_session, item_data)
        assert item.id is not None

        # 2. 添加 Task Extension
        ext_data = TaskExtensionCreate(
            item_id=item.id,
            goal="Complete goal",
            risk_level="high"
        )
        extension = await crud.create_task_extension(db_session, ext_data)
        assert extension is not None

        # 3. 创建 Decision Point
        decision_data = DecisionPointCreate(
            task_id=item.id,
            type="selection",
            options=[{"summary": "Option A"}]
        )
        decision = await crud.create_decision_point(db_session, decision_data)
        assert decision is not None

        # 4. 记录审计日志
        await crud.record_agent_suggestion(db_session, item.id, {"suggestion": "test"})
        ledger = await crud.get_task_ledger(db_session, item.id)
        assert len(ledger) >= 1

        # 5. 更新 Item
        updated_item = await crud.update_item(
            db_session,
            item.id,
            ItemUpdate(title="Updated Task")
        )
        assert updated_item.title == "Updated Task"

        # 6. 软删除
        success = await crud.delete_item(db_session, item.id)
        assert success is True
