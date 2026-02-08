"""Tests for Task Schema validation."""

import pytest
from datetime import date, datetime
from agent_os.tasks.schema import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskList,
    TaskStatusUpdate,
    TaskStats,
    TodayTasksResponse,
    TaskBatchCreate,
    TaskBatchUpdate,
    TaskQueryParams,
)


class TestTaskCreate:
    """Test TaskCreate schema."""

    def test_task_create_valid(self):
        """Test valid task creation."""
        task = TaskCreate(
            title="Test Task",
            description="Test description",
            type="task",
            priority=5
        )
        assert task.title == "Test Task"
        assert task.description == "Test description"
        assert task.type == "task"
        assert task.priority == 5
        assert task.status == "pending"
        assert task.source == "manual"

    def test_task_create_default_values(self):
        """Test default values."""
        task = TaskCreate(title="Simple Task")
        assert task.type == "task"
        assert task.status == "pending"
        assert task.source == "manual"
        assert task.priority == 5
        assert task.scheduled_date is None

    def test_task_create_invalid_type(self):
        """Test invalid task type."""
        with pytest.raises(ValueError):
            TaskCreate(title="Test", type="invalid")

    def test_task_create_invalid_status(self):
        """Test invalid status."""
        with pytest.raises(ValueError):
            TaskCreate(title="Test", status="invalid")

    def test_task_create_invalid_source(self):
        """Test invalid source."""
        with pytest.raises(ValueError):
            TaskCreate(title="Test", source="invalid")

    def test_task_create_priority_too_low(self):
        """Test priority too low."""
        with pytest.raises(ValueError):
            TaskCreate(title="Test", priority=0)

    def test_task_create_priority_too_high(self):
        """Test priority too high."""
        with pytest.raises(ValueError):
            TaskCreate(title="Test", priority=11)

    def test_task_create_title_too_long(self):
        """Test title too long."""
        with pytest.raises(ValueError):
            TaskCreate(title="x" * 201)

    def test_task_create_title_empty(self):
        """Test empty title."""
        with pytest.raises(ValueError):
            TaskCreate(title="")

    def test_task_create_all_types(self):
        """Test all valid task types."""
        for task_type in ["task", "habit", "goal"]:
            task = TaskCreate(title="Test", type=task_type)
            assert task.type == task_type

    def test_task_create_all_statuses(self):
        """Test all valid statuses."""
        for status_val in ["pending", "in_progress", "completed"]:
            task = TaskCreate(title="Test", status=status_val)
            assert task.status == status_val

    def test_task_create_all_sources(self):
        """Test all valid sources."""
        for source in ["manual", "ai_generated", "recurring"]:
            task = TaskCreate(title="Test", source=source)
            assert task.source == source

    def test_task_create_with_scheduled_date(self):
        """Test task with scheduled date."""
        task = TaskCreate(
            title="Test",
            scheduled_date=date(2026, 1, 28)
        )
        assert task.scheduled_date == date(2026, 1, 28)


class TestTaskUpdate:
    """Test TaskUpdate schema."""

    def test_task_update_valid(self):
        """Test valid task update."""
        update = TaskUpdate(title="Updated Title")
        assert update.title == "Updated Title"

    def test_task_update_multiple_fields(self):
        """Test updating multiple fields."""
        update = TaskUpdate(
            title="Updated",
            status="in_progress",
            priority=7
        )
        assert update.title == "Updated"
        assert update.status == "in_progress"
        assert update.priority == 7

    def test_task_update_all_fields_optional(self):
        """Test all fields are optional."""
        update = TaskUpdate()
        assert update.title is None
        assert update.status is None
        assert update.priority is None

    def test_task_update_invalid_type(self):
        """Test invalid type in update."""
        with pytest.raises(ValueError):
            TaskUpdate(type="invalid")

    def test_task_update_with_completed_at(self):
        """Test update with completed_at."""
        completed_at = datetime(2026, 1, 28, 12, 0, 0)
        update = TaskUpdate(completed_at=completed_at)
        assert update.completed_at == completed_at


class TaskStatusUpdateTest:
    """Test TaskStatusUpdate schema."""

    def test_status_update_valid(self):
        """Test valid status update."""
        update = TaskStatusUpdate(status="completed")
        assert update.status == "completed"
        assert update.completed_at is None

    def test_status_update_with_timestamp(self):
        """Test status update with timestamp."""
        completed_at = datetime(2026, 1, 28, 12, 0, 0)
        update = TaskStatusUpdate(
            status="completed",
            completed_at=completed_at
        )
        assert update.completed_at == completed_at

    def test_status_update_invalid_status(self):
        """Test invalid status."""
        with pytest.raises(ValueError):
            TaskStatusUpdate(status="invalid")


