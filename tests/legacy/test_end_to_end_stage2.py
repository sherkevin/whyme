"""End-to-End Integration Tests for Stage 2.

Tests the complete flow:
1. Create RAW items
2. Agent Tick processes them
3. Cards are generated
4. Today API returns processed items
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.test_app import test_app as app

from agent_os.auth.models import User
from agent_os.items.models import Item, ItemStatus, ItemType, Workspace

# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def e2e_test_client(db_session):
    """Create test client with database session override."""
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    from agent_os.db import base as db_base
    from agent_os.db.session import get_db as session_get_db

    app.dependency_overrides[db_base.get_db] = override_get_db
    app.dependency_overrides[session_get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def e2e_user_workspace(db_session: AsyncSession):
    """Create user and workspace for E2E testing."""
    from agent_os.auth.security import get_password_hash

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        username="e2e_user",
        email="e2e@example.com",
        password_hash=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    workspace_id = uuid.uuid4()
    workspace = Workspace(
        id=workspace_id,
        name="E2E Test Workspace",
        owner_id=user.id
    )
    db_session.add(workspace)
    await db_session.flush()

    user.default_workspace_id = workspace_id
    await db_session.commit()
    await db_session.refresh(user)

    return {"user": user, "workspace": workspace}


@pytest.fixture
def e2e_auth_headers(e2e_user_workspace):
    """Create authentication headers."""
    from agent_os.auth.security import create_access_token
    user = e2e_user_workspace["user"]
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# End-to-End Tests
# =============================================================================

class TestEndToEndStage2:
    """端到端测试：完整的 Agent 处理流程"""

    async def test_complete_flow_raw_to_processed(
        self,
        db_session: AsyncSession,
        e2e_user_workspace,
        e2e_test_client: TestClient,
        e2e_auth_headers: dict
    ):
        """测试完整流程：RAW → PROCESSED → Card → Today API"""
        workspace = e2e_user_workspace["workspace"]
        user = e2e_user_workspace["user"]

        # 步骤 1: 创建 RAW items
        raw_items = []
        for i in range(3):
            item = Item(
                workspace_id=workspace.id,
                creator_id=user.id,
                type="task",  # 必需字段
                title=f"Task {i}",
                content=f"TODO: Complete task number {i}",
                status=ItemStatus.RAW
            )
            db_session.add(item)
            raw_items.append(item)

        await db_session.commit()
        # 刷新以获取生成的 id
        for item in raw_items:
            await db_session.refresh(item)

        print(f"✅ Step 1: Created {len(raw_items)} RAW items")

        # 步骤 2: 调用 Agent Tick 处理
        response = e2e_test_client.post(
            "/api/v1/agent/tick",
            json={"max_items": 10},
            headers=e2e_auth_headers
        )

        assert response.status_code == 200
        tick_result = response.json()
        assert tick_result["processed"] == 3
        assert tick_result["succeeded"] == 3
        assert tick_result["failed"] == 0
        print(f"✅ Step 2: Agent tick processed {tick_result['succeeded']} items")

        # 步骤 3: 验证 items 已转换为 PROCESSED 状态
        for item in raw_items:
            await db_session.refresh(item)
            assert item.status == ItemStatus.PROCESSED
            assert item.title is not None
            assert item.summary is not None
            assert item.item_type is not None

        print("✅ Step 3: All items converted to PROCESSED status")

        # 步骤 4: 验证处理结果包含正确的数据
        for result in tick_result["results"]:
            assert result["success"] is True
            assert result["from_status"] == "raw"
            assert result["to_status"] == "processed"
            assert result["title"] is not None
            assert result["item_type"] in ["task", "note", "resource", "plan", "insight"]

        print("✅ Step 4: Processing results validated")

        # 步骤 5: 验证 Agent Status 端点
        response = e2e_test_client.get(
            "/api/v1/agent/status",
            headers=e2e_auth_headers
        )

        assert response.status_code == 200
        status = response.json()
        assert status["raw_count"] == 0  # 所有 RAW items 已处理
        assert status["processed_count"] == 3  # 3 个 PROCESSED items
        print(f"✅ Step 5: Agent status shows {status['processed_count']} processed items")

        # 步骤 6: 验证 Cards 已生成
        from sqlalchemy import select

        from agent_os.knowledge.models import Card

        card_count = 0
        for item in raw_items:
            await db_session.refresh(item)
            # Check metadata for card_id
            assert "card_id" in item.source_meta, f"Item {item.id} should have card_id in metadata"
            assert item.source_meta.get("card_generation") == "success"

            # Verify Card exists in database
            result = await db_session.execute(
                select(Card).where(Card.source_inbox_item_id == item.id)
            )
            card = result.scalar_one_or_none()
            assert card is not None, f"Card should exist for item {item.id}"
            card_count += 1
            print(f"   ✓ Card {card.id} generated for item {item.type}")

        assert card_count == 3, f"Expected 3 cards, found {card_count}"
        print(f"✅ Step 6: All {card_count} Cards generated successfully")

        print("\n🎉 Complete flow test PASSED! Including Card generation!")

    async def test_single_item_processing_flow(
        self,
        db_session: AsyncSession,
        e2e_user_workspace,
        e2e_test_client: TestClient,
        e2e_auth_headers: dict
    ):
        """测试单个 item 处理流程"""
        workspace = e2e_user_workspace["workspace"]
        user = e2e_user_workspace["user"]

        # 创建单个 RAW item
        item = Item(
            workspace_id=workspace.id,
            creator_id=user.id,
            type="note",  # 必需字段
            content="NOTE: This is an important concept about system design",
            status=ItemStatus.RAW
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        item_id = str(item.id)
        print(f"✅ Created RAW item: {item_id}")

        # 调用 process item endpoint
        response = e2e_test_client.post(
            f"/api/v1/agent/process/{item_id}",
            json={"force_reprocess": False},
            headers=e2e_auth_headers
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["from_status"] == "raw"
        assert result["to_status"] == "processed"
        assert result["item_type"] == "note"  # 应该被分类为 note

        print(f"✅ Item processed: {result['title']}")
        print(f"   Type: {result['item_type']}, Summary: {result['summary'][:50]}...")

        # 验证数据库中的状态
        await db_session.refresh(item)
        assert item.status == ItemStatus.PROCESSED
        assert item.item_type == ItemType.NOTE

        print("✅ Single item processing flow PASSED!")

    async def test_idempotent_processing(
        self,
        db_session: AsyncSession,
        e2e_user_workspace,
        e2e_test_client: TestClient,
        e2e_auth_headers: dict
    ):
        """测试幂等性：处理已处理的 item 应该跳过"""
        workspace = e2e_user_workspace["workspace"]
        user = e2e_user_workspace["user"]

        # 创建并处理一个 item
        item = Item(
            workspace_id=workspace.id,
            creator_id=user.id,
            type="task",  # 必需字段
            content="Task to test idempotency",
            status=ItemStatus.RAW
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        # 第一次处理
        response = e2e_test_client.post(
            f"/api/v1/agent/process/{item.id}",
            json={"force_reprocess": False},
            headers=e2e_auth_headers
        )

        assert response.status_code == 200
        first_result = response.json()
        assert first_result["success"] is True
        assert first_result["from_status"] == "raw"

        # 第二次处理（应该跳过）
        response = e2e_test_client.post(
            f"/api/v1/agent/process/{item.id}",
            json={"force_reprocess": False},
            headers=e2e_auth_headers
        )

        assert response.status_code == 200
        second_result = response.json()
        assert second_result["success"] is True
        assert "skipped" in second_result.get("metadata", {})

        print("✅ Idempotent processing test PASSED!")

    async def test_processing_generates_metadata(
        self,
        db_session: AsyncSession,
        e2e_user_workspace,
        e2e_test_client: TestClient,
        e2e_auth_headers: dict
    ):
        """测试处理过程生成正确的元数据"""
        workspace = e2e_user_workspace["workspace"]
        user = e2e_user_workspace["user"]

        item = Item(
            workspace_id=workspace.id,
            creator_id=user.id,
            type="task",  # 必需字段
            content="TODO: Implement the feature X with high priority",
            status=ItemStatus.RAW
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        # 处理 item
        response = e2e_test_client.post(
            f"/api/v1/agent/process/{item.id}",
            json={"force_reprocess": False},
            headers=e2e_auth_headers
        )

        assert response.status_code == 200
        result = response.json()

        # 验证元数据
        await db_session.refresh(item)
        metadata = item.source_meta or {}

        assert "classification_confidence" in metadata
        assert "summary_quality" in metadata
        assert "card_generation" in metadata or "card_generation_error" in metadata

        print(f"✅ Metadata generated: confidence={metadata.get('classification_confidence')}")
        print("✅ Processing metadata test PASSED!")


if __name__ == "__main__":
    print("=" * 70)
    print("End-to-End Integration Tests for Stage 2")
    print("=" * 70)
    print()

    pytest.main([__file__, "-v", "-s", "--tb=short"])
