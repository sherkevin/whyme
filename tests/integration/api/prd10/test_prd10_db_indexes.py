from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from agent_os.db.base import Base, ensure_prd10_performance_indexes

# Side-effect imports so Base.metadata contains every PRD10 table/FK target.
from agent_os.ai.models import AIConversation, AIMessage  # noqa: F401
from agent_os.auth.models import User  # noqa: F401
from agent_os.inbox.prd10_models import Prd10InboxItem  # noqa: F401
from agent_os.items.models import Workspace  # noqa: F401
from agent_os.jobs.models import Job  # noqa: F401
from agent_os.kb.models import Chunk, Document, Folder  # noqa: F401
from agent_os.knowledge.models import Card, InboxItem  # noqa: F401
from agent_os.notifications.models import Notification  # noqa: F401
from agent_os.search_engine.models import SearchIndex  # noqa: F401
from agent_os.sources.models import Source  # noqa: F401
from agent_os.tasks.models import PRD10Task  # noqa: F401


REQUIRED_INDEXES: dict[str, dict[str, list[str]]] = {
    "prd10_inbox_items": {
        "idx_prd10_inbox_user_created": ["user_id", "created_at"],
        "idx_prd10_inbox_user_status": ["user_id", "status"],
    },
    "cards": {
        "idx_card_user_created": ["user_id", "created_at"],
        "idx_card_user_folder": ["user_id", "folder_id"],
        "idx_card_user_tags": ["user_id", "tags"],
    },
    "kb_folders": {
        "idx_kb_folders_user_parent": ["user_id", "parent_id"],
        "idx_kb_folders_user_name": ["user_id", "name"],
    },
    "kb_documents": {
        "idx_kb_documents_user_folder_updated": [
            "user_id",
            "folder_id",
            "updated_at",
        ],
        "idx_kb_documents_user_updated": ["user_id", "updated_at"],
        "idx_kb_documents_user_status": ["user_id", "status"],
    },
    "kb_chunks": {
        "idx_kb_chunks_doc_index": ["document_id", "chunk_index"],
        "idx_kb_chunks_user_source": ["user_id", "source_id"],
    },
    "prd10_tasks": {
        "idx_prd10_tasks_user_status_due": ["user_id", "status", "due_at"],
    },
    "ai_conversations": {
        "idx_ai_conv_user_updated": ["user_id", "updated_at"],
    },
    "ai_messages": {
        "idx_ai_msg_conv_created": ["conversation_id", "created_at"],
    },
    "prd10_notifications": {
        "idx_prd10_notifications_user_read_created": [
            "user_id",
            "is_read",
            "created_at",
        ],
    },
    "prd10_jobs": {
        "idx_prd10_jobs_user_status_created": ["user_id", "status", "created_at"],
    },
    "search_indices": {
        "idx_search_user_object_updated": ["user_id", "item_type", "updated_at"],
    },
}


@pytest.mark.asyncio
async def test_prd10_21_3_required_indexes_exist_after_runtime_ensure():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await ensure_prd10_performance_indexes(conn)

            def collect_indexes(sync_conn):
                inspector = inspect(sync_conn)
                return {
                    table: {
                        item["name"]: item["column_names"]
                        for item in inspector.get_indexes(table)
                    }
                    for table in REQUIRED_INDEXES
                }

            indexes = await conn.run_sync(collect_indexes)

        missing: list[str] = []
        wrong_columns: list[str] = []
        for table, required in REQUIRED_INDEXES.items():
            for name, expected_columns in required.items():
                actual_columns = indexes[table].get(name)
                if actual_columns is None:
                    missing.append(f"{table}.{name}")
                elif actual_columns != expected_columns:
                    wrong_columns.append(
                        f"{table}.{name}: expected {expected_columns}, got {actual_columns}"
                    )

        assert not missing
        assert not wrong_columns
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_prd10_21_3_sqlite_query_plans_use_required_indexes():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await ensure_prd10_performance_indexes(conn)

            def explain(sync_conn, sql: str) -> str:
                rows = sync_conn.exec_driver_sql(f"EXPLAIN QUERY PLAN {sql}").fetchall()
                return "\n".join(str(row[3]) for row in rows)

            plans = {
                "chunks_by_source": await conn.run_sync(
                    explain,
                    "SELECT id FROM kb_chunks "
                    "WHERE user_id = 'u' AND source_id = 's'",
                ),
                "notifications_unread": await conn.run_sync(
                    explain,
                    "SELECT id FROM prd10_notifications "
                    "WHERE user_id = 'u' AND is_read = 0 "
                    "ORDER BY created_at DESC",
                ),
                "tasks_due": await conn.run_sync(
                    explain,
                    "SELECT id FROM prd10_tasks "
                    "WHERE user_id = 'u' AND status = 'todo' "
                    "ORDER BY due_at ASC",
                ),
            }

        assert "idx_kb_chunks_user_source" in plans["chunks_by_source"]
        assert (
            "idx_prd10_notifications_user_read_created"
            in plans["notifications_unread"]
        )
        assert "idx_prd10_tasks_user_status_due" in plans["tasks_due"]
    finally:
        await engine.dispose()
