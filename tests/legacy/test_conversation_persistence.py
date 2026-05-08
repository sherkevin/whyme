"""Test conversation persistence functionality."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_os.conversations import ConversationRepository
from agent_os.db.base import Base


@pytest.fixture
async def test_db():
    """Create a test database."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield async_session

    # Cleanup
    await engine.dispose()


class TestConversationPersistence:
    """Test conversation persistence functionality."""

    @pytest.mark.asyncio
    async def test_add_user_message(self, test_db):
        """Test adding a user message to database."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1
            session_id = "test_session_123"

            await repo.add_message(
                session=db,
                user_id=user_id,
                session_id=session_id,
                role="user",
                content="Hello, Agent!",
            )
            await db.commit()

            # Verify message was saved
            history = await repo.get_conversation_history(
                session=db,
                user_id=user_id,
                session_id=session_id,
                limit=10,
            )

            assert len(history) == 1
            assert history[0].role == "user"
            assert history[0].content == "Hello, Agent!"
            assert history[0].session_id == session_id

    @pytest.mark.asyncio
    async def test_add_assistant_message(self, test_db):
        """Test adding an assistant message to database."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1
            session_id = "test_session_456"

            await repo.add_message(
                session=db,
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content="Hello! How can I help you?",
                model="gpt-4",
            )
            await db.commit()

            # Verify message was saved
            history = await repo.get_conversation_history(
                session=db,
                user_id=user_id,
                session_id=session_id,
                limit=10,
            )

            assert len(history) == 1
            assert history[0].role == "assistant"
            assert history[0].model == "gpt-4"

    @pytest.mark.asyncio
    async def test_add_tool_message(self, test_db):
        """Test adding a tool execution message to database."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1
            session_id = "test_session_789"

            # Add tool message
            tool_calls = [
                {
                    "id": "call_123",
                    "name": "read_file",
                    "args": {"path": "test.py"},
                }
            ]

            await repo.add_message(
                session=db,
                user_id=user_id,
                session_id=session_id,
                role="tool",
                content="File content: print('hello')",
                tool_calls=tool_calls,
            )
            await db.commit()

            # Verify message was saved
            history = await repo.get_conversation_history(
                session=db,
                user_id=user_id,
                session_id=session_id,
                limit=10,
            )

            assert len(history) == 1
            assert history[0].role == "tool"
            assert history[0].tool_calls == tool_calls

    @pytest.mark.asyncio
    async def test_get_conversation_history_pagination(self, test_db):
        """Test retrieving conversation history with pagination."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1
            session_id = "test_session_pagination"

            # Add multiple messages
            messages = [
                ("user", "Hello"),
                ("assistant", "Hi there!"),
                ("user", "How are you?"),
                ("assistant", "I'm doing well!"),
                ("user", "Great!"),
            ]

            for role, content in messages:
                await repo.add_message(
                    session=db,
                    user_id=user_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                )
            await db.commit()

            # Get first 3 messages
            history = await repo.get_conversation_history(
                session=db,
                user_id=user_id,
                session_id=session_id,
                limit=3,
            )

            assert len(history) == 3
            # Verify we got unique messages
            ids = [msg.id for msg in history]
            assert len(ids) == len(set(ids))  # All unique

    @pytest.mark.asyncio
    async def test_token_count(self, test_db):
        """Test getting token count for a session."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1
            session_id = "test_session_tokens"

            # Add messages with token counts
            await repo.add_message(
                session=db,
                user_id=user_id,
                session_id=session_id,
                role="user",
                content="Hello",
                tokens=10,
            )
            await repo.add_message(
                session=db,
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content="Hi there!",
                tokens=15,
            )
            await db.commit()

            # Get token count
            count = await repo.get_token_count(
                session=db,
                user_id=user_id,
                session_id=session_id,
            )

            assert count == 25

    @pytest.mark.asyncio
    async def test_recent_sessions(self, test_db):
        """Test getting recent session IDs."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1

            # Add messages to multiple sessions
            sessions = ["session_1", "session_2", "session_3"]
            for session_id in sessions:
                await repo.add_message(
                    session=db,
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content=f"Message in {session_id}",
                )
            await db.commit()

            # Get recent sessions
            recent = await repo.get_recent_sessions(db, user_id, limit=10)

            assert len(recent) == 3
            assert all(sid in recent for sid in sessions)

    @pytest.mark.asyncio
    async def test_delete_conversation(self, test_db):
        """Test deleting a conversation message."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1
            session_id = "test_session_delete"

            # Add a message
            await repo.add_message(
                session=db,
                user_id=user_id,
                session_id=session_id,
                role="user",
                content="Delete me",
            )
            await db.commit()

            # Get the message
            history = await repo.get_conversation_history(
                session=db,
                user_id=user_id,
                session_id=session_id,
                limit=10,
            )
            assert len(history) == 1

            # Delete the message
            deleted = await repo.delete_conversation(db, history[0].id)
            await db.commit()

            assert deleted is True

            # Verify deletion
            history_after = await repo.get_conversation_history(
                session=db,
                user_id=user_id,
                session_id=session_id,
                limit=10,
            )
            assert len(history_after) == 0

    @pytest.mark.asyncio
    async def test_create_conversation_summary(self, test_db):
        """Test creating a conversation summary."""
        async with test_db() as db:
            repo = ConversationRepository()

            user_id = 1
            session_id = "test_session_summary"

            # Add some messages
            msg_ids = []
            for i in range(5):
                conv = await repo.add_message(
                    session=db,
                    user_id=user_id,
                    session_id=session_id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Message {i}",
                )
                msg_ids.append(conv.id)
            await db.commit()

            # Create summary
            summary = await repo.create_summary(
                session=db,
                user_id=user_id,
                session_id=session_id,
                summary_text="Summary of conversation",
                message_ids=msg_ids,
            )
            await db.commit()

            assert summary is not None
            assert summary.summary_text == "Summary of conversation"
            assert summary.message_count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
