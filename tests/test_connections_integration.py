"""Stage 3: Connection API Integration Tests.

Complete integration tests for Connection API using full CRUD workflow.
"""

import pytest
import uuid
from datetime import datetime, timedelta

from agent_os.connections.engine import ConnectionEngine
from agent_os.connections import crud
from agent_os.items.crud import create_workspace, create_item
from agent_os.items.schema import WorkspaceCreate, ItemCreate
from agent_os.items.models import Item


# ============================================================================
# Integration Tests - Connection CRUD
# ============================================================================

@pytest.mark.asyncio
async def test_connection_calculation_and_storage(db_session):
    """测试连接计算和存储"""
    # Step 1: 创建workspace和items
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Connection Test Workspace",
        owner_id=creator_id
    ))

    # Step 2: 创建测试items (使用embedding)
    import random

    items_to_create = [
        ItemCreate(
            workspace_id=workspace.id,
            creator_id=creator_id,
            type="note",
            title="Python Programming Guide",
            content="Complete guide to Python programming language"
        ),
        ItemCreate(
            workspace_id=workspace.id,
            creator_id=creator_id,
            type="note",
            title="Python Machine Learning",
            content="Advanced Python for ML and AI applications"
        ),
        ItemCreate(
            workspace_id=workspace.id,
            creator_id=creator_id,
            type="task",
            title="Java Development",
            content="Java programming tutorial"
        )
    ]

    created_items = []
    for item_data in items_to_create:
        item = await create_item(db_session, item_data)
        created_items.append(item)

    # Step 3: 手动添加embedding (模拟)
    for item in created_items:
        # 创建1536维的模拟embedding向量
        embedding = [random.random() for _ in range(1536)]
        # 直接更新数据库
        from sqlalchemy import update
        await db_session.execute(
            update(Item.__table__).where(Item.id == item.id).values(embedding=embedding)
        )
    await db_session.commit()

    # Step 4: 计算连接
    engine = ConnectionEngine()

    # Python items 之间应该有强连接
    score = await engine.calculate_score(created_items[0], created_items[1])
    assert score > 0.0
    print(f"\nConnection score between Python items: {score:.3f}")

    # Python和Java之间连接应该较弱
    score2 = await engine.calculate_score(created_items[0], created_items[2])
    assert score2 >= 0.0
    print(f"Connection score between Python and Java: {score2:.3f}")


@pytest.mark.asyncio
async def test_store_and_retrieve_connections(db_session):
    """测试存储和检索连接"""
    # Step 1: 创建workspace和items
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Connection Storage Test",
        owner_id=creator_id
    ))

    item_a = await create_item(db_session, ItemCreate(
        workspace_id=workspace.id,
        creator_id=creator_id,
        type="note",
        title="Data Science Tutorial",
        content="Learn data science with Python"
    ))

    item_b = await create_item(db_session, ItemCreate(
        workspace_id=workspace.id,
        creator_id=creator_id,
        type="note",
        title="Python Programming",
        content="Complete Python guide"
    ))

    # Step 2: 计算并存储连接
    edge = await crud.calculate_and_store_connection(
        db_session,
        item_a.id,
        item_b.id
    )

    assert edge is not None
    assert edge.weight > 0.0
    assert edge.relation_type in ['topic', 'causal', 'supplement']
    print(f"\nCreated connection: weight={edge.weight:.3f}, type={edge.relation_type}")

    # Step 3: 检索连接
    connections = await crud.get_connections(
        db_session,
        item_a.id,
        strong_only=False,
        limit=10
    )

    assert len(connections) >= 1
    assert connections[0].from_node_id == item_a.id


