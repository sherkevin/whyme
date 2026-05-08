"""Database configuration and session management."""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

import agent_os.db.sqlite_compat  # noqa: F401
from agent_os.core.config import load_config

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


class _LazyAsyncSessionMaker:
    """Callable proxy so direct imports stay valid before engine init."""

    def __call__(self, *args, **kwargs):
        session_factory = get_sessionmaker()
        return session_factory(*args, **kwargs)


async_session_maker = _LazyAsyncSessionMaker()


def get_engine():
    """Get or create database engine."""
    global _engine, _AsyncSessionLocal

    if _engine is None:
        # Echo SQL is off by default in production / smoke runs; toggle by
        # setting AGENTOS_DB_ECHO=on (or DB_ECHO=on) when debugging schema.
        echo_flag = (
            os.getenv("AGENTOS_DB_ECHO")
            or os.getenv("DB_ECHO")
            or "off"
        ).strip().lower() in ("1", "on", "true", "yes")
        engine_kwargs = {
            "echo": echo_flag,
            "pool_pre_ping": True,
        }
        if not DATABASE_URL.startswith("sqlite"):
            engine_kwargs.update(
                {
                    "pool_size": 20,  # Support ~1000 users
                    "max_overflow": 40,
                }
            )

        # Create async engine
        _engine = create_async_engine(DATABASE_URL, **engine_kwargs)

        # Create async session factory
        _AsyncSessionLocal = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _engine


def get_sessionmaker():
    """Get or create the async SQLAlchemy session factory."""
    get_engine()
    return _AsyncSessionLocal


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
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with get_engine().begin() as conn:
        # Import all models to ensure they're registered with Base
        # Note: Only import models that actually exist
        from agent_os.auth.models import User  # noqa: F401
        from agent_os.conversations.models import Conversation, ConversationSummary  # noqa: F401
        from agent_os.inbox.prd10_models import Prd10InboxItem  # noqa: F401
        from agent_os.insights.models import Prd10Insight  # noqa: F401
        from agent_os.items.models import GraphEdge, Item  # noqa: F401
        from agent_os.jobs.models import Job  # noqa: F401
        from agent_os.kb.models import Chunk, Document, Folder  # noqa: F401
        from agent_os.knowledge.models import Card  # noqa: F401
        from agent_os.knowledge.models import InboxItem as KnowledgeInboxItem
        from agent_os.notifications.models import Notification  # noqa: F401

        # PRD10 product-data models (Agent 2 ownership).
        from agent_os.sources.models import Source  # noqa: F401
        from agent_os.tasks.models import PRD10Task, Task  # noqa: F401

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        await ensure_prd10_performance_indexes(conn)


