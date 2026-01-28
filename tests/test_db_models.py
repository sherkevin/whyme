"""Test database models and connections.

IMPORTANT: These tests MUST NOT require any external dependencies like PostgreSQL.
All tests use pure Python mocks and validate model definitions only.
"""

import pytest
from unittest.mock import Mock
from datetime import datetime, date

from agent_os.auth.models import User, UserSettings
from agent_os.knowledge.models import InboxItem, Card
from agent_os.tasks.models import Task


class TestUserModels:
    """Test User and UserSettings models."""

    def test_create_user_attributes(self):
        """Test creating a user with correct attributes."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_here"
        )

        # Verify attributes (without database)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password_here"
        assert user.id is None  # No ID until committed

    def test_user_settings_relationship_structure(self):
        """Test user-settings relationship structure (without database)."""
        # Create user and settings
        user = User(
            username="testuser2",
            email="test2@example.com",
            hashed_password="hashed_password_here"
        )

        settings = UserSettings(
            daily_goal=15,
            theme="dark"
        )

        # Verify settings attributes (without database relationship)
        assert settings.daily_goal == 15
        assert settings.theme == "dark"
        assert settings.user_id is None  # Not linked yet

    def test_user_field_types(self):
        """Test field types are correct."""
        user = User(username="user", email="email@test.com", hashed_password="hash")

        assert isinstance(user.username, str)
        assert isinstance(user.email, str)
        assert isinstance(user.hashed_password, str)

    def test_settings_field_types(self):
        """Test settings field types."""
        settings = UserSettings(daily_goal=10, theme="light", language="zh")

        assert isinstance(settings.daily_goal, int)
        assert isinstance(settings.theme, str)
        assert isinstance(settings.language, str)


class TestKnowledgeModels:
    """Test InboxItem and Card models."""

    def test_inbox_item_attributes(self):
        """Test inbox item attributes."""
        inbox_item = InboxItem(
            user_id=1,
            content="Test content",
            status="raw",
            source="manual"
        )

        # Verify attributes
        assert inbox_item.user_id == 1
        assert inbox_item.content == "Test content"
        assert inbox_item.status == "raw"
        assert inbox_item.source == "manual"

    def test_inbox_item_field_types(self):
        """Test inbox item field types."""
        inbox_item = InboxItem(
            user_id=1,
            content="Content",
            status="processed"
        )

        assert isinstance(inbox_item.content, str)
        assert isinstance(inbox_item.status, str)
        assert isinstance(inbox_item.source, str) or inbox_item.source is None

    def test_card_attributes(self):
        """Test card attributes."""
        card = Card(
            user_id=1,
            title="Test Card",
            content="Test card content",
            para_type="concept",
            tags=["python", "test"]
        )

        # Verify attributes
        assert card.title == "Test Card"
        assert card.content == "Test card content"
        assert card.para_type == "concept"
        assert card.tags == ["python", "test"]

    def test_card_field_types(self):
        """Test card field types."""
        card = Card(
            user_id=1,
            title="Card",
            content="Content",
            para_type="action"
        )

        assert isinstance(card.title, str)
        assert isinstance(card.content, str)
        assert isinstance(card.para_type, str) or card.para_type is None
        assert isinstance(card.tags, list) or card.tags is None

    def test_card_with_source_inbox_item(self):
        """Test card can have source inbox item."""
        card = Card(
            user_id=1,
            title="Processed Card",
            content="Processed content",
            source_inbox_item_id=1
        )

        # Verify relationship
        assert card.source_inbox_item_id == 1


class TestTaskModels:
    """Test Task model."""

    def test_task_attributes(self):
        """Test task attributes."""
        task = Task(
            user_id=1,
            title="Test Task",
            description="Test task description",
            type="task",
            status="pending",
            priority=7,
            scheduled_date=date(2026, 1, 27)
        )

        # Verify attributes
        assert task.title == "Test Task"
        assert task.description == "Test task description"
        assert task.type == "task"
        assert task.status == "pending"
        assert task.priority == 7
        assert task.scheduled_date == date(2026, 1, 27)

    def test_task_field_types(self):
        """Test task field types."""
        task = Task(
            user_id=1,
            title="Task",
            description="Desc",
            type="habit",
            status="pending",  # Explicitly set status (defaults not applied until DB commit)
            priority=5  # Explicitly set priority
        )

        assert isinstance(task.title, str)
        assert isinstance(task.description, str) or task.description is None
        assert isinstance(task.type, str) or task.type is None
        assert isinstance(task.status, str) or task.status is None
        assert isinstance(task.priority, int) or task.priority is None

    def test_task_status_change(self):
        """Test task status can be changed."""
        task = Task(
            title="Complete Me",
            status="pending"
        )

        assert task.status == "pending"
        assert task.completed_at is None

        # Mark as completed
        task.status = "completed"
        task.completed_at = datetime.now()

        assert task.status == "completed"
        assert task.completed_at is not None


class TestModelConstraints:
    """Test model constraints and validation."""

    def test_user_requires_fields(self):
        """Test user model requires certain fields."""
        # Verify fields exist on the model class
        # Check if User model has these column attributes
        assert hasattr(User, 'username')
        assert hasattr(User, 'email')
        assert hasattr(User, 'hashed_password')
        assert hasattr(User, 'created_at')
        assert hasattr(User, 'updated_at')

    def test_card_requires_title(self):
        """Test card has title field."""
        card = Card(
            user_id=1,
            title="Test",
            content="Content",
            para_type="concept"
        )

        # Verify title is set
        assert card.title == "Test"

    def test_task_requires_title(self):
        """Test task has title field."""
        task = Task(
            user_id=1,
            title="Test Task",
            description="Optional desc",
            type="task"
        )

        # Verify title is set
        assert task.title == "Test Task"


class TestTableStructure:
    """Test table structure definitions."""

    def test_users_table_name(self):
        """Test users table has correct name."""
        assert User.__tablename__ == "users"

    def test_user_settings_table_name(self):
        """Test user_settings table has correct name."""
        assert UserSettings.__tablename__ == "user_settings"

    def test_inbox_items_table_name(self):
        """Test inbox_items table has correct name."""
        assert InboxItem.__tablename__ == "inbox_items"

    def test_cards_table_name(self):
        """Test cards table has correct name."""
        assert Card.__tablename__ == "cards"

    def test_tasks_table_name(self):
        """Test tasks table has correct name."""
        assert Task.__tablename__ == "tasks"


class TestRelationships:
    """Test relationship definitions."""

    def test_user_settings_back_populates(self):
        """Test UserSettings back_populates to User."""
        # This just verifies the relationship name is correct
        # Actual relationship testing requires database
        assert hasattr(User, 'settings')
        assert hasattr(UserSettings, 'user')

    def test_user_inbox_items_relationship(self):
        """Test User has inbox_items relationship."""
        assert hasattr(User, 'inbox_items')
        assert hasattr(InboxItem, 'user')

    def test_user_cards_relationship(self):
        """Test User has cards relationship."""
        assert hasattr(User, 'cards')
        assert hasattr(Card, 'user')

    def test_user_tasks_relationship(self):
        """Test User has tasks relationship."""
        assert hasattr(User, 'tasks')
        assert hasattr(Task, 'user')
