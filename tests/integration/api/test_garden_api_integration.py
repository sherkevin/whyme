"""Garden & Today API Integration Tests - PRD9 Module 3.

PRD10 NOTICE
============

This file targets the PRD9 garden router (``/api/v1/garden/nodes``,
``/api/v1/garden/edges/batch``, ``/api/v1/garden/nodes/{id}`` and the legacy
``/api/v1/today/insight``). PRD10 replaced that surface with
``/api/v1/garden/overview`` + ``/api/v1/garden/graph`` (covered by
``tests/integration/api/test_prd10_garden_api.py``) and a new
``/api/v1/today`` aggregator (covered by
``tests/integration/api/prd10/test_prd10_today_api.py``).

Additional incompatibilities:

* ``httpx 0.28`` removed ``TestClient(app=app)``-style construction; the file
  uses ``data=`` form-login while PRD10's auth router requires JSON bodies.
* The PRD9 garden_router is no longer mounted under ``app`` because the PRD10
  router takes its place at the same prefix.

The whole module is skipped at collection time. Re-enable only if the PRD9
garden surface is intentionally restored alongside the PRD10 one.
"""

import pytest

pytest.skip(
    "Legacy PRD9 garden tests; superseded by PRD10 garden + today tests.",
    allow_module_level=True,
)

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash
from agent_os.db import base as db_base
from agent_os.db.session import get_db as session_get_db
from agent_os.garden.models import DailyInsight, KnowledgeCardLink
from agent_os.items.models import Item, Workspace
from agent_os.server.app import app

# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
async def http_client(db_session):
    """Create an async HTTP client with ASGITransport and db session override."""
    # Override get_db dependency
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[db_base.get_db] = override_get_db
    app.dependency_overrides[session_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_test_user(db_session):
    """Create a test user for auth tests."""
    user = User(
        id=uuid.uuid4(),
        username="test_garden_api_user",
        email="test_garden_api@example.com",
        password_hash=get_password_hash("test_pass_123"),
        is_active=True,
        settings={"daily_goal": 10, "theme": "light", "language": "zh"}
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_workspace(db_session, auth_test_user):
    """Create a test workspace."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Garden API Test Workspace",
        owner_id=auth_test_user.id
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def test_items(db_session, test_workspace, auth_test_user, count=15):
    """Create test items (nodes)."""
    items = []
    now = datetime.now(UTC)

    for i in range(count):
        item = Item(
            workspace_id=test_workspace.id,
            creator_id=auth_test_user.id,
            type="note" if i % 3 == 0 else "card" if i % 3 == 1 else "task",
            title=f"Test Item {i}",
            content=f"Content for item {i} - this is a longer content for snippet testing",
            status="active",
            created_at=now - timedelta(days=count - i)
        )
        db_session.add(item)
        items.append(item)

    await db_session.commit()
    return items


@pytest.fixture
async def test_edges(db_session, test_workspace, test_items):
    """Create test edges between items with varying strengths."""
    edges = []

    # Create edges with different strengths
    for i in range(len(test_items) - 1):
        edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=test_items[i].id,
            to_id=test_items[i + 1].id,
            type="related",
            relation_strength=0.3 + (i * 0.05),
            is_active=True
        )
        db_session.add(edge)
        edges.append(edge)

    # Create some strong edges (>= 0.5 threshold)
    if len(test_items) >= 5:
        strong_edge1 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=test_items[0].id,
            to_id=test_items[5].id,
            type="support",
            relation_strength=0.9,
            is_active=True
        )
        strong_edge2 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=test_items[0].id,
            to_id=test_items[6].id,
            type="reference",
            relation_strength=0.8,
            is_active=True
        )
        weak_edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=test_items[0].id,
            to_id=test_items[7].id,
            type="contradict",
            relation_strength=0.1,
            is_active=True
        )
        db_session.add_all([strong_edge1, strong_edge2, weak_edge])
        edges.extend([strong_edge1, strong_edge2, weak_edge])

    await db_session.commit()
    return edges


@pytest.fixture
async def test_insights(db_session, test_workspace, auth_test_user):
    """Create test insights with various statuses and levels."""
    insights = []
    now = datetime.now(UTC)
    today = now.date()

    insights_data = [
        ("Stable Insight Level 2", "stable", 2, 0, "hash_stable_l2"),
        ("Stable Insight Level 3", "stable", 3, 0, "hash_stable_l3"),
        ("Candidate Insight", "candidate", 2, 0, "hash_candidate"),
        ("Draft Insight", "draft", 2, 0, "hash_draft"),
        ("Rejected Insight", "rejected", 3, 0, "hash_rejected"),
        ("Stable Level 1", "stable", 1, 0, "hash_stable_l1"),
        ("Old Stable Insight", "stable", 2, -5, "hash_old_stable"),
    ]

    for title, status, level, days_offset, canonical_hash in insights_data:
        created_at = datetime.combine(today + timedelta(days=days_offset), datetime.min.time(), tzinfo=UTC)
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=auth_test_user.id,
            title=title,
            content=f"Content for {title}. This is the rationale explanation.",
            status=status,
            level=level,
            canonical_hash=canonical_hash,
            stability_score=0.8 if status == "stable" else 0.3,
            evidence_count=3 if status == "stable" else 1,
            source_item_ids=None,  # Set to None to avoid UUID parsing issues
            created_at=created_at,
            updated_at=created_at
        )
        db_session.add(insight)
        insights.append(insight)

    await db_session.commit()
    return insights


# ============================================================================
# Helper: Get Auth Token
# ============================================================================

async def get_auth_token(client: AsyncClient, username: str, password: str) -> str:
    """Helper to get auth token."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


# ============================================================================
# Test 1: Schema Validation - POST /garden/edges/batch
# ============================================================================

class TestSchemaValidation:
    """Test schema validation for API endpoints."""

    @pytest.mark.asyncio
    async def test_edges_batch_invalid_node_ids_format(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace
    ):
        """Test that invalid node_ids format returns 422."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        # Test 1: node_ids as string instead of array (should fail)
        response = await http_client.post(
            "/api/v1/garden/edges/batch",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id)},
            json={"node_ids": "not-an-array"}
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

        # Test 2: node_ids as number (should fail)
        response = await http_client.post(
            "/api/v1/garden/edges/batch",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id)},
            json={"node_ids": 12345}
        )
        assert response.status_code == 422


# ============================================================================
# Test 2: Backward Compatibility - GET /auth/me with stats
# ============================================================================

class TestAuthMeBackwardCompatibility:
    """Test backward compatibility of /auth/me endpoint with stats."""

    @pytest.mark.asyncio
    async def test_auth_me_returns_original_fields(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items
    ):
        """Test that /auth/me returns all original fields plus stats."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        response = await http_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id)}
        )

        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        # Verify ORIGINAL fields are still present (backward compatibility)
        assert "id" in data
        assert "username" in data
        assert "email" in data
        assert "settings" in data
        assert "is_active" in data
        assert "created_at" in data

        # Verify values are correct
        assert data["username"] == auth_test_user.username
        assert data["email"] == auth_test_user.email
        assert data["is_active"] == auth_test_user.is_active

        # Verify NEW stats field is present
        assert "stats" in data, "New field 'stats' is missing"
        assert data["stats"] is not None, "Stats should not be None when workspace_id provided"

        # Verify stats structure
        stats = data["stats"]
        assert "total_notes" in stats
        assert "neural_connections" in stats
        assert "generated_insights" in stats

    @pytest.mark.asyncio
    async def test_auth_me_without_workspace_id(
        self,
        http_client: AsyncClient,
        auth_test_user: User
    ):
        """Test that /auth/me without workspace_id returns stats as None."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        response = await http_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["username"] == auth_test_user.username
        assert "stats" in data
        assert data["stats"] is None


# ============================================================================
# Test 3: Pagination and Filtering - GET /garden/nodes
# ============================================================================

class TestGardenNodesPagination:
    """Test pagination and filtering for /garden/nodes endpoint."""

    @pytest.mark.asyncio
    async def test_nodes_limit_parameter(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items
    ):
        """Test that limit=5 returns exactly 5 items."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        response = await http_client.get(
            "/api/v1/garden/nodes",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id), "limit": 5, "offset": 0}
        )

        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        assert "data" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        assert len(data["data"]) == 5, f"Expected 5 items, got {len(data['data'])}"
        assert data["limit"] == 5
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_nodes_offset_parameter(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items
    ):
        """Test that offset works correctly with limit."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        response1 = await http_client.get(
            "/api/v1/garden/nodes",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id), "limit": 5, "offset": 0}
        )

        response2 = await http_client.get(
            "/api/v1/garden/nodes",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id), "limit": 5, "offset": 5}
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        ids1 = {node["id"] for node in data1["data"]}
        ids2 = {node["id"] for node in data2["data"]}
        assert ids1.isdisjoint(ids2), "Pagination should return non-overlapping results"

    @pytest.mark.asyncio
    async def test_nodes_types_filter(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items
    ):
        """Test types filter returns only matching items."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        response = await http_client.get(
            "/api/v1/garden/nodes",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id), "types": ["note"], "limit": 100}
        )

        assert response.status_code == 200
        data = response.json()

        for node in data["data"]:
            assert node["object_type"] == "note"

    @pytest.mark.asyncio
    async def test_nodes_response_schema(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items
    ):
        """Test that response matches PRD9 schema exactly."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        response = await http_client.get(
            "/api/v1/garden/nodes",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id), "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()

        for node in data["data"]:
            assert "id" in node
            assert "object_type" in node
            assert "title" in node
            assert "created_at" in node
            assert "strong_connection_count" in node
            assert "snippet" in node


# ============================================================================
# Test 4: Detail and Sorting - GET /garden/nodes/{id}
# ============================================================================

class TestGardenNodeDetail:
    """Test node detail endpoint with connected nodes sorting."""

    @pytest.mark.asyncio
    async def test_node_detail_connected_nodes_sorted(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items,
        test_edges
    ):
        """Test connected_nodes are sorted by relation_strength descending."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        target_item = test_items[0]
        response = await http_client.get(
            f"/api/v1/garden/nodes/{target_item.id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id)}
        )

        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        assert "connected_nodes" in data
        connected = data["connected_nodes"]

        # Verify max 5 connected nodes
        assert len(connected) <= 5, f"Should return at most 5 connected nodes, got {len(connected)}"

        # Verify sorted by relation_strength descending
        if len(connected) > 1:
            strengths = [node["relation_strength"] for node in connected]
            assert strengths == sorted(strengths, reverse=True), \
                f"connected_nodes not sorted by relation_strength desc: {strengths}"

    @pytest.mark.asyncio
    async def test_node_detail_response_schema(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items
    ):
        """Test that detail response matches PRD9 schema."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        target_item = test_items[0]
        response = await http_client.get(
            f"/api/v1/garden/nodes/{target_item.id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id)}
        )

        assert response.status_code == 200
        data = response.json()

        for node in data["connected_nodes"]:
            assert "id" in node
            assert "object_type" in node
            assert "relation_strength" in node
            assert "jump_url" in node

    @pytest.mark.asyncio
    async def test_node_detail_not_found(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace
    ):
        """Test 404 for non-existent node."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        fake_id = str(uuid.uuid4())
        response = await http_client.get(
            f"/api/v1/garden/nodes/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id)}
        )

        assert response.status_code == 404