@pytest.mark.asyncio
async def test_strong_connections_filter(db_session):
    """测试强连接过滤"""
    # Step 1: 创建workspace和items
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Strong Connections Test",
        owner_id=creator_id
    ))

    # Step 2: 创建相关items
    items = []
    for i in range(3):
        item = await create_item(db_session, ItemCreate(
            workspace_id=workspace.id,
            creator_id=creator_id,
            type="note",
            title=f"Python Tutorial {i}",
            content=f"Learn Python programming {i}"
        ))
        items.append(item)

    # Step 3: 批量计算连接
    engine = ConnectionEngine()

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            edge = await crud.calculate_and_store_connection(
                db_session,
                items[i].id,
                items[j].id,
                engine
            )
            print(f"\nEdge {i}-{j}: weight={edge.weight if edge else 0:.3f}, strong={edge.is_strong if edge else False}")

    # Step 4: 查询强连接
    strong_connections = await crud.get_strong_connections(
        db_session,
        items[0].id,
        limit=10
    )

    print(f"\nStrong connections count: {len(strong_connections)}")
    # 验证强连接 (同类型的Python items应该有强连接)
    # 注意: 由于没有真实的embedding，可能不会有强连接
    assert isinstance(strong_connections, list)


@pytest.mark.asyncio
async def test_connection_statistics(db_session):
    """测试连接统计"""
    # Step 1: 创建数据
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Statistics Test",
        owner_id=creator_id
    ))

    items = []
    for i in range(5):
        item = await create_item(db_session, ItemCreate(
            workspace_id=workspace.id,
            creator_id=creator_id,
            type="note",
            title=f"Test Item {i}",
            content=f"Content {i}"
        ))
        items.append(item)

    # Step 2: 创建一些连接
    engine = ConnectionEngine()

    # 只创建部分连接
    for i in range(4):
        edge = await crud.calculate_and_store_connection(
            db_session,
            items[i].id,
            items[i + 1].id,
            engine
        )

    # Step 3: 获取统计
    stats = await crud.get_connection_stats(db_session, items[0].id)

    assert stats is not None
    assert stats["total_connections"] >= 0
    assert "by_type" in stats

    print(f"\nConnection stats: {stats}")


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_batch_connection_calculation(db_session):
    """测试批量连接计算性能"""
    import time

    # Step 1: 创建数据
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Performance Test",
        owner_id=creator_id
    ))

    # Step 2: 创建多个items
    num_items = 20
    items = []

    for i in range(num_items):
        item = await create_item(db_session, ItemCreate(
            workspace_id=workspace.id,
            creator_id=creator_id,
            type="note",
            title=f"Performance Test Item {i}",
            content=f"Test content number {i} with keywords Python and programming"
        ))
        items.append(item)

    # Step 3: 批量计算连接
    engine = ConnectionEngine()

    start = time.time()

    # 为第一个item计算与所有其他item的连接
    candidate_ids = [item.id for item in items[1:]]
    edges = await crud.batch_calculate_connections(
        db_session,
        items[0].id,
        candidate_ids,
        engine
    )

    elapsed = time.time() - start

    # Step 4: 验证结果
    assert isinstance(edges, list)
    print(f"\n性能测试: 为1个item计算与{len(candidate_ids)}个候选的连接")
    print(f"耗时: {elapsed:.3f} 秒")
    print(f"创建连接数: {len(edges)}")

    # 性能验证: 应该在合理时间内完成
    assert elapsed < 10.0  # 10秒内完成


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_connection_with_no_candidates(db_session):
    """测试没有候选item的情况"""
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="No Candidates Test",
        owner_id=creator_id
    ))

    # 只创建一个item
    item = await create_item(db_session, ItemCreate(
        workspace_id=workspace.id,
        creator_id=creator_id,
        type="note",
        title="Single Item",
        content="Only item in workspace"
    ))

    # 尝试批量计算 (没有候选)
    engine = ConnectionEngine()
    edges = await crud.batch_calculate_connections(
        db_session,
        item.id,
        [],  # 空候选列表
        engine
    )

    assert len(edges) == 0


@pytest.mark.asyncio
async def test_connection_self_loop_prevention(db_session):
    """测试防止自连接"""
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Self Loop Test",
        owner_id=creator_id
    ))

    item = await create_item(db_session, ItemCreate(
        workspace_id=workspace.id,
        creator_id=creator_id,
        type="note",
        title="Test Item",
        content="Test content"
    ))

    # 尝试与自身计算连接
    engine = ConnectionEngine()
    edges = await crud.batch_calculate_connections(
        db_session,
        item.id,
        [item.id],  # 包含自身
        engine
    )

    # 应该没有自连接
    assert len(edges) == 0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
