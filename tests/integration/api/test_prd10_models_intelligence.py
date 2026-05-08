"""PRD10 intelligence-domain model tests (Agent 3 ownership).

These tests cover Agent 3's slice of the PRD10 persistence contract frozen in
``agent-progress-report.md`` Milestone 3:

* ``AIConversation`` / ``AIMessage`` (PRD10 §5.11 / §5.12)
* ``SkillRun`` (PRD10 §17) plus the ``Skill`` PRD10 display fields
* ``SearchIndex`` extended to PRD10 §5.14 ``SearchDocument`` shape

The fixtures below are intentionally **scoped to this file** so they don't
collide with ``tests/conftest.py`` (which is owned by Agent 1 and currently
covers PRD4 + auth tables). Using uniquely named fixtures (``prd10_engine``,
``prd10_session``) means we don't trigger the parent-scope fixture chain at
all when these tests run.

The fixtures rely on ``agent_os.db.sqlite_compat`` to register a SQLite
DDL fallback for ``postgresql.UUID`` columns, which is what the PRD10 ORM
models use across the board.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# Side-effect import: registers SQLite DDL rendering for PG UUID columns.
import agent_os.db.sqlite_compat  # noqa: F401
from agent_os.ai.models import (
    AIConversation,
    AIConversationMode,
    AIMessage,
    AIMessageRole,
    AIMessageStatus,
)
from agent_os.auth.models import User
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.search_engine.models import SearchIndex
from agent_os.skills.runs import SkillRun, SkillRunStatus
from agent_os.stage3.models import Skill

PRD10_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def prd10_engine():
    """In-memory async SQLite engine with only the PRD10 intelligence tables.

    We avoid ``Base.metadata.create_all`` because PRD4 models referenced by
    ``Base`` would also try to create themselves and the conftest chain
    becomes brittle. Listing tables explicitly keeps the surface tight.
    """

    # NOTE: SQLAlchemy 2.x async + ``sqlite+aiosqlite:///:memory:`` only works
    # with ``StaticPool`` because every new connection from ``NullPool`` would
    # spawn a fresh in-memory DB and lose the schema we just created.
    engine = create_async_engine(
        PRD10_TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )

    async with engine.begin() as conn:
        def _create(connection):
            User.__table__.create(connection, checkfirst=True)
            AIConversation.__table__.create(connection, checkfirst=True)
            AIMessage.__table__.create(connection, checkfirst=True)
            Skill.__table__.create(connection, checkfirst=True)
            Job.__table__.create(connection, checkfirst=True)
            SkillRun.__table__.create(connection, checkfirst=True)
            SearchIndex.__table__.create(connection, checkfirst=True)

        await conn.run_sync(_create)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def prd10_session(prd10_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test async session bound to the PRD10 in-memory schema."""

    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(session: AsyncSession, *, email: str | None = None) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        email=email or f"u{suffix}@example.com",
        username=f"u_{suffix}",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_skill(session: AsyncSession, *, name: str = "Career Coach") -> Skill:
    skill = Skill(
        name=name,
        description="A PRD10 Skill fixture",
        category="decision",
        steps=[
            {"order": 1, "name": "analyze", "agent_action": "summarize"},
        ],
        version="1.0",
        icon="lightbulb",
        status="published",
        usage_count=0,
        is_installed_default=True,
        input_schema={"type": "object", "properties": {"goal": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"plan": {"type": "string"}}},
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return skill


# ---------------------------------------------------------------------------
# AIConversation / AIMessage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAIConversationModel:
    async def test_create_conversation_with_defaults(self, prd10_session):
        user = await _make_user(prd10_session)
        conv = AIConversation(user_id=user.id)
        prd10_session.add(conv)
        await prd10_session.commit()
        await prd10_session.refresh(conv)

        assert conv.id is not None
        assert conv.title == "新的对话"
        assert conv.mode == AIConversationMode.GENERAL.value
        assert conv.message_count == 0
        assert conv.context_scope == {}
        assert conv.created_at is not None
        assert conv.updated_at is not None

    async def test_to_prd10_dict_shape(self, prd10_session):
        user = await _make_user(prd10_session)
        conv = AIConversation(
            user_id=user.id,
            title="周报草稿",
            mode=AIConversationMode.PLANNING.value,
            last_message_preview="让我们规划周报...",
            message_count=4,
            context_scope={"folder_ids": ["f1", "f2"]},
        )
        prd10_session.add(conv)
        await prd10_session.commit()
        await prd10_session.refresh(conv)

        dto = conv.to_prd10_dict()
        assert dto["title"] == "周报草稿"
        assert dto["mode"] == "planning"
        assert dto["message_count"] == 4
        assert dto["last_message_preview"] == "让我们规划周报..."
        assert dto["user_id"] == str(user.id)
        assert "created_at" in dto and "updated_at" in dto


@pytest.mark.asyncio
class TestAIMessageModel:
    async def test_create_message_and_serialize(self, prd10_session):
        user = await _make_user(prd10_session)
        conv = AIConversation(user_id=user.id)
        prd10_session.add(conv)
        await prd10_session.commit()
        await prd10_session.refresh(conv)

        msg = AIMessage(
            conversation_id=conv.id,
            user_id=user.id,
            role=AIMessageRole.ASSISTANT.value,
            content="这是回答",
            status=AIMessageStatus.COMPLETED.value,
            citations=[
                {"object_type": "document", "object_id": "doc_1", "score": 0.9}
            ],
            tool_calls=[{"name": "search", "args": {}}],
            attachments=[],
            model="gpt-4o",
            input_tokens=120,
            output_tokens=240,
            latency_ms=850,
        )
        prd10_session.add(msg)
        await prd10_session.commit()
        await prd10_session.refresh(msg)

        dto = msg.to_prd10_dict()
        assert dto["role"] == "assistant"
        assert dto["status"] == "completed"
        assert dto["citations"][0]["object_type"] == "document"
        assert dto["model"] == "gpt-4o"
        assert dto["input_tokens"] == 120 and dto["output_tokens"] == 240
        assert dto["latency_ms"] == 850
        assert dto["conversation_id"] == str(conv.id)
        assert dto["user_id"] == str(user.id)


# ---------------------------------------------------------------------------
# Skill (PRD10 §5.13 display fields) + SkillRun
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSkillPrd10Fields:
    async def test_skill_to_prd10_dict_includes_display_fields(self, prd10_session):
        skill = await _make_skill(prd10_session)
        dto = skill.to_prd10_dict()
        assert dto["icon"] == "lightbulb"
        assert dto["status"] == "published"
        assert dto["is_installed"] is True
        assert dto["usage_count"] == 0
        assert dto["category"] == "decision"
        assert dto["input_schema"]["properties"]["goal"]["type"] == "string"
        assert dto["output_schema"]["properties"]["plan"]["type"] == "string"

    async def test_skill_to_prd10_dict_respects_explicit_is_installed(
        self, prd10_session
    ):
        skill = await _make_skill(prd10_session)
        dto = skill.to_prd10_dict(is_installed=False)
        assert dto["is_installed"] is False


@pytest.mark.asyncio
class TestSkillRunModel:
    async def test_create_skill_run_with_job_link(self, prd10_session):
        user = await _make_user(prd10_session)
        skill = await _make_skill(prd10_session)
        job = Job(
            user_id=user.id,
            job_type=JobType.SKILL_RUN.value,
            status=JobStatus.QUEUED.value,
            input={"skill_id": str(skill.id)},
        )
        prd10_session.add(job)
        await prd10_session.commit()
        await prd10_session.refresh(job)

        run = SkillRun(
            user_id=user.id,
            skill_id=skill.id,
            job_id=job.id,
            input={"goal": "Plan a quarter"},
        )
        prd10_session.add(run)
        await prd10_session.commit()
        await prd10_session.refresh(run)

        assert run.status == SkillRunStatus.QUEUED.value
        dto = run.to_prd10_dict()
        assert dto["skill_id"] == str(skill.id)
        assert dto["user_id"] == str(user.id)
        assert dto["job_id"] == str(job.id)
        assert dto["status"] == "queued"
        assert dto["input"] == {"goal": "Plan a quarter"}
        assert dto["output"] is None
        assert dto["error"] is None


# ---------------------------------------------------------------------------
# SearchIndex (PRD10 §5.14 SearchDocument)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchIndexPrd10:
    async def test_legacy_ingestion_write_still_works(self, prd10_session):
        """Existing ingestion path does not pass user_id; it must keep working."""

        idx = SearchIndex(
            item_type="card",
            item_id=uuid.uuid4(),
            title="Legacy ingestion row",
            content="body",
            tags=["a", "b"],
            search_metadata={"workspace_id": "w_1"},
        )
        prd10_session.add(idx)
        await prd10_session.commit()
        await prd10_session.refresh(idx)

        assert idx.user_id is None
        assert idx.summary is None
        assert idx.embedding_id is None
        assert idx.object_type == "card"
        assert idx.object_id == idx.item_id

    async def test_prd10_object_types_accepted(self, prd10_session):
        for object_type in (
            "document",
            "folder",
            "conversation",
            "message",
            "skill",
            "insight",
        ):
            idx = SearchIndex(
                item_type=object_type,
                item_id=uuid.uuid4(),
                title=f"{object_type}-row",
                summary="Short summary",
                tags=[object_type],
                user_id=None,
                embedding_id=f"emb_{object_type}",
            )
            prd10_session.add(idx)
        await prd10_session.commit()

    async def test_to_prd10_dict_shape(self, prd10_session):
        user = await _make_user(prd10_session)
        idx = SearchIndex(
            item_type="document",
            item_id=uuid.uuid4(),
            user_id=user.id,
            title="UI 设计规范",
            summary="Mydow V1 UI 设计文档",
            content="正文",
            tags=["UI", "Mydow"],
            embedding_id="emb_001",
        )
        prd10_session.add(idx)
        await prd10_session.commit()
        await prd10_session.refresh(idx)

        dto = idx.to_prd10_dict()
        assert dto["object_type"] == "document"
        assert dto["object_id"] == str(idx.item_id)
        assert dto["user_id"] == str(user.id)
        assert dto["title"] == "UI 设计规范"
        assert dto["summary"] == "Mydow V1 UI 设计文档"
        assert dto["tags"] == ["UI", "Mydow"]
        assert dto["embedding_id"] == "emb_001"

    async def test_invalid_object_type_rejected(self, prd10_session):
        from sqlalchemy.exc import IntegrityError

        idx = SearchIndex(
            item_type="invalid_type",
            item_id=uuid.uuid4(),
            title="bad",
        )
        prd10_session.add(idx)
        with pytest.raises(IntegrityError):
            await prd10_session.commit()