# ============================================================================
# Test 5: Today Insight - GET /today/insight
# ============================================================================

class TestTodayInsight:
    """Test today insight endpoint with required fields."""

    @pytest.mark.asyncio
    async def test_insight_required_fields(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_insights
    ):
        """Test that insight response contains required fields."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        today = datetime.now(UTC).date().isoformat()
        response = await http_client.get(
            "/api/v1/today/insight",
            headers={"Authorization": f"Bearer {token}"},
            params={"day": today, "workspace_id": str(test_workspace.id)}
        )

        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        assert "data" in data
        assert "day" in data

        for insight in data["data"]:
            assert "claim" in insight
            assert "rationale" in insight
            assert "implications" in insight
            assert "sources" in insight

    @pytest.mark.asyncio
    async def test_insight_filters_stable_level2_plus(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_insights
    ):
        """Test that only stable insights with level >= 2 are returned."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        today = datetime.now(UTC).date().isoformat()
        response = await http_client.get(
            "/api/v1/today/insight",
            headers={"Authorization": f"Bearer {token}"},
            params={"day": today, "workspace_id": str(test_workspace.id)}
        )

        assert response.status_code == 200
        data = response.json()

        for insight in data["data"]:
            assert insight["status"] == "stable"
            assert insight["level"] >= 2

    @pytest.mark.asyncio
    async def test_insight_validation_error_invalid_date(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace
    ):
        """Test that invalid date format returns 422."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        response = await http_client.get(
            "/api/v1/today/insight",
            headers={"Authorization": f"Bearer {token}"},
            params={"day": "invalid-date", "workspace_id": str(test_workspace.id)}
        )

        assert response.status_code == 422


# ============================================================================
# End to End: Complete Garden Flow
# ============================================================================

class TestCompleteGardenFlow:
    """Test complete Garden API flow."""

    @pytest.mark.asyncio
    async def test_full_garden_workflow(
        self,
        http_client: AsyncClient,
        auth_test_user: User,
        test_workspace: Workspace,
        test_items,
        test_edges
    ):
        """Test complete workflow: nodes list -> edge batch -> node detail."""
        token = await get_auth_token(http_client, auth_test_user.username, "test_pass_123")

        # 1. Get nodes list
        nodes_response = await http_client.get(
            "/api/v1/garden/nodes",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id), "limit": 10}
        )
        assert nodes_response.status_code == 200
        nodes = nodes_response.json()["data"]
        assert len(nodes) > 0

        # 2. Use node IDs to query edges
        node_ids = [node["id"] for node in nodes]
        edges_response = await http_client.post(
            "/api/v1/garden/edges/batch",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace_id": str(test_workspace.id)},
            json={"node_ids": node_ids}
        )
        assert edges_response.status_code == 200
        edges_data = edges_response.json()
        assert "data" in edges_data

        # 3. Get detail for first node
        if nodes:
            detail_response = await http_client.get(
                f"/api/v1/garden/nodes/{nodes[0]['id']}",
                headers={"Authorization": f"Bearer {token}"},
                params={"workspace_id": str(test_workspace.id)}
            )
            assert detail_response.status_code == 200
            detail = detail_response.json()
            assert "connected_nodes" in detail


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
