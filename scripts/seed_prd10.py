"""Seed the PRD10 product-data tables with realistic demo content.

Per PRD10 §25.3, the frontend dev environment expects (per user):

    - 6 knowledge-base folders
    - 20 documents
    - 30 cards
    - 5 tasks
    - 5 notifications
    - 3 AI conversations / 10 AI messages   (owned by Agent 3, placeholder)
    - 5 Skills                              (owned by Agent 3, placeholder)
    - 10 SearchDocument                     (owned by Agent 3, placeholder)

This script is *idempotent*: running it twice with the same ``--email`` does
not create duplicate users; pre-existing seed rows are detected by the
``[seed]`` tag in their tags JSON column and removed before re-insertion so
the demo always lands in a known state.

Usage::

    python scripts/seed_prd10.py
    python scripts/seed_prd10.py --email demo@whyme.local --password demo123
    python scripts/seed_prd10.py --reset
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SEED_TAG = "seed"


async def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agent_os.auth.models import User
    from agent_os.auth.security import get_password_hash
    from agent_os.db.base import get_engine, init_db
    from agent_os.inbox.prd10_models import Prd10InboxItem
    from agent_os.ai.models import (
        AIConversation,
        AIConversationMode,
        AIMessage,
        AIMessageRole,
        AIMessageStatus,
    )
    from agent_os.insights.models import InsightStatus, InsightType, Prd10Insight
    from agent_os.kb.models import Document, DocumentStatus, DocumentType, Folder
    from agent_os.knowledge.models import Card
    from agent_os.notifications.models import Notification, NotificationType
    from agent_os.search_engine.embeddings import (
        embed_text,
        embedding_id_for_text,
        text_for_search_embedding,
    )
    from agent_os.search_engine.models import SearchIndex
    from agent_os.stage3.models import Skill
    from agent_os.tasks.models import PRD10Task

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    engine = get_engine()
    await init_db()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as db:
        user = (
            await db.execute(select(User).where(User.email == args.email))
        ).scalar_one_or_none()
        created_user = False
        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=args.email,
                username=args.email.split("@")[0] or f"seed_{uuid.uuid4().hex[:6]}",
                password_hash=get_password_hash(args.password),
                full_name=args.full_name,
                is_active=True,
                is_verified=True,
                settings={"seed": True},
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            created_user = True

        if args.reset or not created_user:
            await _wipe_existing_seed(
                db,
                user,
                Card,
                Document,
                Folder,
                Notification,
                Prd10InboxItem,
                AIConversation,
                AIMessage,
                Skill,
                SearchIndex,
                Prd10Insight,
                PRD10Task,
            )

        rng = random.Random(args.seed)

        folders = await _seed_folders(db, user, rng, Folder, count=6)
        documents = await _seed_documents(
            db, user, folders, rng, Document, DocumentStatus, DocumentType, count=20
        )
        cards = await _seed_cards(db, user, folders, documents, rng, Card, count=30)
        tasks = await _seed_tasks(
            db,
            user,
            folders,
            rng,
            PRD10Task,
            count=5,
        )
        notifications = await _seed_notifications(
            db, user, documents, rng, Notification, NotificationType, count=5
        )
        ai_conversations, ai_messages = await _seed_ai_conversations(
            db,
            user,
            rng,
            AIConversation,
            AIConversationMode,
            AIMessage,
            AIMessageRole,
            AIMessageStatus,
            conversation_count=3,
            total_messages=10,
        )
        skills = await _seed_skills(db, rng, Skill, count=12)
        search_documents = await _seed_search_documents(
            db,
            user,
            documents,
            cards,
            rng,
            SearchIndex,
            embed_text,
            embedding_id_for_text,
            text_for_search_embedding,
            count=50,
        )
        insights = await _seed_insights(
            db, user, rng, Prd10Insight, InsightType, InsightStatus, count=6
        )

        await db.commit()

    print(
        f"Seed completed for user '{args.email}':\n"
        f"  - folders:           {len(folders)}\n"
        f"  - documents:         {len(documents)}\n"
        f"  - cards:             {len(cards)}\n"
        f"  - tasks:             {len(tasks)}\n"
        f"  - notifications:     {len(notifications)}\n"
        f"  - ai_conversations:  {len(ai_conversations)}\n"
        f"  - ai_messages:       {len(ai_messages)}\n"
        f"  - skills:            {len(skills)}\n"
        f"  - search_documents:  {len(search_documents)}\n"
        f"  - insights:          {len(insights)}"
    )
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="demo@whyme.local")
    parser.add_argument("--password", default="demo-password-123")
    parser.add_argument("--full-name", default="Demo User")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Override DATABASE_URL for the seed run",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove previous seed rows for the same user before inserting",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic content",
    )
    return parser.parse_args(argv)


async def _wipe_existing_seed(
    db,
    user,
    Card,
    Document,
    Folder,
    Notification,
    Prd10InboxItem,
    AIConversation,
    AIMessage,
    Skill,
    SearchIndex,
    Prd10Insight=None,
    PRD10Task=None,
):
    """Best-effort cleanup of previous seed rows.

    Row identification: each table carries the ``[seed]`` marker either in a
    ``tags``, ``extra``, ``description``, ``content``, or ``search_metadata``
    column. We delete by user_id + marker so production data is never touched.
    """

    from sqlalchemy import String, cast, delete

    await db.execute(
        delete(Card).where(
            Card.user_id == user.id,
            cast(Card.tags, String).ilike(f"%{SEED_TAG}%"),
        )
    )
    await db.execute(
        delete(Document).where(
            Document.user_id == user.id,
            cast(Document.extra, String).ilike(f"%{SEED_TAG}%"),
        )
    )
    await db.execute(
        delete(Folder).where(
            Folder.user_id == user.id,
            Folder.description.ilike(f"%[{SEED_TAG}]%"),
        )
    )
    await db.execute(
        delete(Notification).where(
            Notification.user_id == user.id,
            Notification.content.ilike(f"%[{SEED_TAG}]%"),
        )
    )
    await db.execute(
        delete(Prd10InboxItem).where(
            Prd10InboxItem.user_id == user.id,
            cast(Prd10InboxItem.tags, String).ilike(f"%{SEED_TAG}%"),
        )
    )
    # Cascading delete handles AIMessage rows because AIConversation owns
    # ``cascade="all, delete-orphan"``.
    await db.execute(
        delete(AIConversation).where(
            AIConversation.user_id == user.id,
            cast(AIConversation.extra, String).ilike(f"%{SEED_TAG}%"),
        )
    )
    await db.execute(
        delete(SearchIndex).where(
            SearchIndex.user_id == user.id,
            cast(SearchIndex.search_metadata, String).ilike(f"%{SEED_TAG}%"),
        )
    )
    # Skills are workspace-scoped (no user_id); only purge our seed entries.
    await db.execute(
        delete(Skill).where(Skill.description.ilike(f"%[{SEED_TAG}]%"))
    )
    if Prd10Insight is not None:
        await db.execute(
            delete(Prd10Insight).where(
                Prd10Insight.user_id == user.id,
                cast(Prd10Insight.extra, String).ilike(f"%{SEED_TAG}%"),
            )
        )
    if PRD10Task is not None:
        await db.execute(
            delete(PRD10Task).where(
                PRD10Task.user_id == user.id,
                cast(PRD10Task.tags, String).ilike(f"%{SEED_TAG}%"),
            )
        )
    await db.commit()


async def _seed_folders(db, user, rng, Folder, *, count):
    presets = [
        ("产品设计", "blue", "icon-product"),
        ("技术架构", "violet", "icon-tech"),
        ("市场分析", "emerald", "icon-market"),
        ("运营笔记", "amber", "icon-ops"),
        ("个人成长", "rose", "icon-self"),
        ("待整理收件", "slate", "icon-inbox"),
    ]
    out = []
    for name, color, icon in presets[:count]:
        folder = Folder(
            user_id=user.id,
            name=name,
            description=f"{name} 相关的 PRD10 演示资料 [{SEED_TAG}]",
            color=color,
            icon=icon,
            is_favorite=rng.random() < 0.4,
            sort_order=len(out) * 10,
        )
        db.add(folder)
        out.append(folder)
    await db.flush()
    return out


async def _seed_documents(
    db, user, folders, rng, Document, DocumentStatus, DocumentType, *, count
):
    titles = [
        "Mydow 首页信息架构概览",
        "知识库文件夹层级模式",
        "AI 对话引用引擎设计",
        "搜索召回管线对比",
        "上传与解析任务调度",
        "用户偏好与主题切换",
        "通知系统的 SSE 接入",
        "Capture 输入流的去重策略",
        "标签体系与全局过滤",
        "首屏聚合接口性能",
        "AI 输出的 Markdown 规范",
        "知识图谱字段建模",
        "运营数据洞察周报",
        "Skill 市场的合规要求",
        "数字花园主题聚合",
        "Insight 评分与置信度",
        "审计日志与追溯",
        "上传安全与签名 URL",
        "脱敏与隐私要求清单",
        "联调对接清单与状态码",
    ]
    types = [
        DocumentType.NOTE.value,
        DocumentType.MARKDOWN.value,
        DocumentType.PDF.value,
        DocumentType.LINK.value,
        DocumentType.TEXT.value,
    ]
    out = []
    for i in range(count):
        folder = rng.choice(folders) if folders else None
        title = titles[i % len(titles)]
        doc = Document(
            user_id=user.id,
            folder_id=folder.id if folder else None,
            title=title,
            summary=f"{title} 的精炼摘要——演示用。",
            content=f"# {title}\n\n这是 PRD10 演示文档的正文。覆盖图、表与示例片段。",
            document_type=rng.choice(types),
            status=DocumentStatus.READY.value,
            tags=[SEED_TAG, "示例", folder.name if folder else "无目录"],
            extra={"seed": True, "source": "seed_prd10"},
            is_favorite=rng.random() < 0.25,
            word_count=rng.randint(300, 4200),
        )
        db.add(doc)
        out.append(doc)
    await db.flush()
    return out


async def _seed_cards(db, user, folders, documents, rng, Card, *, count):
    summaries = [
        "把首页内容流的卡片做成可拖拽的灵感板。",
        "AI 摘要默认 3 句话，长按展开完整段落。",
        "搜索建议优先展示高频命令而不是文档。",
        "上传超过 50MB 的文件提示拆分或压缩。",
        "知识库文档支持双链回溯。",
        "通知按主题归并而不是按时间。",
        "右侧洞察栏支持折叠与置顶。",
        "Inbox 的语音输入支持自动断句。",
        "收藏夹按标签快速过滤。",
        "AI 回答的引用支持悬停预览。",
    ]
    out = []
    for i in range(count):
        folder = rng.choice(folders) if folders else None
        related_doc = rng.choice(documents) if documents else None
        title = f"灵感卡片 #{i+1}"
        summary = rng.choice(summaries)
        card = Card(
            user_id=user.id,
            workspace_id=None,
            title=title,
            content=f"{title}\n\n{summary}\n\n（PRD10 演示数据）",
            summary=summary,
            content_type=rng.choice(["note", "article", "ai_output"]),
            tags=[SEED_TAG, "示例", folder.name if folder else "无目录"],
            entities=["Mydow", "PRD10"],
            folder_id=folder.id if folder else None,
            source_id=None,
            inbox_item_id=None,
            is_favorite=rng.random() < 0.3,
            is_archived=False,
            visibility="private",
        )
        if related_doc is not None:
            card.entities = card.entities + [related_doc.title]
        db.add(card)
        out.append(card)
    await db.flush()
    return out


async def _seed_tasks(
    db,
    user,
    folders,
    rng,
    PRD10Task,
    *,
    count,
):
    titles = [
        "整理上周的产品访谈纪要",
        "完善 KB 文件夹的标签体系",
        "为 AI 输出加上代码块复制",
        "审阅运营周报的指标定义",
        "迁移历史 Inbox 到知识库",
    ]
    out = []
    now = datetime.now(timezone.utc)
    priorities = ["medium", "high", "urgent"]
    source_types = ["manual", "ai", "inbox", "document", "insight"]
    for i in range(count):
        folder = rng.choice(folders) if folders else None
        item = PRD10Task(
            user_id=user.id,
            title=titles[i % len(titles)],
            description=f"任务: {titles[i % len(titles)]} (演示数据)",
            status="todo" if i < count - 1 else "doing",
            priority=rng.choice(priorities),
            due_at=now + timedelta(days=i + 1),
            source_type=rng.choice(source_types),
            source_id=str(folder.id) if folder else None,
            tags=[SEED_TAG, "任务"],
            extra={"seed": True, "folder_id": str(folder.id) if folder else None},
        )
        db.add(item)
        out.append(item)
    await db.flush()
    return out


async def _seed_notifications(db, user, documents, rng, Notification, NotificationType, *, count):
    out = []
    now = datetime.now(timezone.utc)
    examples = [
        ("已完成上周内容整理", NotificationType.JOB_COMPLETED.value),
        ("新文档已就绪", NotificationType.DOCUMENT_READY.value),
        ("生成了一条新洞察", NotificationType.INSIGHT_GENERATED.value),
        ("AI 输出已保存到知识库", NotificationType.AI_OUTPUT_SAVED.value),
        ("欢迎来到 Mydow", NotificationType.SYSTEM.value),
    ]
    for i, (title, ntype) in enumerate(examples[:count]):
        related_doc = rng.choice(documents) if documents and i < 3 else None
        notif = Notification(
            user_id=user.id,
            type=ntype,
            title=title,
            content=f"{title} (演示数据 [{SEED_TAG}])",
            object_type="document" if related_doc else None,
            object_id=str(related_doc.id) if related_doc else None,
            is_read=False,
            created_at=now - timedelta(hours=i),
        )
        db.add(notif)
        out.append(notif)
    await db.flush()
    return out


async def _seed_ai_conversations(
    db,
    user,
    rng,
    AIConversation,
    AIConversationMode,
    AIMessage,
    AIMessageRole,
    AIMessageStatus,
    *,
    conversation_count,
    total_messages,
):
    titles = [
        "PRD10 联调演示对话",
        "知识库整理思路",
        "灵感卡片标签优化",
    ]
    convs: list = []
    for i in range(conversation_count):
        conv = AIConversation(
            user_id=user.id,
            title=titles[i % len(titles)],
            mode=AIConversationMode.GENERAL.value,
            last_message_preview="",
            message_count=0,
            extra={"seed": True, "marker": f"[{SEED_TAG}]"},
        )
        db.add(conv)
        convs.append(conv)
    await db.flush()

    user_prompts = [
        "帮我列出本周需要整理的卡片。",
        "请总结上周的会议纪要。",
        "给我推荐 3 条产品迭代方向。",
        "如何把这份资料归到合适的文件夹？",
        "针对此问题，再给出一个反向观点。",
    ]
    assistant_replies = [
        "（演示）下面是按主题归并后的卡片列表……",
        "（演示）会议纪要总结：1) ……2) ……3) ……",
        "（演示）三条产品迭代方向：体验、性能、生态。",
        "（演示）建议归到“产品策略 / Mydow”。",
        "（演示）反向观点：先稳定再扩展，避免破坏既有体验。",
    ]
    msgs: list = []
    per_conv = max(2, total_messages // conversation_count)
    for conv in convs:
        for i in range(per_conv):
            user_msg = AIMessage(
                conversation_id=conv.id,
                user_id=user.id,
                role=AIMessageRole.USER.value,
                content=rng.choice(user_prompts),
                status=AIMessageStatus.COMPLETED.value,
            )
            db.add(user_msg)
            await db.flush()
            assistant_msg = AIMessage(
                conversation_id=conv.id,
                user_id=user.id,
                role=AIMessageRole.ASSISTANT.value,
                content=rng.choice(assistant_replies),
                status=AIMessageStatus.COMPLETED.value,
                parent_message_id=user_msg.id,
                model="placeholder",
                input_tokens=12,
                output_tokens=64,
                latency_ms=150,
            )
            db.add(assistant_msg)
            await db.flush()
            msgs.extend([user_msg, assistant_msg])
        conv.message_count = len(msgs)
        if msgs:
            conv.last_message_preview = msgs[-1].content[:120]
    await db.flush()
    # Trim to the requested total in case of rounding.
    return convs, msgs[: total_messages * 2]


async def _seed_skills(db, rng, Skill, *, count):
    """Seed Mydow Skills marketplace.

    Each preset is wired with a ``step.agent_action`` that the §16 worker
    (`agent_os.jobs.service::_materialize_skill_run`) recognises so a
    real `POST /skills/{id}/run` enqueues an LLM-backed job and the run
    produces persisted output (instead of staying queued forever).
    """

    # required_tags drives the §16.5 personalized recommendation algorithm —
    # the user's recent capture tags get matched against these via Jaccard +
    # weighted overlap, so the「猜你想用」 panel actually reflects what the
    # user has been working on.
    presets = [
        # (name, category, icon, description, agent_action, output_kind, tags)
        (
            "访谈洞察提炼",
            "interview",
            "icon-bulb",
            "把访谈记录提炼成结构化洞察、关键引用、待跟进项 [seed]",
            "extract_insights",
            "outline",
            ["用户研究", "访谈", "洞察", "用户体验"],
        ),
        (
            "周报生成器",
            "report",
            "icon-doc",
            "把本周卡片整理成可投递的周报草稿（成果 / 学到 / 下周计划）[seed]",
            "weekly_report",
            "report",
            ["周报", "运营笔记", "总结", "效率工具"],
        ),
        (
            "研究主题拓展",
            "research",
            "icon-search",
            "围绕主题给出 5 条拓展方向、关键资料、推荐阅读 [seed]",
            "research_expand",
            "outline",
            ["研究分析", "市场分析", "调研", "深度研究"],
        ),
        (
            "Markdown 美化",
            "format",
            "icon-edit",
            "把长文做 Markdown 美化：标题层级 / 代码块 / 引用 / 列表 [seed]",
            "markdown_polish",
            "markdown",
            ["写作", "格式", "Markdown"],
        ),
        (
            "脑暴评分",
            "ideate",
            "icon-stars",
            "对一组想法按可行性、影响力、创新度三维度打分排序 [seed]",
            "rate_ideas",
            "scorecard",
            ["灵感", "产品设计", "决策", "脑暴"],
        ),
        (
            "会议纪要总结",
            "writing",
            "icon-mic",
            "从会议录音文字稿生成 5W1H 纪要 + 待办清单 [seed]",
            "meeting_minutes",
            "outline",
            ["会议", "团队", "运营笔记", "协作"],
        ),
        (
            "竞品对比分析",
            "research",
            "icon-chart",
            "给 3-5 个竞品做功能 / 价格 / 用户评价对比表 [seed]",
            "competitor_compare",
            "table",
            ["市场分析", "竞品", "研究分析", "战略"],
        ),
        (
            "知识卡片生成",
            "productivity",
            "icon-card",
            "从一段文字提炼成 3 张可独立分享的知识卡片（概念/案例/金句）[seed]",
            "knowledge_cards",
            "cards",
            ["知识管理", "整理", "卡片", "个人成长"],
        ),
        (
            "代码 Review 助手",
            "development",
            "icon-code",
            "给一段代码做 Review：可读性 / 性能 / 安全 / 测试覆盖 [seed]",
            "code_review",
            "review",
            ["技术架构", "代码", "工程", "技术"],
        ),
        (
            "邮件润色",
            "writing",
            "icon-mail",
            "把口语化的邮件草稿润色成专业版（保留中文语气）[seed]",
            "email_polish",
            "markdown",
            ["写作", "沟通", "邮件", "团队"],
        ),
        (
            "OKR 拆解",
            "productivity",
            "icon-target",
            "把一个目标拆成 3-5 个 KR + 每个 KR 的 2-3 个 Action [seed]",
            "okr_breakdown",
            "outline",
            ["产品设计", "运营笔记", "战略", "OKR"],
        ),
        (
            "用户访谈大纲",
            "research",
            "icon-users",
            "围绕调研主题生成 8-12 个访谈问题（含开放式 + 量化）[seed]",
            "interview_outline",
            "outline",
            ["用户研究", "访谈", "调研", "用户体验"],
        ),
    ]
    out = []
    # Use min(count, len(presets)) so we never repeat presets — the
    # frontend skill-card grid filters by category, so duplicates would
    # break the dropdown counts.
    n = max(count, len(presets))
    for i in range(n):
        preset = presets[i % len(presets)]
        name, category, icon, description, agent_action, output_kind = preset[:6]
        required_tags = list(preset[6]) if len(preset) > 6 else []
        skill = Skill(
            name=name,
            description=description,
            category=category,
            steps=[
                {
                    "order": 1,
                    "name": agent_action,
                    "agent_action": agent_action,
                    "output_kind": output_kind,
                }
            ],
            version="1.0",
            icon=icon,
            status="published",
            usage_count=rng.randint(2, 80),
            is_installed_default=True,
            required_tags=required_tags,
            input_schema={
                "type": "object",
                "properties": {
                    "instruction": {"type": "string"},
                    "target": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "content": {"type": "string"},
                    "items": {"type": "array"},
                },
            },
        )
        db.add(skill)
        out.append(skill)
    await db.flush()
    return out


async def _seed_search_documents(
    db,
    user,
    documents,
    cards,
    rng,
    SearchIndex,
    embed_text,
    embedding_id_for_text,
    text_for_search_embedding,
    *,
    count,
):
    """Populate SearchIndex with rows that mirror real Documents/Cards.

    Half of the rows reference recent ``kb_documents`` so the search results
    can drill into the knowledge base; the rest reference ``cards`` for
    the Feed surface.
    """

    out = []
    sources = []
    for doc in documents[: max(1, count // 2)]:
        sources.append(("document", doc.id, doc.title, doc.summary or "", doc.content or ""))
    for card in cards[: count - len(sources)]:
        sources.append(("card", card.id, card.title, card.summary or "", card.content or ""))

    for kind, obj_id, title, summary, content in sources[:count]:
        embedding_text = text_for_search_embedding(title, summary, content)
        idx = SearchIndex(
            item_id=obj_id,
            item_type=kind,
            title=title,
            content=content[:1000],
            summary=summary[:500] if summary else None,
            user_id=user.id,
            embedding=embed_text(embedding_text),
            embedding_id=embedding_id_for_text(embedding_text),
            search_metadata={"seed": True, "tag": f"[{SEED_TAG}]"},
        )
        db.add(idx)
        out.append(idx)
    await db.flush()
    return out


async def _seed_insights(
    db, user, rng, Prd10Insight, InsightType, InsightStatus, *, count
):
    """Populate ``prd10_insights`` so PRD10 §12 (right-side insights centre)
    has real demo content driving the biz prototype's "完整洞察中心" page
    (see §15.16 + bridge.js::refreshInsightsFullPanel).

    Six rows by default: 4 themed insights covering the 4 main types
    (theme_trend / task_risk / knowledge_gap / connection) + 2 ``*_summary``
    rows that surface in the "最近洞察报告" list.
    """

    presets = [
        (
            InsightType.THEME_TREND.value,
            "你最近持续关注 AI 产品设计与用户研究",
            "过去 30 天，相关记录与阅读较上月增加 42%，建议深入梳理方法论。",
            "本周新增的卡片中 18 条与「AI 产品设计」「用户研究」相关；建议把这些"
            "灵感整理为一份『AI 产品设计 V1』方法论文档，沉淀到知识库的"
            "『产品设计』文件夹。",
        ),
        (
            InsightType.KNOWLEDGE_GAP.value,
            "你的内容捕捉正在从灵感记录转向方法论沉淀",
            "方法论类笔记占比提升 28%，知识结构逐渐清晰，可考虑体系化输出。",
            "建议为「产品设计」「用户研究」两个主题分别建立体系化目录："
            "1) 通用方法 2) 行业案例 3) 工具与模板，让方法论沉淀更易被复用。",
        ),
        (
            InsightType.CONNECTION.value,
            "知识连接在「Agent 责任」主题上明显增强",
            "本周新增 12 个关联节点，建议进一步拓展至团队与信任主题。",
            "数字花园里『Agent 责任』节点本周新连接到『团队协作』『AI 伦理』"
            "等 12 个其它节点，是一个高活跃枢纽；建议围绕它做一次深度专题写作。",
        ),
        (
            InsightType.TASK_RISK.value,
            "本周有 3 个任务接近截止时间但仍未完成",
            "建议优先处理「Mydow 演示脚本验收」「PRD10 §12 接入」「Skills 列表"
            "重排」三项，避免下周阻塞。",
            "「Mydow 演示脚本验收」剩余 2 天到期；「PRD10 §12 接入」剩余 3 天到期；"
            "「Skills 列表重排」剩余 4 天到期。建议今天先确认「演示脚本验收」"
            "的 demo 路径是否能完整跑通。",
        ),
        (
            InsightType.WEEKLY_SUMMARY.value,
            "本周回顾：产品设计与 AI 产品研究是主题",
            "本周产生 32 条记录，整理出 4 篇文档，3 项任务推进中。",
            "# 本周回顾\n\n- 灵感记录: 32\n- 整理文档: 4\n- 任务进展: 3\n\n"
            "## 高频主题\n- 产品设计: 14 条\n- AI 研究: 9 条\n- 用户研究: 6 条\n\n"
            "## 建议下周\n围绕「AI 产品研究」做一篇综述文档，把 9 条灵感"
            "组织成方法论 + 行业案例 + 工具模板。",
        ),
        (
            InsightType.DAILY_SUMMARY.value,
            "今日小结：完成了 4 条捕捉与 1 篇文档",
            "今日重点：产品设计灵感、Agent 责任主题；建议今晚整理一次。",
            "# 今日小结\n\n- 灵感记录: 4 条\n- 整理文档: 1 篇\n- 待整理收件箱: 2 条\n\n"
            "## 今日重点\n- 产品设计灵感: 3 条相关\n- Agent 责任主题: 1 条相关\n\n"
            "## 建议\n今晚抽出 20 分钟整理产品设计 3 条灵感为一份方法论草稿。",
        ),
    ]

    out = []
    now = datetime.now(timezone.utc)
    for idx, (insight_type, title, summary, body) in enumerate(presets[:count]):
        # Distribute creation timestamps across the past week so the list
        # ordering looks natural.
        created = now - timedelta(days=idx, hours=rng.randint(0, 6))
        row = Prd10Insight(
            user_id=user.id,
            insight_type=insight_type,
            title=title,
            summary=summary,
            body=body,
            status=InsightStatus.READY.value,
            extra={"seed": True, "tag": f"[{SEED_TAG}]", "preset_index": idx},
        )
        # Override server_default for deterministic seed ordering.
        row.created_at = created
        row.updated_at = created
        db.add(row)
        out.append(row)
    await db.flush()
    return out


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
