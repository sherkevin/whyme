"""Database configuration and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from agent_os.core.config import load_config
import os

# Load config
config = load_config("config.yaml")

# Database URL from environment or config
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://agentos:agentos@localhost/agentos_db"
)

# Global engine and session factory (initialized lazily)
_engine = None
_AsyncSessionLocal = None


def get_engine():
    """Get or create database engine."""
    global _engine, _AsyncSessionLocal

    if _engine is None:
        # Create async engine
        _engine = create_async_engine(
            DATABASE_URL,
            echo=True,  # Log SQL queries (disable in production)
            pool_size=20,  # Support ~1000 users
            max_overflow=40,
            pool_pre_ping=True,
        )

        # Create async session factory
        _AsyncSessionLocal = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _engine


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency for FastAPI to get database session.

    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with _AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with get_engine().begin() as conn:
        # Import all models to ensure they're registered
        from agent_os.knowledge.models import InboxItem, Card
        from agent_os.tasks.models import Task
        from agent_os.auth.models import User, UserSettings
        from agent_os.conversations.models import Conversation, ConversationSummary

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


# Exports
AsyncSessionLocal = _AsyncSessionLocal
engine = get_engine