async def ensure_prd10_performance_indexes(conn) -> None:
    """Ensure PRD10 §21.3 performance indexes exist on fresh and existing DBs.

    ``Base.metadata.create_all`` does not retrofit indexes or columns onto an
    already-created SQLite/Postgres database. This helper keeps the runtime
    schema aligned with PRD10 without requiring a destructive rebuild.
    """

    dialect = conn.dialect.name
    if dialect == "sqlite":
        await _ensure_sqlite_column(
            conn,
            table_name="kb_chunks",
            column_name="source_id",
            column_sql="source_id CHAR(32)",
        )
        await _execute_many(
            conn,
            [
                "UPDATE kb_chunks SET source_id = ("
                "SELECT kb_documents.source_id FROM kb_documents "
                "WHERE kb_documents.id = kb_chunks.document_id"
                ") WHERE source_id IS NULL",
                "CREATE INDEX IF NOT EXISTS idx_prd10_inbox_user_created "
                "ON prd10_inbox_items (user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_inbox_user_status "
                "ON prd10_inbox_items (user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_card_user_created "
                "ON cards (user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_card_user_folder "
                "ON cards (user_id, folder_id)",
                "CREATE INDEX IF NOT EXISTS idx_card_user_tags "
                "ON cards (user_id, tags)",
                "CREATE INDEX IF NOT EXISTS idx_kb_folders_user_parent "
                "ON kb_folders (user_id, parent_id)",
                "CREATE INDEX IF NOT EXISTS idx_kb_folders_user_name "
                "ON kb_folders (user_id, name)",
                "CREATE INDEX IF NOT EXISTS idx_kb_documents_user_folder_updated "
                "ON kb_documents (user_id, folder_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_kb_documents_user_updated "
                "ON kb_documents (user_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_kb_documents_user_status "
                "ON kb_documents (user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_index "
                "ON kb_chunks (document_id, chunk_index)",
                "CREATE INDEX IF NOT EXISTS idx_kb_chunks_user_source "
                "ON kb_chunks (user_id, source_id)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_tasks_user_status_due "
                "ON prd10_tasks (user_id, status, due_at)",
                "CREATE INDEX IF NOT EXISTS idx_ai_conv_user_updated "
                "ON ai_conversations (user_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_ai_msg_conv_created "
                "ON ai_messages (conversation_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_notifications_user_read_created "
                "ON prd10_notifications (user_id, is_read, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_jobs_user_status_created "
                "ON prd10_jobs (user_id, status, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_search_user_object_updated "
                "ON search_indices (user_id, item_type, updated_at)",
            ],
        )
        return

    if dialect == "postgresql":
        await _execute_many(
            conn,
            [
                "ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS source_id "
                "UUID REFERENCES prd10_sources(id) ON DELETE SET NULL",
                "UPDATE kb_chunks AS c SET source_id = d.source_id "
                "FROM kb_documents AS d "
                "WHERE c.document_id = d.id AND c.source_id IS NULL",
                "CREATE INDEX IF NOT EXISTS idx_prd10_inbox_user_created "
                "ON prd10_inbox_items (user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_inbox_user_status "
                "ON prd10_inbox_items (user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_card_user_created "
                "ON cards (user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_card_user_folder "
                "ON cards (user_id, folder_id)",
                "CREATE INDEX IF NOT EXISTS idx_card_user_tags "
                "ON cards (user_id, ((tags)::text))",
                "CREATE INDEX IF NOT EXISTS idx_kb_folders_user_parent "
                "ON kb_folders (user_id, parent_id)",
                "CREATE INDEX IF NOT EXISTS idx_kb_folders_user_name "
                "ON kb_folders (user_id, name)",
                "CREATE INDEX IF NOT EXISTS idx_kb_documents_user_folder_updated "
                "ON kb_documents (user_id, folder_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_kb_documents_user_updated "
                "ON kb_documents (user_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_kb_documents_user_status "
                "ON kb_documents (user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_index "
                "ON kb_chunks (document_id, chunk_index)",
                "CREATE INDEX IF NOT EXISTS idx_kb_chunks_user_source "
                "ON kb_chunks (user_id, source_id)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_tasks_user_status_due "
                "ON prd10_tasks (user_id, status, due_at)",
                "CREATE INDEX IF NOT EXISTS idx_ai_conv_user_updated "
                "ON ai_conversations (user_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_ai_msg_conv_created "
                "ON ai_messages (conversation_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_notifications_user_read_created "
                "ON prd10_notifications (user_id, is_read, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_prd10_jobs_user_status_created "
                "ON prd10_jobs (user_id, status, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_search_user_object_updated "
                "ON search_indices (user_id, item_type, updated_at)",
            ],
        )


async def _ensure_sqlite_column(
    conn,
    *,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    result = await conn.execute(text(f'PRAGMA table_info("{table_name}")'))
    existing = {row[1] for row in result.fetchall()}
    if column_name not in existing:
        await conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN {column_sql}'))


async def _execute_many(conn, statements: list[str]) -> None:
    for statement in statements:
        await conn.execute(text(statement))


# Exports
AsyncSessionLocal = get_sessionmaker
engine = get_engine
