"""测试数据库持久化 - 验证数据真正落库

这个测试文件验证：
1. 写入的数据是否真正保存到数据库
2. 跨数据库会话是否能读取到数据
3. 与生产环境行为一致
"""

import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_os.items.models import Workspace, Item
from agent_os.items.crud import create_workspace, create_item, get_workspace
from agent_os.items.schema import WorkspaceCreate, ItemCreate
from agent_os.insights.models import InsightExtension
from agent_os.insights import crud


@pytest.mark.asyncio
async def test_workspace_persistence_across_sessions(engine):
    """测试 Workspace 数据跨会话持久化"""

    workspace_id = None

    # === 第一个会话：创建数据并提交 ===
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session1:
        # 创建 workspace
        workspace = await create_workspace(session1, WorkspaceCreate(
            name="Persistence Test Workspace",
            owner_id=uuid.uuid4()
        ))
        workspace_id = workspace.id

        # 显式提交
        await session1.commit()

        # 在同一会话中读取 - 应该能读到
        result = await session1.get(Workspace, workspace_id)
        assert result is not None
        assert result.name == "Persistence Test Workspace"

    # === 第二个会话：验证数据已持久化 ===
    async with async_session_maker() as session2:
        # 跨会话读取 - 应该能读到（证明数据已真正落库）
        result = await session2.get(Workspace, workspace_id)
        assert result is not None
        assert result.name == "Persistence Test Workspace"
        assert result.id == workspace_id


@pytest.mark.asyncio
async def test_insight_persistence_across_sessions(engine):
    """测试 Insight 数据跨会话持久化"""

    workspace_id = None
    insight_item_id = None
    claim_hash = None

    # === 第一个会话：创建 insight ===
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session1:
        # 创建 workspace
        workspace = await create_workspace(session1, WorkspaceCreate(
            name="Insight Persistence Workspace",
            owner_id=uuid.uuid4()
        ))
        workspace_id = workspace.id

        # 创建 insight
        from agent_os.insights.models import generate_claim_hash
        creator_id = uuid.uuid4()
        claim = "Cross-session persistence test claim"

        insight = await crud.create_insight(
            session1,
            workspace_id=workspace_id,
            creator_id=creator_id,
            claim=claim,
            rationale="Testing persistence across sessions",
            implications=["Implication 1", "Implication 2"]
        )

        insight_item_id = insight.item_id
        claim_hash = insight.claim_hash

        # 显式提交
        await session1.commit()

        # 在同一会话中验证
        result = await crud.get_insight(session1, insight_item_id)
        assert result is not None
        assert result.claim == claim

    # === 第二个会话：验证 insight 已持久化 ===
    async with async_session_maker() as session2:
        # 通过 item_id 获取 insight
        result = await crud.get_insight(session2, insight_item_id)
        assert result is not None
        assert result.claim == "Cross-session persistence test claim"
        assert result.rationale == "Testing persistence across sessions"
        assert len(result.implications) == 2
        assert result.claim_hash == claim_hash

    # === 第三个会话：通过 claim_hash 查询 ===
    async with async_session_maker() as session3:
        from sqlalchemy import select

        result = await session3.execute(
            select(InsightExtension).where(
                InsightExtension.claim_hash == claim_hash
            )
        )
        insight = result.scalar_one_or_none()

        assert insight is not None
        assert insight.item_id == insight_item_id
        assert insight.claim == "Cross-session persistence test claim"


@pytest.mark.asyncio
async def test_item_with_extension_persistence(engine):
    """测试 Item 和 Extension 的联合持久化"""

    workspace_id = None
    item_id = None

    # === 第一个会话：创建带扩展的 item ===
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session1:
        # 创建 workspace
        workspace = await create_workspace(session1, WorkspaceCreate(
            name="Extension Persistence Workspace",
            owner_id=uuid.uuid4()
        ))
        workspace_id = workspace.id

        # 创建 item
        from agent_os.items.models import TaskExtension

        item_data = ItemCreate(
            workspace_id=workspace_id,
            creator_id=uuid.uuid4(),
            type="task",
            title="Test Task",
            content="Test content"
        )

        item = await create_item(session1, item_data)
        item_id = item.id

        # 创建 task extension
        task_ext = TaskExtension(
            item_id=item.id,
            goal="Test goal",
            risk_level="low",
            execution_status="draft"
        )

        session1.add(task_ext)
        await session1.commit()

        # 验证在同一会话中
        result = await session1.get(Item, item_id)
        assert result is not None
        assert result.title == "Test Task"

    # === 第二个会话：验证 item 和 extension 都持久化了 ===
    async with async_session_maker() as session2:
        from sqlalchemy import select

        # 读取 item
        item_result = await session2.get(Item, item_id)
        assert item_result is not None
        assert item_result.title == "Test Task"
        assert item_result.id == item_id

        # 读取 task extension
        task_result = await session2.execute(
            select(TaskExtension).where(TaskExtension.item_id == item_id)
        )
        task_ext = task_result.scalar_one_or_none()

        assert task_ext is not None
        assert task_ext.goal == "Test goal"
        assert task_ext.risk_level == "low"
        assert task_ext.execution_status == "draft"