class TestTaskResponse:
    """Test TaskResponse schema."""

    def test_task_response_from_dict(self):
        """Test creating response from dict."""
        data = {
            "id": 1,
            "user_id": 1,
            "title": "Test Task",
            "description": "Description",
            "type": "task",
            "source": "manual",
            "status": "pending",
            "priority": 5,
            "scheduled_date": None,
            "completed_at": None,
            "created_at": "2026-01-28T00:00:00",
            "updated_at": "2026-01-28T00:00:00"
        }
        response = TaskResponse(**data)
        assert response.id == 1
        assert response.user_id == 1
        assert response.title == "Test Task"


class TestTaskList:
    """Test TaskList schema."""

    def test_task_list(self):
        """Test task list schema."""
        data = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20
        }
        task_list = TaskList(**data)
        assert task_list.items == []
        assert task_list.total == 0
        assert task_list.page == 1
        assert task_list.page_size == 20


class TestTaskStats:
    """Test TaskStats schema."""

    def test_task_stats_default(self):
        """Test default stats."""
        stats = TaskStats()
        assert stats.total == 0
        assert stats.pending == 0
        assert stats.in_progress == 0
        assert stats.completed == 0
        assert stats.by_priority == {}
        assert stats.by_type == {}

    def test_task_stats_with_data(self):
        """Test stats with data."""
        stats = TaskStats(
            total=10,
            pending=5,
            in_progress=3,
            completed=2,
            by_priority={"1": 2, "5": 5, "10": 3},
            by_type={"task": 7, "habit": 2, "goal": 1}
        )
        assert stats.total == 10
        assert stats.pending == 5
        assert stats.by_priority["5"] == 5


class TestTodayTasksResponse:
    """Test TodayTasksResponse schema."""

    def test_today_tasks_response(self):
        """Test today's tasks response."""
        data = {
            "date": "2026-01-28",
            "tasks": [],
            "stats": {"total": 0, "pending": 0, "in_progress": 0, "completed": 0},
            "knowledge_context": None
        }
        response = TodayTasksResponse(**data)
        assert response.date == date(2026, 1, 28)
        assert response.tasks == []
        assert response.stats.total == 0


class TestTaskBatchCreate:
    """Test TaskBatchCreate schema."""

    def test_batch_create_valid(self):
        """Test valid batch creation."""
        batch = TaskBatchCreate(tasks=[
            TaskCreate(title="Task 1"),
            TaskCreate(title="Task 2"),
            TaskCreate(title="Task 3")
        ])
        assert len(batch.tasks) == 3

    def test_batch_create_empty(self):
        """Test empty batch."""
        with pytest.raises(ValueError):
            TaskBatchCreate(tasks=[])

    def test_batch_create_too_many(self):
        """Test batch with too many tasks."""
        tasks = [TaskCreate(title=f"Task {i}") for i in range(51)]
        with pytest.raises(ValueError):
            TaskBatchCreate(tasks=tasks)


class TestTaskBatchUpdate:
    """Test TaskBatchUpdate schema."""

    def test_batch_update_valid(self):
        """Test valid batch update."""
        batch = TaskBatchUpdate(
            task_ids=[1, 2, 3],
            updates=TaskUpdate(status="completed")
        )
        assert len(batch.task_ids) == 3
        assert batch.updates.status == "completed"

    def test_batch_update_empty_ids(self):
        """Test empty task IDs."""
        with pytest.raises(ValueError):
            TaskBatchUpdate(
                task_ids=[],
                updates=TaskUpdate(status="completed")
            )


class TestTaskQueryParams:
    """Test TaskQueryParams schema."""

    def test_query_params_default(self):
        """Test default query parameters."""
        params = TaskQueryParams()
        assert params.status is None
        assert params.type is None
        assert params.sort_by == "created_at"
        assert params.sort_order == "desc"

    def test_query_params_with_filters(self):
        """Test query parameters with filters."""
        params = TaskQueryParams(
            status="pending",
            type="task",
            priority_min=3,
            priority_max=7,
            sort_by="priority",
            sort_order="asc"
        )
        assert params.status == "pending"
        assert params.priority_min == 3
        assert params.priority_max == 7
        assert params.sort_by == "priority"
        assert params.sort_order == "asc"

    def test_query_params_invalid_sort_by(self):
        """Test invalid sort_by field."""
        with pytest.raises(ValueError):
            TaskQueryParams(sort_by="invalid")

    def test_query_params_invalid_sort_order(self):
        """Test invalid sort order."""
        with pytest.raises(ValueError):
            TaskQueryParams(sort_order="invalid")

    def test_query_params_invalid_priority(self):
        """Test invalid priority range."""
        with pytest.raises(ValueError):
            TaskQueryParams(priority_min=0)

        with pytest.raises(ValueError):
            TaskQueryParams(priority_max=11)

    def test_query_params_with_date_range(self):
        """Test query parameters with date range."""
        params = TaskQueryParams(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31)
        )
        assert params.date_from == date(2026, 1, 1)
        assert params.date_to == date(2026, 1, 31)
