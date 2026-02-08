"""Integration tests for Stage 3 API endpoints."""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# Import from server module
from agent_os.server.app import app
from agent_os.stage3.models import Skill, AgentDecision
from agent_os.auth.models import User
from agent_os.auth.security import create_access_token


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed_password"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Get authentication headers for test user."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestSkillAPIEndpoints:
    """Test Skill API endpoints."""

    async def test_create_skill(self, client, auth_headers):
        """Test creating a skill via API."""
        response = client.post(
            "/api/v1/agent/skills",
            json={
                "name": "API Test Skill",
                "description": "Created via API",
                "category": "decision",
                "steps": [
                    {
                        "order": 1,
                        "name": "analyze",
                        "agent_action": "classify_and_summarize",
                        "requires_confirmation": False
                    }
                ],
                "applicable_item_types": ["task"],
                "required_tags": ["test"]
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Test Skill"
        assert data["category"] == "decision"
        assert len(data["steps"]) == 1
        print(f"✅ Created skill via API: {data['name']}")

    async def test_list_skills(self, client, auth_headers, db_session):
        """Test listing skills via API."""
        # Create a test skill directly in DB
        skill = Skill(
            name="List Test Skill",
            description="For listing",
            category="decision",
            steps=[{"order": 1, "name": "step1"}],
            created_by=str(uuid.uuid4()),
            version="1.0"
        )
        db_session.add(skill)
        await db_session.commit()

        # List via API
        response = client.get(
            "/api/v1/agent/skills",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"✅ Listed {len(data)} skills via API")

    async def test_get_skill(self, client, auth_headers, db_session):
        """Test getting a skill by ID via API."""
        # Create a test skill
        skill = Skill(
            name="Get Test Skill",
            description="For getting",
            category="decision",
            steps=[{"order": 1, "name": "step1"}],
            created_by=str(uuid.uuid4()),
            version="1.0"
        )
        db_session.add(skill)
        await db_session.commit()
        await db_session.refresh(skill)

        # Get via API
        response = client.get(
            f"/api/v1/agent/skills/{skill.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(skill.id)
        assert data["name"] == "Get Test Skill"
        print(f"✅ Retrieved skill via API: {data['name']}")

    async def test_update_skill(self, client, auth_headers, db_session):
        """Test updating a skill via API."""
        # Create a test skill
        skill = Skill(
            name="Update Test Skill",
            description="Original description",
            category="decision",
            steps=[{"order": 1, "name": "step1"}],
            created_by=str(uuid.uuid4()),
            version="1.0"
        )
        db_session.add(skill)
        await db_session.commit()

        # Update via API
        response = client.put(
            f"/api/v1/agent/skills/{skill.id}",
            json={
                "name": "Updated Skill Name",
                "description": "Updated description"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Skill Name"
        assert data["description"] == "Updated description"
        print(f"✅ Updated skill via API: {data['name']}")

    async def test_delete_skill(self, client, auth_headers, db_session):
        """Test deleting a skill via API."""
        # Create a test skill
        skill = Skill(
            name="Delete Test Skill",
            description="For deletion",
            category="decision",
            steps=[{"order": 1, "name": "step1"}],
            created_by=str(uuid.uuid4()),
            version="1.0"
        )
        db_session.add(skill)
        await db_session.commit()

        # Delete via API
        response = client.delete(
            f"/api/v1/agent/skills/{skill.id}",
            headers=auth_headers
        )

        assert response.status_code == 204
        print(f"✅ Deleted skill via API")

    async def test_recommend_skills(self, client, auth_headers, db_session):
        """Test skill recommendation via API."""
        # Create test skills
        user_id = str(uuid.uuid4())

        skill1 = Skill(
            name="Task Skill",
            description="For tasks",
            category="decision",
            steps=[],
            created_by=user_id,
            applicable_item_types=["task"]
        )

        skill2 = Skill(
            name="Urgent Skill",
            description="For urgent items",
            category="decision",
            steps=[],
            created_by=user_id,
            required_tags=["urgent"]
        )

        db_session.add_all([skill1, skill2])
        await db_session.commit()

        # Get recommendations via API
        response = client.post(
            "/api/v1/agent/skills/recommend",
            json={
                "task_type": "task",
                "task_tags": ["urgent"],
                "limit": 10
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "score" in data[0]
        assert "match_reason" in data[0]
        print(f"✅ Got {len(data)} skill recommendations via API")


@pytest.mark.asyncio
class TestFlowAPIEndpoints:
    """Test Flow Execution API endpoints."""

    async def test_start_flow(self, client, auth_headers, db_session):
        """Test starting a flow via API."""
        # Create a test skill
        skill = Skill(
            name="Flow Test Skill",
            description="For flow testing",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "step1",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                }
            ],
            created_by=str(uuid.uuid4()),
            version="1.0"
        )
        db_session.add(skill)
        await db_session.commit()
        await db_session.refresh(skill)

        # Start flow via API
        task_id = str(uuid.uuid4())
        response = client.post(
            "/api/v1/agent/flow/start",
            json={
                "task_id": task_id,
                "skill_id": str(skill.id),
                "initial_context": {"test": "data"}
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] in ["running", "completed", "waiting_confirmation"]
        print(f"✅ Started flow via API: {data['execution_id']}")

    async def test_get_flow_status(self, client, auth_headers, db_session):
        """Test getting flow status via API."""
        # Create and start a flow
        skill = Skill(
            name="Status Test Skill",
            description="For status testing",
            category="decision",
            steps=[
                {
                    "order": 1,
                    "name": "step1",
                    "agent_action": "classify_and_summarize",
                    "requires_confirmation": False
                }
            ],
            created_by=str(uuid.uuid4()),
            version="1.0"
        )
        db_session.add(skill)
        await db_session.commit()
        await db_session.refresh(skill)

        task_id = str(uuid.uuid4())

        # Start flow
        start_response = client.post(
            "/api/v1/agent/flow/start",
            json={
                "task_id": task_id,
                "skill_id": str(skill.id),
                "initial_context": {}
            },
            headers=auth_headers
        )

        assert start_response.status_code == 201
        start_data = start_response.json()
        execution_id = start_data["execution_id"]

        # Get status
        status_response = client.get(
            f"/api/v1/agent/flow/{execution_id}/status",
            headers=auth_headers
        )

        assert status_response.status_code == 200
        status_data = status_response.json()
        assert "status" in status_data
        assert "current_step" in status_data
        print(f"✅ Got flow status via API: {status_data['status']}")


@pytest.mark.asyncio
class TestDecisionAPIEndpoints:
    """Test Decision API endpoints."""

    async def test_get_decision(self, client, auth_headers, db_session):
        """Test getting a decision via API."""
        # Create a test decision
        task_id = str(uuid.uuid4())
        decision = AgentDecision(
            task_id=task_id,
            step_name="test_step",
            options=[
                {
                    "id": "option_a",
                    "title": "Option A",
                    "description": "Test option",
                    "rationale": "Test rationale",
                    "risks": [],
                    "confidence": 0.8
                }
            ]
        )
        db_session.add(decision)
        await db_session.commit()
        await db_session.refresh(decision)

        # Get via API
        response = client.get(
            f"/api/v1/agent/decisions/{decision.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(decision.id)
        assert data["task_id"] == task_id
        assert len(data["options"]) == 1
        print(f"✅ Retrieved decision via API: {data['id']}")

    async def test_confirm_decision(self, client, auth_headers, db_session):
        """Test confirming a decision via API."""
        # Create a test decision
        task_id = str(uuid.uuid4())
        decision = AgentDecision(
            task_id=task_id,
            step_name="test_step",
            options=[
                {
                    "id": "option_a",
                    "title": "Option A",
                    "description": "Test option",
                    "rationale": "Test rationale",
                    "risks": [],
                    "confidence": 0.8
                }
            ]
        )
        db_session.add(decision)
        await db_session.commit()

        # Confirm via API
        response = client.post(
            f"/api/v1/agent/decisions/{decision.id}/confirm",
            json={
                "selected_option_id": "option_a"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["selected_option_id"] == "option_a"
        assert data["confirmed_at"] is not None
        print(f"✅ Confirmed decision via API: {data['id']}")

    async def test_get_task_decisions(self, client, auth_headers, db_session):
        """Test getting all decisions for a task via API."""
        task_id = str(uuid.uuid4())

        # Create multiple decisions
        decision1 = AgentDecision(
            task_id=task_id,
            step_name="step1",
            options=[{"id": "opt1", "title": "Opt1", "description": "D1", "rationale": "R1", "risks": [], "confidence": 0.5}]
        )
        decision2 = AgentDecision(
            task_id=task_id,
            step_name="step2",
            options=[{"id": "opt2", "title": "Opt2", "description": "D2", "rationale": "R2", "risks": [], "confidence": 0.5}]
        )

        db_session.add_all([decision1, decision2])
        await db_session.commit()

        # Get via API
        response = client.get(
            f"/api/v1/agent/tasks/{task_id}/decisions",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        print(f"✅ Retrieved {len(data)} decisions for task via API")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
