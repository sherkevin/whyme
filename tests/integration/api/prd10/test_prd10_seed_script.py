"""Run scripts/seed_prd10.py against a temp SQLite DB.

PRD10 §25.3 demands a seed script that prepares 1 user with the documented
counts. This test invokes the real script entry-point, points it at a
temp file SQLite DB, and asserts the post-conditions match §25.3.
"""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


@contextmanager
def _env(name: str, value: str | None) -> Iterator[None]:
    previous = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _reset_db_module() -> None:
    """Force ``agent_os.db.base`` to recreate its engine when DATABASE_URL changes."""

    import agent_os.db.base as db_base

    db_base._engine = None  # noqa: SLF001
    db_base._AsyncSessionLocal = None  # noqa: SLF001
    db_base.DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://agentos:agentos@localhost/agentos_db",
    )


@pytest.mark.asyncio
async def test_seed_script_creates_prd10_25_3_counts(tmp_path):
    db_path = tmp_path / f"seed_{uuid.uuid4().hex}.sqlite"
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))

    with _env("DATABASE_URL", db_url):
        _reset_db_module()
        # The script imports several runtime modules; reload to pick up the
        # rebuilt engine bound to the temp database.
        import agent_os.db.base  # noqa: F401  (ensure cache invalidated)

        seed_module = importlib.import_module("seed_prd10")
        seed_module = importlib.reload(seed_module)

        exit_code = await seed_module.main(
            ["--email", "seed-test@whyme.local", "--password", "seed-test-pwd"]
        )
        assert exit_code == 0

        # Re-run with --reset to prove the script is idempotent.
        exit_code = await seed_module.main(
            [
                "--email",
                "seed-test@whyme.local",
                "--password",
                "seed-test-pwd",
                "--reset",
            ]
        )
        assert exit_code == 0

        # Now inspect the resulting DB directly.
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from agent_os.ai.models import AIConversation, AIMessage
        from agent_os.auth.models import User
        from agent_os.db.base import get_engine
        from agent_os.kb.models import Document, Folder
        from agent_os.knowledge.models import Card
        from agent_os.notifications.models import Notification
        from agent_os.search_engine.models import SearchIndex
        from agent_os.stage3.models import Skill
        from agent_os.tasks.models import PRD10Task

        engine = get_engine()
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with sessionmaker() as session:
            user = (
                await session.execute(
                    select(User).where(User.email == "seed-test@whyme.local")
                )
            ).scalar_one()

            async def _count(model, *where):
                rows = (await session.execute(select(model).where(*where))).scalars().all()
                return len(rows)

            assert await _count(Folder, Folder.user_id == user.id) == 6
            assert await _count(Document, Document.user_id == user.id) == 20
            assert await _count(Card, Card.user_id == user.id) == 30
            assert await _count(PRD10Task, PRD10Task.user_id == user.id) == 5
            assert await _count(Notification, Notification.user_id == user.id) == 5
            assert (
                await _count(AIConversation, AIConversation.user_id == user.id) == 3
            )
            ai_msg_count = await _count(AIMessage, AIMessage.user_id == user.id)
            assert ai_msg_count >= 10
            assert await _count(Skill) >= 5
            # PRD10 §25.3 requires "at least 10 indexed objects"; the demo
            # seed populates 50 (half kb_documents + half cards) so the
            # global search has real depth — accept any value ≥ 10.
            assert await _count(SearchIndex, SearchIndex.user_id == user.id) >= 10
            indexed = (
                await session.execute(
                    select(SearchIndex).where(SearchIndex.user_id == user.id)
                )
            ).scalars().all()
            assert all(row.embedding_id for row in indexed)
            assert all(isinstance(row.embedding, list) and row.embedding for row in indexed)

        await engine.dispose()
        _reset_db_module()
