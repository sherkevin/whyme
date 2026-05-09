"""PRD10 Skills router tests (Agent 3)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import agent_os.db.sqlite_compat  # noqa: F401
from agent_os.ai import llm_provider
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import get_db
from agent_os.jobs.models import Job
from agent_os.skills.router import router as skills_router
from agent_os.skills.runs import SkillRun
from agent_os.stage3.models import Skill


class FakeSkillProvider:
    async def complete(self, messages, tools=None, **kwargs):
        return {
            "content": "FAKE_SKILL_LLM_OUTPUT\n\n" + messages[-1]["content"][:200],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }


@pytest_asyncio.fixture
async def prd10_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        def _create(connection):
            User.__table__.create(connection, checkfirst=True)
            Skill.__table__.create(connection, checkfirst=True)
            Job.__table__.create(connection, checkfirst=True)
            SkillRun.__table__.create(connection, checkfirst=True)

        await conn.run_sync(_create)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def prd10_session(prd10_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def fixture_user(prd10_session) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        email=f"u{suffix}@example.com",
        username=f"u_{suffix}",
        password_hash="x",
        is_active=True,
    )
    prd10_session.add(user)
    await prd10_session.commit()
    await prd10_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def app(prd10_engine, fixture_user):
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )

    fastapi_app = FastAPI()
    fastapi_app.include_router(skills_router)

    async def _override_db():
        async with factory() as session:
            yield session

    async def _override_user():
        return fixture_user

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_current_user] = _override_user

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _make_skill(
    session: AsyncSession,
    *,
    name: str = "会议纪要生成",
    category: str = "productivity",
    description: str = "将录音或文本整理为会议纪要、行动项和负责人。",
    skill_status: str = "published",
    icon: str = "sparkles",
    usage_count: int = 0,
    is_active: bool = True,
) -> Skill:
    skill = Skill(
        name=name,
        description=description,
        category=category,
        steps=[{"order": 1, "name": "summarize"}],
        version="1.0",
        icon=icon,
        status=skill_status,
        usage_count=usage_count,
        is_installed_default=True,
        is_active=is_active,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return skill


# ---------------------------------------------------------------------------
# List + detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSkillsList:
    async def test_fresh_install_includes_default_skill(self, client):
        resp = await client.get("/api/v1/skills")
        body = resp.json()
        assert resp.status_code == 200
        assert body["data"]["pagination"]["total"] == 1
        assert body["data"]["items"][0]["name"] == "Mydow 快速总结"
        assert body["data"]["items"][0]["status"] == "published"

    async def test_list_returns_prd10_shape(self, client, prd10_session):
        await _make_skill(prd10_session, name="A", usage_count=5)
        await _make_skill(prd10_session, name="B", usage_count=10)
        resp = await client.get("/api/v1/skills")
        items = resp.json()["data"]["items"]
        assert len(items) == 2
        # Sorted by usage_count DESC
        assert items[0]["name"] == "B"
        for skill in items:
            assert "icon" in skill and "is_installed" in skill
            assert "usage_count" in skill
            assert skill["category"] == "productivity"

    async def test_list_keyword_filter(self, client, prd10_session):
        await _make_skill(prd10_session, name="周报生成器")
        await _make_skill(prd10_session, name="日报生成器")
        resp = await client.get(
            "/api/v1/skills", params={"keyword": "周报"}
        )
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "周报生成器"

    async def test_list_status_filter(self, client, prd10_session):
        await _make_skill(prd10_session, name="A", skill_status="published")
        await _make_skill(prd10_session, name="B", skill_status="draft")
        resp = await client.get(
            "/api/v1/skills", params={"status": "draft"}
        )
        items = resp.json()["data"]["items"]
        assert len(items) == 1 and items[0]["status"] == "draft"

    async def test_list_invalid_status_rejected(self, client):
        resp = await client.get(
            "/api/v1/skills", params={"status": "weird"}
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    async def test_inactive_skill_hidden(self, client, prd10_session):
        await _make_skill(prd10_session, name="visible", is_active=True)
        await _make_skill(prd10_session, name="hidden", is_active=False)
        resp = await client.get("/api/v1/skills")
        items = resp.json()["data"]["items"]
        names = [s["name"] for s in items]
        assert names == ["visible"]


@pytest.mark.asyncio
class TestSkillDetail:
    async def test_detail_404(self, client):
        resp = await client.get(f"/api/v1/skills/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_detail_invalid_uuid(self, client):
        resp = await client.get("/api/v1/skills/not-a-uuid")
        assert resp.status_code == 400

    async def test_detail_returns_full_prd10_shape(self, client, prd10_session):
        skill = await _make_skill(prd10_session, name="详情测试")
        resp = await client.get(f"/api/v1/skills/{skill.id}")
        body = resp.json()
        assert resp.status_code == 200
        data = body["data"]
        assert data["id"] == str(skill.id)
        assert data["name"] == "详情测试"
        assert data["icon"] == "sparkles"
        assert data["status"] == "published"
        assert data["is_installed"] is True
        assert "input_schema" in data and "output_schema" in data


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSkillRun:
    async def test_run_404_for_unknown_skill(self, client):
        resp = await client.post(
            f"/api/v1/skills/{uuid.uuid4()}/run",
            json={"input": {}},
        )
        assert resp.status_code == 404

    async def test_run_creates_job_and_skill_run(
        self, client, prd10_session
    ):
        skill = await _make_skill(prd10_session, name="run-me")
        resp = await client.post(
            f"/api/v1/skills/{skill.id}/run",
            json={
                "input": {"source_id": "src_001", "instruction": "请生成"},
                "save_output": True,
            },
        )
        assert resp.status_code == 202
        body = resp.json()["data"]
        assert body["status"] == "queued"
        assert body["job_id"]
        assert body["skill_run_id"]

        # usage_count should have been incremented
        await prd10_session.refresh(skill)
        assert skill.usage_count == 1

    async def test_run_with_string_save_output(self, client, prd10_session):
        skill = await _make_skill(prd10_session, name="str-save")
        resp = await client.post(
            f"/api/v1/skills/{skill.id}/run",
            json={"input": {}, "save_output": "task"},
        )
        assert resp.status_code == 202
        assert resp.json()["data"]["status"] == "queued"


@pytest.mark.asyncio
class TestSkillRunWorker:
    """Verify the §16 worker actually executes skill_run jobs end-to-end."""

    async def test_worker_runs_skill_and_persists_output(self, prd10_engine, fixture_user):
        # Need full DB schema (Document, Chunk, Notification, Workspace) for
        # the materializer; create them on top of the existing fixture engine.
        from agent_os.kb.models import Chunk, Document, Folder
        from agent_os.notifications.models import Notification

        from sqlalchemy.ext.asyncio import async_sessionmaker

        async with prd10_engine.begin() as conn:
            def _create(connection):
                Folder.__table__.create(connection, checkfirst=True)
                Document.__table__.create(connection, checkfirst=True)
                Chunk.__table__.create(connection, checkfirst=True)
                Notification.__table__.create(connection, checkfirst=True)
            await conn.run_sync(_create)

        factory = async_sessionmaker(
            prd10_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            skill = await _make_skill(session, name="worker-skill")
            from agent_os.jobs.models import Job, JobStatus, JobType
            job = Job(
                user_id=fixture_user.id,
                job_type=JobType.SKILL_RUN.value,
                status=JobStatus.QUEUED.value,
                input={
                    "skill_id": str(skill.id),
                    "skill_name": skill.name,
                    "input": {"text": "测试输入：把这段做成结构化笔记"},
                    "save_output": True,
                },
            )
            session.add(job)
            await session.flush()
            run = SkillRun(
                user_id=fixture_user.id,
                skill_id=skill.id,
                job_id=job.id,
                status="queued",
                input={"text": "测试输入：把这段做成结构化笔记"},
                save_output="kb",
            )
            session.add(run)
            await session.commit()
            from agent_os.jobs.service import process_job_once
            llm_provider.set_test_provider(FakeSkillProvider())
            try:
                updated = await process_job_once(session, job.id)
                await session.commit()
            finally:
                llm_provider.set_test_provider(None)
                llm_provider.reset_provider_for_test()
            assert updated is not None
            assert updated.status == JobStatus.COMPLETED.value
            await session.refresh(run)
            assert run.status == "completed"
            assert run.output is not None
            from sqlalchemy import select
            docs = (
                await session.execute(select(Document).where(Document.user_id == fixture_user.id))
            ).scalars().all()
            assert len(docs) == 1
            assert "worker-skill" in docs[0].title

    async def test_worker_transform_updates_existing_document(
        self, prd10_engine, fixture_user
    ):
        from agent_os.kb.models import Chunk, Document
        from agent_os.notifications.models import Notification
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker

        async with prd10_engine.begin() as conn:
            def _create(connection):
                Document.__table__.create(connection, checkfirst=True)
                Chunk.__table__.create(connection, checkfirst=True)
                Notification.__table__.create(connection, checkfirst=True)

            await conn.run_sync(_create)

        factory = async_sessionmaker(
            prd10_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            skill = await _make_skill(session, name="transform-skill")
            from agent_os.jobs.models import Job, JobStatus, JobType

            doc = Document(
                user_id=fixture_user.id,
                title="Original title",
                content="ONLY_ORIGINAL_MARKER",
                document_type="note",
                status="ready",
                tags=[],
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            job = Job(
                user_id=fixture_user.id,
                job_type=JobType.SKILL_RUN.value,
                status=JobStatus.QUEUED.value,
                input={
                    "skill_id": str(skill.id),
                    "skill_name": skill.name,
                    "input": {
                        "instruction": "压缩为一句",
                        "text": "压缩为一句",
                        "document_id": str(doc.id),
                        "output_mode": "transform",
                    },
                    "save_output": True,
                },
            )
            session.add(job)
            await session.flush()
            run = SkillRun(
                user_id=fixture_user.id,
                skill_id=skill.id,
                job_id=job.id,
                status="queued",
                input=job.input["input"],
                save_output="kb",
            )
            session.add(run)
            await session.commit()

            from agent_os.jobs.service import process_job_once

            llm_provider.set_test_provider(FakeSkillProvider())
            try:
                updated = await process_job_once(session, job.id)
                await session.commit()
            finally:
                llm_provider.set_test_provider(None)
                llm_provider.reset_provider_for_test()
            assert updated is not None
            assert updated.status == JobStatus.COMPLETED.value
            await session.refresh(run)
            assert run.output.get("transformed") is True
            await session.refresh(doc)
            # LLM 输出可能引用原文片段，不要求去除 marker；但正文应已被改写而非原样保留
            assert (doc.content or "").strip() != "ONLY_ORIGINAL_MARKER"
            assert len((doc.content or "").strip()) > 10

            docs = (
                await session.execute(
                    select(Document).where(Document.user_id == fixture_user.id)
                )
            ).scalars().all()
            assert len(docs) == 1

    async def test_worker_fails_skill_when_llm_is_disabled(
        self, prd10_engine, fixture_user, monkeypatch
    ):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(
            prd10_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            skill = await _make_skill(session, name="requires-real-llm")
            from agent_os.jobs.models import Job, JobStatus, JobType

            job = Job(
                user_id=fixture_user.id,
                job_type=JobType.SKILL_RUN.value,
                status=JobStatus.QUEUED.value,
                input={
                    "skill_id": str(skill.id),
                    "skill_name": skill.name,
                    "input": {"text": "must not produce placeholder"},
                    "save_output": False,
                },
            )
            session.add(job)
            await session.flush()
            run = SkillRun(
                user_id=fixture_user.id,
                skill_id=skill.id,
                job_id=job.id,
                status="queued",
                input=job.input["input"],
            )
            session.add(run)
            await session.commit()

            monkeypatch.delenv("AGENTOS_AI_LLM", raising=False)
            llm_provider.set_test_provider(None)
            llm_provider.reset_provider_for_test()
            from agent_os.jobs.service import process_job_once

            updated = await process_job_once(session, job.id)
            await session.commit()

            assert updated is not None
            assert updated.status == JobStatus.FAILED.value
            assert updated.error["code"] == "LLM_DISABLED"
            await session.refresh(run)
            assert run.status == "failed"
            assert run.error["code"] == "LLM_DISABLED"
            assert not run.output
# §16.7 — GET /api/v1/skills/{skill_id}/runs (run history for the detail drawer)
# §16.5 — _AGENT_ACTION_PROMPTS coverage + _build_skill_prompt deterministic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSkillRunHistory:
    """§16.7 — Recent SkillRun rows behind the v1.4 skillDetail drawer.

    The drawer hits ``GET /skills/{id}/runs`` so the user can see what
    their last few runs produced (status / completed_at / 240-char preview)
    instead of having to wait for a notification or refresh blindly.
    """

    async def test_history_404_for_unknown_skill(self, client):
        resp = await client.get(f"/api/v1/skills/{uuid.uuid4()}/runs")
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    async def test_history_invalid_uuid_400(self, client):
        resp = await client.get("/api/v1/skills/not-a-uuid/runs")
        assert resp.status_code == 400

    async def test_history_empty_returns_paginated_envelope(
        self, client, prd10_session
    ):
        skill = await _make_skill(prd10_session, name="history-empty")
        resp = await client.get(f"/api/v1/skills/{skill.id}/runs")
        body = resp.json()
        assert resp.status_code == 200
        assert body["data"]["items"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["has_more"] is False

    async def test_history_returns_runs_newest_first_with_preview(
        self, client, prd10_session, fixture_user
    ):
        skill = await _make_skill(prd10_session, name="history-skill")
        # 3 runs with different statuses + content lengths
        long_content = "测试输出 " * 80  # ~240 chars
        runs = []
        for idx, (status_val, content) in enumerate(
            [
                ("completed", "运行 1 简短输出"),
                ("running", ""),
                ("completed", long_content),
            ]
        ):
            r = SkillRun(
                user_id=fixture_user.id,
                skill_id=skill.id,
                status=status_val,
                input={"text": f"input #{idx}"},
                output={"kind": "skill_run", "content": content} if content else None,
            )
            prd10_session.add(r)
            runs.append(r)
            await prd10_session.commit()
            await prd10_session.refresh(r)

        resp = await client.get(f"/api/v1/skills/{skill.id}/runs")
        body = resp.json()
        assert resp.status_code == 200
        items = body["data"]["items"]
        assert len(items) == 3
        # Newest first — third run is the longest
        assert items[0]["status"] == "completed"
        assert len(items[0]["output_preview"]) <= 240
        assert items[0]["output_preview"]  # non-empty
        # Middle run (running, no output)
        assert items[1]["status"] == "running"
        assert items[1]["output_preview"] == ""
        # status / created_at / job_id keys all present
        for entry in items:
            assert "id" in entry
            assert "status" in entry
            assert "created_at" in entry
            assert "skill_id" in entry
            assert entry["skill_id"] == str(skill.id)

    async def test_history_only_returns_current_user_runs(
        self, client, prd10_session, fixture_user
    ):
        # Other user — same skill, but their run must NOT leak.
        from agent_os.auth.models import User

        other = User(
            id=uuid.uuid4(),
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            username=f"other_{uuid.uuid4().hex[:8]}",
            password_hash="x",
            is_active=True,
        )
        prd10_session.add(other)
        await prd10_session.commit()

        skill = await _make_skill(prd10_session, name="leak-test")
        prd10_session.add(
            SkillRun(
                user_id=other.id,
                skill_id=skill.id,
                status="completed",
                input={},
                output={"content": "another user's secret output"},
            )
        )
        prd10_session.add(
            SkillRun(
                user_id=fixture_user.id,
                skill_id=skill.id,
                status="completed",
                input={},
                output={"content": "my own output"},
            )
        )
        await prd10_session.commit()

        resp = await client.get(f"/api/v1/skills/{skill.id}/runs")
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert "my own output" in items[0]["output_preview"]
        # cross-user content must not leak
        for entry in items:
            assert "secret" not in entry["output_preview"]

    async def test_history_pagination_respects_page_and_page_size(
        self, client, prd10_session, fixture_user
    ):
        skill = await _make_skill(prd10_session, name="paginate")
        for i in range(7):
            prd10_session.add(
                SkillRun(
                    user_id=fixture_user.id,
                    skill_id=skill.id,
                    status="completed",
                    input={},
                    output={"content": f"run-{i}"},
                )
            )
        await prd10_session.commit()

        resp = await client.get(
            f"/api/v1/skills/{skill.id}/runs",
            params={"page": 1, "page_size": 3},
        )
        body = resp.json()["data"]
        assert len(body["items"]) == 3
        assert body["pagination"]["total"] == 7
        assert body["pagination"]["has_more"] is True

        resp2 = await client.get(
            f"/api/v1/skills/{skill.id}/runs",
            params={"page": 3, "page_size": 3},
        )
        body2 = resp2.json()["data"]
        assert len(body2["items"]) == 1  # last page has the leftover
        assert body2["pagination"]["has_more"] is False


# ---------------------------------------------------------------------------
# §16.5 — _AGENT_ACTION_PROMPTS / _build_skill_prompt unit coverage
# ---------------------------------------------------------------------------


class TestAgentActionPromptCoverage:
    """§16.5 — Verify the §16 worker prompt registry stays in sync with
    the seeded Skill catalog so a newly-seeded ``周报生成器`` / ``访谈洞察提炼``
    / ``Markdown 美化`` etc. resolves to a domain-specific Chinese system
    prompt rather than silently falling back to ``summarize``.
    """

    def test_registry_covers_seeded_agent_actions(self):
        from agent_os.jobs.service import _AGENT_ACTION_PROMPTS

        # The 12 seeded skills in scripts/seed_prd10.py reference these
        # ``agent_action`` keys via ``Skill.steps[0]['agent_action']``. If a
        # new seeded skill lands without a matching prompt, this test fires.
        seeded_keys = {
            "extract_insights",
            "weekly_report",
            "research_expand",
            "markdown_polish",
            "rate_ideas",
            "meeting_minutes",
            "competitor_compare",
            "knowledge_cards",
            "code_review",
            "email_polish",
            "okr_breakdown",
            "interview_outline",
            "summarize",  # default fallback
        }
        missing = seeded_keys - set(_AGENT_ACTION_PROMPTS.keys())
        assert not missing, f"§16.5 prompt registry missing: {missing}"

    def test_registry_returns_chinese_system_prompt(self):
        from agent_os.jobs.service import _AGENT_ACTION_PROMPTS

        # All entries should be in Chinese (>=10 CJK chars) — guards against
        # an accidental English fallback that would degrade the v1.4 demo.
        import re
        cjk = re.compile(r"[\u4e00-\u9fff]")
        for key, prompt in _AGENT_ACTION_PROMPTS.items():
            chars = cjk.findall(prompt)
            assert len(chars) >= 10, (
                f"{key} prompt is too thin in Chinese ({len(chars)} CJK chars):"
                f" {prompt!r}"
            )

    def test_build_skill_prompt_picks_action_specific_prompt(self):
        from agent_os.jobs.service import (
            _AGENT_ACTION_PROMPTS,
            _build_skill_prompt,
        )

        skill = Skill(
            id=uuid.uuid4(),
            name="周报生成器",
            description="自动整理本周记录，输出可发送的周报。",
            category="report",
            steps=[
                {
                    "order": 1,
                    "name": "summarize",
                    "agent_action": "weekly_report",
                }
            ],
            version="1.0",
            icon="sparkles",
            status="published",
            is_active=True,
            input_schema={},
            output_schema={},
        )
        sys_prompt, user_prompt = _build_skill_prompt(
            skill,
            {
                "instruction": "生成本周周报",
                "target": "灵感卡片",
                "text": "本周完成了 §16.5 后端单元测试增量。",
            },
        )

        assert "周报" in sys_prompt
        # Skill identity is stitched in — investors love a sourceable trail.
        assert "周报生成器" in sys_prompt
        assert "用户指令: 生成本周周报" in user_prompt
        assert "目标对象: 灵感卡片" in user_prompt
        assert "待处理内容:" in user_prompt
        # Default fallback must not have been used.
        assert sys_prompt.startswith(_AGENT_ACTION_PROMPTS["weekly_report"])

    def test_build_skill_prompt_unknown_action_falls_back_to_summarize(self):
        from agent_os.jobs.service import (
            _AGENT_ACTION_PROMPTS,
            _build_skill_prompt,
        )

        skill = Skill(
            id=uuid.uuid4(),
            name="未知 Skill",
            description="agent_action 不在注册表内，应优雅 fallback。",
            category="productivity",
            steps=[{"order": 1, "name": "summarize", "agent_action": "do_magic"}],
            version="1.0",
            icon="sparkles",
            status="published",
            is_active=True,
            input_schema={},
            output_schema={},
        )
        sys_prompt, user_prompt = _build_skill_prompt(skill, {})
        assert sys_prompt.startswith(_AGENT_ACTION_PROMPTS["summarize"])
        # Empty user input still produces a non-empty user_prompt placeholder
        # so the LLM has something to anchor on.
        assert user_prompt
        assert "未提供" in user_prompt or "示例" in user_prompt

    def test_build_skill_prompt_handles_no_steps(self):
        from agent_os.jobs.service import (
            _AGENT_ACTION_PROMPTS,
            _build_skill_prompt,
        )

        skill = Skill(
            id=uuid.uuid4(),
            name="No-step skill",
            description="边界：steps 为空，应 fallback 到 summarize。",
            category="productivity",
            steps=[],
            version="1.0",
            icon="sparkles",
            status="published",
            is_active=True,
            input_schema={},
            output_schema={},
        )
        sys_prompt, _ = _build_skill_prompt(skill, {"text": "hello"})
        assert sys_prompt.startswith(_AGENT_ACTION_PROMPTS["summarize"])
