"""API integration tests for Task management endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.test_app import test_app as app

from agent_os.auth.jwt_handler import create_access_token
from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash
from agent_os.db.base import Base
from agent_os.db.session import get_db
from agent_os.tasks.models import Task

# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
async def in_memory_db():
    """Create in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture
async def db_session(in_memory_db):
    """Create async database session for testing."""
    async_session_maker = async_sessionmaker(
        bind=in_memory_db,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def test_client(db_session):
    """Create test client with database session override."""
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override both get_db functions
    from agent_os.db import base as db_base
    app.dependency_overrides[db_base.get_db] = override_get_db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    """Create and authenticate test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123")
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user):
    """Get authentication headers for test user."""
    token = create_access_token(user_id=test_user.id)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Task CRUD API Tests
# =============================================================================

class TestTaskAPI:
    """Test Task API endpoints."""

    def test_create_task(self, test_client, auth_headers):
        """Test creating a new task."""
        response = test_client.post(
            "/api/v1/tasks",
            json={
                "title": "Test Task",
                "description": "Task description",
                "type": "task",
                "priority": 7
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Task"
        assert data["description"] == "Task description"
        assert data["type"] == "task"
        assert data["priority"] == 7
        assert data["status"] == "pending"
        assert "id" in data

    def test_create_task_with_defaults(self, test_client, auth_headers):
        """Test creating task with default values."""
        response = test_client.post(
            "/api/v1/tasks",
            json={"title": "Simple Task"},
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Simple Task"
        assert data["type"] == "task"
        assert data["status"] == "pending"
        assert data["priority"] == 5

    def test_create_task_invalid_type(self, test_client, auth_headers):
        """Test creating task with invalid type."""
        response = test_client.post(
            "/api/v1/tasks",
            json={"title": "Test", "type": "invalid"},
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_get_task(self, test_client, db_session, test_user, auth_headers):
        """Test getting a specific task."""
        import asyncio

        async def create_task():
            task = Task(
                user_id=test_user.id,
                title="Test Task",
                type="task"
            )
            db_session.add(task)
            await db_session.commit()
            await db_session.refresh(task)
            return task

        task = asyncio.run(create_task())

        # Get the task
        response = test_client.get(
            f"/api/v1/tasks/{task.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task.id
        assert data["title"] == "Test Task"

    def test_get_task_not_found(self, test_client, auth_headers):
        """Test getting non-existent task."""
        response = test_client.get(
            "/api/v1/tasks/999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_list_tasks_empty(self, test_client, auth_headers):
        """Test listing tasks when empty."""
        response = test_client.get(
            "/api/v1/tasks",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_tasks_with_data(self, test_client, db_session, test_user, auth_headers):
        """Test listing tasks with data."""
        # Create multiple tasks
        for i in range(3):
            task = Task(
                user_id=test_user.id,
                title=f"Task {i}",
                status="pending"
            )
            db_session.add(task)
        await db_session.commit()

        # List tasks
        response = test_client.get(
            "/api/v1/tasks",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_tasks_with_status_filter(self, test_client, db_session, test_user, auth_headers):
        """Test listing tasks with status filter."""
        # Create tasks with different statuses
        task1 = Task(user_id=test_user.id, title="Pending", status="pending")
        task2 = Task(user_id=test_user.id, title="In Progress", status="in_progress")
        db_session.add_all([task1, task2])
        await db_session.commit()

        # Filter by status
        response = test_client.get(
            "/api/v1/tasks?status=pending",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Pending"

    async def test_list_tasks_with_type_filter(self, test_client, db_session, test_user, auth_headers):
        """Test listing tasks with type filter."""
        # Create tasks with different types
        task1 = Task(user_id=test_user.id, title="Task", type="task")
        task2 = Task(user_id=test_user.id, title="Habit", type="habit")
        db_session.add_all([task1, task2])
        await db_session.commit()

        # Filter by type
        response = test_client.get(
            "/api/v1/tasks?type=habit",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "habit"

    async def test_list_tasks_with_pagination(self, test_client, db_session, test_user, auth_headers):
        """Test pagination for tasks."""
        # Create 5 tasks
        for i in range(5):
            task = Task(user_id=test_user.id, title=f"Task {i}")
            db_session.add(task)
        await db_session.commit()

        # Get first page
        response = test_client.get(
            "/api/v1/tasks?page=1&page_size=3",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3
        assert data["page"] == 1

    async def test_update_task(self, test_client, db_session, test_user, auth_headers):
        """Test updating a task."""
        task = Task(
            user_id=test_user.id,
            title="Original",
            type="task"
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = test_client.put(
            f"/api/v1/tasks/{task.id}",
            json={"title": "Updated", "priority": 8},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["priority"] == 8

    async def test_update_task_status(self, test_client, db_session, test_user, auth_headers):
        """Test updating task status via PATCH."""
        task = Task(
            user_id=test_user.id,
            title="Test",
            status="pending"
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = test_client.patch(
            f"/api/v1/tasks/{task.id}/status",
            json={"status": "completed"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    async def test_delete_task(self, test_client, db_session, test_user, auth_headers):
        """Test deleting a task."""
        task = Task(
            user_id=test_user.id,
            title="To be deleted"
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = test_client.delete(
            f"/api/v1/tasks/{task.id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify deletion
        get_response = test_client.get(
            f"/api/v1/tasks/{task.id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404

    def test_unauthorized_access(self, test_client):
        """Test accessing API without authentication."""
        response = test_client.get("/api/v1/tasks")
        assert response.status_code == 401


# =============================================================================
# Batch Operations Tests
# =============================================================================

class TestBatchOperations:
    """Test batch operation endpoints."""

    def test_create_tasks_batch(self, test_client, auth_headers):
        """Test creating tasks in batch."""
        response = test_client.post(
            "/api/v1/tasks/batch",
            json={
                "tasks": [
                    {"title": "Task 1"},
                    {"title": "Task 2"},
                    {"title": "Task 3"}
                ]
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_create_tasks_batch_empty(self, test_client, auth_headers):
        """Test creating empty batch."""
        response = test_client.post(
            "/api/v1/tasks/batch",
            json={"tasks": []},
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_update_tasks_batch(self, test_client, db_session, test_user, auth_headers):
        """Test updating tasks in batch."""
        import asyncio

        async def create_tasks():
            task1 = Task(user_id=test_user.id, title="Task 1", status="pending")
            task2 = Task(user_id=test_user.id, title="Task 2", status="pending")
            db_session.add_all([task1, task2])
            await db_session.commit()
            await db_session.refresh(task1)
            await db_session.refresh(task2)
            return task1.id, task2.id

        task1_id, task2_id = asyncio.run(create_tasks())

        # Update batch
        response = test_client.put(
            "/api/v1/tasks/batch",
            json={
                "task_ids": [task1_id, task2_id],
                "updates": {"status": "completed"}
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == 2

    def test_delete_tasks_batch(self, test_client, db_session, test_user, auth_headers):
        """Test deleting tasks in batch."""
        import asyncio

        async def create_tasks():
            task1 = Task(user_id=test_user.id, title="Task 1")
            task2 = Task(user_id=test_user.id, title="Task 2")
            db_session.add_all([task1, task2])
            await db_session.commit()
            await db_session.refresh(task1)
            await db_session.refresh(task2)
            return task1.id, task2.id

        task1_id, task2_id = asyncio.run(create_tasks())

        # Delete batch
        response = test_client.delete(
            f"/api/v1/tasks/batch?task_ids={task1_id}&task_ids={task2_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2


# =============================================================================
# Today's Tasks Tests
# =============================================================================

class TestTodayTasks:
    """Test today's tasks aggregation."""

    def test_get_today_tasks_empty(self, test_client, auth_headers):
        """Test getting today's tasks when empty."""
        response = test_client.get(
            "/api/v1/tasks/today",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert "tasks" in data
        assert "stats" in data
        assert data["stats"]["total"] == 0

    async def test_get_today_tasks_with_data(self, test_client, db_session, test_user, auth_headers):
        """Test getting today's tasks with data."""
        from datetime import date

        # Create task for today
        task = Task(
            user_id=test_user.id,
            title="Today's Task",
            scheduled_date=date.today()
        )
        db_session.add(task)
        await db_session.commit()

        # Get today's tasks
        response = test_client.get(
            "/api/v1/tasks/today",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["total"] == 1
        assert len(data["tasks"]) == 1

    def test_get_task_stats(self, test_client, auth_headers):
        """Test getting task statistics."""
        response = test_client.get(
            "/api/v1/tasks/stats",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "pending" in data
        assert "in_progress" in data
        assert "completed" in data