@pytest.mark.asyncio
async def test_duplicate_detection_across_sessions(engine):
    """测试跨会话的重复检测"""

    workspace_id = None
    claim = "Duplicate detection test claim"

    # === 第一个会话：创建 insight ===
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session1:
        workspace = await create_workspace(session1, WorkspaceCreate(
            name="Duplicate Detection Workspace",
            owner_id=uuid.uuid4()
        ))
        workspace_id = workspace.id

        # 创建第一个 insight
        insight1 = await crud.create_insight(
            session1,
            workspace_id=workspace_id,
            creator_id=uuid.uuid4(),
            claim=claim,
            rationale="First creation"
        )

        await session1.commit()

    # === 第二个会话：尝试创建重复的 insight ===
    async with async_session_maker() as session2:
        # 应该检测到重复（从数据库中读取到已存在的 claim_hash）
        with pytest.raises(ValueError, match="already exists"):
            await crud.create_insight(
                session2,
                workspace_id=workspace_id,
                creator_id=uuid.uuid4(),
                claim=claim,  # 相同的 claim
                rationale="Second attempt - should fail"
            )


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(engine):
    """测试错误时事务回滚"""

    workspace_id = None

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # === 第一个会话：创建 workspace ===
    async with async_session_maker() as session1:
        workspace = await create_workspace(session1, WorkspaceCreate(
            name="Rollback Test Workspace",
            owner_id=uuid.uuid4()
        ))
        workspace_id = workspace.id
        await session1.commit()

    # === 第二个会话：开始事务但不提交，然后回滚 ===
    async with async_session_maker() as session2:
        # 直接创建 InsightExtension 对象（不使用 CRUD 函数，避免内部 commit）
        from agent_os.insights.models import InsightExtension, generate_claim_hash

        # 先创建一个 Item
        item_data = ItemCreate(
            workspace_id=workspace_id,
            creator_id=uuid.uuid4(),
            type="insight",
            title="To be rolled back",
            content="This should be rolled back"
        )
        item = await create_item(session2, item_data)

        insight_id = item.id

        # 创建 InsightExtension 但不提交
        claim = "This should be rolled back"
        insight_ext = InsightExtension(
            item_id=item.id,
            claim=claim,
            rationale="Rollback test",
            implications=[],
            claim_hash=generate_claim_hash(claim),
            source_refs=[],
            confidence_score={"score": 0.5},
            mining_metadata={},
            review_status="pending"
        )

        session2.add(insight_ext)

        # 显式回滚（不调用 commit）
        await session2.rollback()

    # === 第三个会话：验证回滚后数据不存在 ===
    async with async_session_maker() as session3:
        # 应该读不到这个 insight（因为被回滚了）
        result = await crud.get_insight(session3, insight_id)

        # Item 可能存在（因为 create_item 可能 commit 了），但 InsightExtension 应该不存在
        # 我们通过直接查询 InsightExtension 来验证
        from sqlalchemy import select

        ext_result = await session3.execute(
            select(InsightExtension).where(
                InsightExtension.item_id == insight_id
            )
        )
        ext = ext_result.scalar_one_or_none()

        # InsightExtension 应该不存在（因为被回滚了）
        assert ext is None, "InsightExtension should have been rolled back"


@pytest.mark.asyncio
async def test_update_persistence(engine):
    """测试更新的持久化"""

    workspace_id = None
    insight_id = None

    # === 第一个会话：创建 insight ===
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session1:
        workspace = await create_workspace(session1, WorkspaceCreate(
            name="Update Test Workspace",
            owner_id=uuid.uuid4()
        ))
        workspace_id = workspace.id

        insight = await crud.create_insight(
            session1,
            workspace_id=workspace_id,
            creator_id=uuid.uuid4(),
            claim="Original claim",
            rationale="Original rationale"
        )

        insight_id = insight.item_id
        await session1.commit()

    # === 第二个会话：更新 insight ===
    async with async_session_maker() as session2:
        insight = await crud.get_insight(session2, insight_id)
        assert insight is not None

        # 更新审核状态
        insight.review_status = "approved"
        await session2.commit()

    # === 第三个会话：验证更新已持久化 ===
    async with async_session_maker() as session3:
        insight = await crud.get_insight(session3, insight_id)
        assert insight is not None
        assert insight.review_status == "approved"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
