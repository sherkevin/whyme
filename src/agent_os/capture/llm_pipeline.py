"""LLM-driven enrichment for free-text captures (PRD10 §15.51 / §17.1).

When a user types raw inspiration into the home capture box, V1 stored the
text verbatim and stamped a 200-char prefix as the "summary". That made the
home feed look mock-y: every card shared the same first sentence as both
title and summary, and there were no useful tags / folder routing.

This module fixes that by calling the **real LLM** (DeepSeek / GLM / etc.,
the same provider the AI workspace uses) once per capture to generate:

- ``title``         — punchy 8-20 char Chinese title
- ``summary``       — 50-150 char abstract surfacing the key points
- ``tags``          — 3-7 short Chinese tags (will reuse the user's
                      existing folders by name when possible)
- ``folder_hint``   — best-guess KB folder name to file the card under
- ``folder_id``     — resolved folder UUID (existing or auto-created)
- ``folder_name``   — final folder name (mirrors folder_hint when matched)
- ``content_type``  — note / task / question / decision / insight
- ``model``         — model identifier reported by the provider

The original raw input is kept verbatim on ``InboxItem.raw_content`` and on
the resulting ``Card.content`` — we never mutate user content. Enrichment
is best-effort: if the LLM is unavailable or returns garbage we fall back
to a deterministic heuristic so the capture loop never breaks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.ai.llm_provider import get_provider, is_llm_enabled
from agent_os.kb.models import Folder

log = logging.getLogger(__name__)


# Trim inputs to keep token cost predictable. ~6k chars is roughly 3k tokens
# for Chinese text, well below the 8k context window of the cheapest models.
_MAX_INPUT_CHARS = 6000
_MAX_TITLE_CHARS = 80
_MAX_SUMMARY_CHARS = 240
_MAX_TAGS = 8
# §16.1 — paratera GLM-4.5-Flash p99 round-trip on a 6k-char Chinese
# prompt is ~15-25s, the heuristic 12s timeout was firing too often.
# Bumped to 30s default so real LLM enrichment actually finishes.
# Override via ``AGENTOS_CAPTURE_ENRICH_TIMEOUT`` for slower models.
_LLM_TIMEOUT_SECONDS = float(
    os.environ.get("AGENTOS_CAPTURE_ENRICH_TIMEOUT", "30")
)
# §16.1 — when the LLM returns a folder_hint with no exact / fuzzy
# match, opt into auto-creating the folder (user explicitly asked
# "如果没有合适的，新建一个 folder" 自动按 LLM tag 归集). Toggle off
# via env to restore the legacy "leave card unfiled" behaviour.
_AUTO_CREATE_FOLDER_ENABLED = (
    os.environ.get("AGENTOS_CAPTURE_AUTO_CREATE_FOLDER", "on").lower()
    in {"on", "1", "true", "yes"}
)
_VALID_CONTENT_TYPES = {"note", "task", "question", "decision", "insight"}


@dataclass
class CaptureEnrichment:
    """Structured output of the enrichment pipeline.

    All fields are guaranteed to be present (never ``None`` for the string
    fields); the caller can apply them directly to the ``Prd10InboxItem`` /
    ``Card`` rows.
    """

    title: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    folder_hint: str = ""
    folder_id: Any | None = None
    folder_name: str = ""
    content_type: str = "note"
    entities: list[str] = field(default_factory=list)
    model: str = ""
    used_llm: bool = False

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()[:_MAX_TITLE_CHARS]
        self.summary = (self.summary or "").strip()[:_MAX_SUMMARY_CHARS]
        self.tags = [
            t.strip().lstrip("#").strip()
            for t in (self.tags or [])
            if t and t.strip()
        ][:_MAX_TAGS]
        self.folder_hint = (self.folder_hint or "").strip()[:60]
        self.folder_name = (self.folder_name or "").strip()[:60]
        if not self.content_type or self.content_type not in _VALID_CONTENT_TYPES:
            self.content_type = "note"
        self.entities = [
            e.strip()
            for e in (self.entities or [])
            if isinstance(e, str) and e.strip()
        ][:16]


_FALLBACK_TAG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(产品|product|prd|路线|roadmap)", re.IGNORECASE), "产品"),
    (re.compile(r"(设计|design|ui|ux|界面)", re.IGNORECASE), "设计"),
    (re.compile(r"(技术|tech|架构|代码|code|api|后端|前端)", re.IGNORECASE), "技术"),
    (re.compile(r"(增长|growth|market|营销|渠道)", re.IGNORECASE), "增长"),
    (re.compile(r"(团队|team|协作|管理|hr)", re.IGNORECASE), "团队"),
    (re.compile(r"(用户|customer|访谈|interview|反馈)", re.IGNORECASE), "用户研究"),
    (re.compile(r"(策略|strategy|商业|business|融资)", re.IGNORECASE), "战略"),
    (re.compile(r"(读书|book|书|阅读|笔记)", re.IGNORECASE), "阅读"),
    (re.compile(r"(灵感|想法|idea)", re.IGNORECASE), "灵感"),
    (re.compile(r"(任务|todo|待办)", re.IGNORECASE), "任务"),
]


SYSTEM_PROMPT = (
    "你是 Mydow 的灵感整理助手。用户会提供一段原始的灵感/笔记/想法，你必须输出"
    "**纯 JSON**（不要 Markdown 代码块、不要解释、不要前后空行），结构如下：\n"
    "{\n"
    '  "title": "8-20 字中文标题，要点睛、有信息密度",\n'
    '  "summary": "50-150 字中文摘要，提炼用户原文的关键信息",\n'
    '  "tags": ["3-7 个简短的中文标签，每个 2-6 字"],\n'
    '  "folder_hint": "最适合归档的知识库文件夹名（优先从给定列表里挑，可新增）",\n'
    '  "content_type": "note 或 task 或 question 或 decision 或 insight",\n'
    '  "entities": ["抽取的专有名词：人名/产品名/公司等，可为空数组"]\n'
    "}\n"
    "规则：\n"
    "1) 标题不能直接复述原文第一句，要做提炼。\n"
    "2) tags 优先使用用户已有的标签词；如果没有匹配再造新词。\n"
    "3) folder_hint 必须是简短的中文名词（2-8 字），不要写完整句子；\n"
    "   优先精确匹配「可用文件夹」列表里的某个名字，匹配不到再返回一个新名字（必须能作为知识库分类）。\n"
    "4) content_type 默认 note；明显是任务（要做什么）→ task；明显在提问 → question；\n"
    "   决策结论 → decision；洞察类心得 → insight。\n"
    "5) 严禁输出任何 JSON 之外的字符。"
)


def _build_user_prompt(
    raw_content: str,
    fallback_title: str | None,
    available_folders: list[str],
    user_tags: list[str],
) -> str:
    parts: list[str] = []
    parts.append(
        f"用户原始输入（{len(raw_content)} 字）：\n```\n{raw_content[:_MAX_INPUT_CHARS]}\n```"
    )
    if fallback_title:
        parts.append(f"用户提供的暂定标题：{fallback_title}")
    if available_folders:
        parts.append("可用文件夹：" + " | ".join(available_folders[:30]))
    else:
        parts.append("可用文件夹：（暂无，folder_hint 可自由命名）")
    if user_tags:
        parts.append("用户已有标签：" + " ".join(user_tags[:30]))
    parts.append("请直接输出 JSON。")
    return "\n\n".join(parts)


def _heuristic_enrichment(
    raw_content: str,
    fallback_title: str | None,
    user_tags: list[str],
) -> CaptureEnrichment:
    """Deterministic fallback when LLM is unavailable."""

    text = (raw_content or "").strip()
    title = (fallback_title or "").strip()
    if not title:
        first_line = text.split("\n", 1)[0].strip()
        title = re.sub(r"[。！？.!?]+$", "", first_line)[:24]
        if not title:
            title = "新的灵感"
    summary = re.sub(r"\s+", " ", text)[:_MAX_SUMMARY_CHARS]
    tag_set: list[str] = list(user_tags or [])
    for pattern, tag in _FALLBACK_TAG_PATTERNS:
        if pattern.search(text) and tag not in tag_set:
            tag_set.append(tag)
        if len(tag_set) >= 5:
            break
    if not tag_set:
        tag_set = ["灵感"]
    return CaptureEnrichment(
        title=title,
        summary=summary,
        tags=tag_set,
        folder_hint="",
        folder_id=None,
        folder_name="",
        content_type="note",
        entities=[],
        model="",
        used_llm=False,
    )


async def _load_user_folders(db: AsyncSession, user_id: Any) -> list[Folder]:
    rows = (
        await db.execute(
            select(Folder)
            .where(
                Folder.user_id == user_id,
                Folder.deleted_at.is_(None),
            )
            .order_by(Folder.sort_order.asc(), Folder.updated_at.desc())
        )
    ).scalars().all()
    return list(rows)


def _match_folder(folder_hint: str, folders: list[Folder]) -> Folder | None:
    """Fuzzy-match the LLM hint to an existing folder.

    1) Exact case-insensitive name match.
    2) Substring containment in either direction (hint contains folder name
       OR folder name contains hint).
    3) Word-overlap heuristic for Chinese: if folder name shares ≥2 chars
       with the hint, treat as a match.
    """
    if not folder_hint or not folders:
        return None
    hint = folder_hint.lower().strip()
    for f in folders:
        if (f.name or "").lower().strip() == hint:
            return f
    for f in folders:
        name = (f.name or "").lower().strip()
        if not name:
            continue
        if name in hint or hint in name:
            return f
    hint_chars = set(hint)
    for f in folders:
        name = (f.name or "").lower().strip()
        if not name:
            continue
        common = hint_chars & set(name)
        if len(common) >= 2:
            return f
    return None


async def _autocreate_folder(
    db: AsyncSession,
    *,
    user_id: Any,
    name: str,
) -> Folder | None:
    """Create a new KB folder named ``name`` for the user.

    Used when the LLM returns a ``folder_hint`` that doesn't match any
    existing folder — instead of leaving the card unfiled we create a new
    bucket so users can see captures land in the right place from day one.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    cleaned = cleaned[:60]
    # Race protection: re-check immediately before insert.
    existing = (
        await db.execute(
            select(Folder).where(
                Folder.user_id == user_id,
                Folder.deleted_at.is_(None),
                Folder.name == cleaned,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    folder = Folder(
        user_id=user_id,
        name=cleaned,
        description=f"由 AI 根据捕获内容自动创建（{cleaned}）",
        is_favorite=False,
    )
    db.add(folder)
    await db.flush()
    return folder


def _coerce_json_payload(raw_text: str) -> dict[str, Any] | None:
    """LLMs occasionally wrap JSON in ```json ... ``` despite our prompt.

    Also tolerates Reasoning-mode prefixes like "（思考过程）..." by
    finding the *largest* balanced JSON object substring instead of the
    first/last brace, which fails when the reasoning narrative contains
    stray ``{`` / ``}`` characters.
    """
    if not raw_text:
        return None
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    candidates: list[str] = []
    if fenced:
        candidates.append(fenced.group(1))
    depth = 0
    start_idx = -1
    for idx, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start_idx = idx
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start_idx >= 0:
                    candidates.append(text[start_idx : idx + 1])
                    start_idx = -1
    candidates.sort(key=len, reverse=True)
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except (TypeError, ValueError):
            continue
        if isinstance(obj, dict):
            return obj
    log.warning("[capture.llm] JSON parse failed; raw=%r", raw_text[:240])
    return None


async def enrich_capture_with_llm(
    db: AsyncSession,
    *,
    user_id: Any,
    content: str,
    fallback_title: str | None = None,
    hint_tags: list[str] | None = None,
    target_folder_id: Any | None = None,
    timeout_seconds: float = _LLM_TIMEOUT_SECONDS,
) -> CaptureEnrichment:
    """Generate title/summary/tags/folder_hint from a raw text capture.

    Side-effects: reads the user's KB folder list (used both as LLM context
    and to resolve ``folder_hint`` → ``folder_id``), and **may create** a
    new ``Folder`` row if the LLM proposes a folder name with no match.
    Does not commit — the caller owns the transaction.
    """

    raw_content = (content or "").strip()
    user_tags = list(hint_tags or [])
    if not raw_content:
        return CaptureEnrichment(
            title=(fallback_title or "").strip() or "新的灵感",
            summary="",
            tags=user_tags,
            folder_hint="",
            folder_id=target_folder_id,
            folder_name="",
            content_type="note",
            entities=[],
            model="",
            used_llm=False,
        )

    folders = await _load_user_folders(db, user_id)
    folder_names = [f.name for f in folders if f.name]
    pinned_folder_id = target_folder_id

    if not is_llm_enabled():
        result = _heuristic_enrichment(raw_content, fallback_title, user_tags)
        result.folder_id = pinned_folder_id
        return result

    user_prompt = _build_user_prompt(
        raw_content=raw_content,
        fallback_title=fallback_title,
        available_folders=folder_names,
        user_tags=user_tags,
    )

    provider = get_provider()
    completion: dict[str, Any] | None = None
    # Prefer the app-wide LLM model unless capture explicitly overrides it.
    enrich_model = (
        (os.environ.get("CAPTURE_ENRICH_MODEL") or "").strip()
        or (os.environ.get("AGENTOS_AI_MODEL") or "").strip()
        or (os.environ.get("DEEPSEEK_MODEL") or "").strip()
        or "deepseek-v4-flash"
    )
    complete_kwargs: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
        "model": enrich_model,
    }
    try:
        completion = await asyncio.wait_for(
            provider.complete(**complete_kwargs),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        log.warning(
            "[capture.llm] enrichment timed out after %.1fs (content head=%r model=%s)",
            timeout_seconds,
            raw_content[:80],
            enrich_model or "default",
        )
    except Exception as exc:  # noqa: BLE001 — LLM failures must not break capture
        log.warning(
            "[capture.llm] provider.complete failed (model=%s): %s",
            enrich_model or "default", exc,
        )

    if not completion:
        result = _heuristic_enrichment(raw_content, fallback_title, user_tags)
        result.folder_id = pinned_folder_id
        return result

    content_str = completion.get("content") if isinstance(completion, dict) else None
    if not content_str and isinstance(completion, dict):
        msg = completion.get("message") or {}
        content_str = msg.get("content") if isinstance(msg, dict) else None
    payload = _coerce_json_payload(content_str or "")
    if not payload:
        log.info(
            "[capture.llm] LLM returned non-JSON; falling back. raw=%r",
            (content_str or "")[:200],
        )
        result = _heuristic_enrichment(raw_content, fallback_title, user_tags)
        result.folder_id = pinned_folder_id
        return result

    title = str(payload.get("title") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    raw_tags = payload.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [t for t in re.split(r"[，,、\s]+", raw_tags) if t]
    llm_tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    merged_tags: list[str] = []
    for t in (user_tags or []):
        if t and t not in merged_tags:
            merged_tags.append(t)
    for t in llm_tags:
        if t and t not in merged_tags:
            merged_tags.append(t)
    folder_hint = str(payload.get("folder_hint") or "").strip()
    content_type = str(payload.get("content_type") or "").strip().lower() or "note"
    raw_entities = payload.get("entities") or []
    parsed_entities: list[str] = []
    if isinstance(raw_entities, list):
        parsed_entities = [
            str(e).strip() for e in raw_entities if str(e).strip()
        ]

    folder_id = pinned_folder_id
    folder_name = ""
    if folder_id is None:
        match = _match_folder(folder_hint, folders)
        if match is not None:
            folder_id = match.id
            folder_name = match.name or ""
        elif folder_hint:
            new_folder = await _autocreate_folder(
                db,
                user_id=user_id,
                name=folder_hint,
            )
            if new_folder is not None:
                folder_id = new_folder.id
                folder_name = new_folder.name or ""

    if folder_id is not None and not folder_name:
        for f in folders:
            if f.id == folder_id:
                folder_name = f.name or ""
                break

    fallback_summary = raw_content[:_MAX_SUMMARY_CHARS]
    fallback_title_value = (
        title
        or (fallback_title or "").strip()
        or _heuristic_enrichment(raw_content, fallback_title, user_tags).title
    )

    enriched = CaptureEnrichment(
        title=fallback_title_value,
        summary=summary or fallback_summary,
        tags=merged_tags or ["灵感"],
        folder_hint=folder_hint,
        folder_id=folder_id,
        folder_name=folder_name,
        content_type=(
            content_type if content_type in _VALID_CONTENT_TYPES else "note"
        ),
        entities=parsed_entities,
        model=str(
            completion.get("model")
            or os.environ.get("MODEL")
            or os.environ.get("LLM_MODEL")
            or ""
        ),
        used_llm=True,
    )
    log.info(
        "[capture.llm] enriched user=%s len=%d title=%r tags=%s folder=%r model=%r used_llm=%s",
        user_id,
        len(raw_content),
        enriched.title,
        enriched.tags,
        enriched.folder_name or enriched.folder_hint,
        enriched.model,
        enriched.used_llm,
    )
    return enriched


async def patch_card_with_enrichment(
    *,
    user_id: Any,
    inbox_item_id: Any,
    card_id: Any | None = None,
    document_id: Any | None = None,
    content: str,
    fallback_title: str | None = None,
    hint_tags: list[str] | None = None,
) -> CaptureEnrichment | None:
    """§16.1 — Background re-enrichment that opens its own DB session.

    Use case: the synchronous capture endpoint has already saved a placeholder
    Card with the heuristic title/summary/tags so the user sees something
    instantly. We then spawn this helper as a fire-and-forget asyncio task
    that calls the LLM, parses the result, and PATCHes the Card / Document
    rows in place. The user's feed will pick up the LLM-improved metadata
    on the next refresh (or via a notification).

    Returns the `CaptureEnrichment` actually applied (None if nothing was
    applied — DB session opening failed or LLM hard-errored). Never raises:
    background tasks must be defensive.
    """

    from agent_os.db.base import get_sessionmaker
    from agent_os.knowledge.models import Card
    from agent_os.kb.models import Document
    from agent_os.notifications import NotificationType, create_notification
    from agent_os.search_engine.models import SearchIndex

    try:
        sessionmaker = get_sessionmaker()
    except Exception:  # noqa: BLE001
        log.exception("[capture.llm.async] cannot acquire sessionmaker")
        return None

    try:
        async with sessionmaker() as session:
            try:
                enrichment = await enrich_capture_with_llm(
                    session,
                    user_id=user_id,
                    content=content,
                    fallback_title=fallback_title,
                    hint_tags=hint_tags,
                )
            except Exception:  # noqa: BLE001
                log.exception("[capture.llm.async] enrich call crashed")
                return None

            if not enrichment.used_llm:
                # No LLM data to write — leave the heuristic placeholder intact.
                log.info(
                    "[capture.llm.async] heuristic-only result for inbox=%s; "
                    "skipping PATCH",
                    inbox_item_id,
                )
                return enrichment

            # 1) Update the Card row in place.
            updated_card_title: str | None = None
            if card_id is not None:
                try:
                    card = (
                        await session.execute(
                            select(Card).where(Card.id == card_id)
                        )
                    ).scalar_one_or_none()
                    if card is not None:
                        card.title = enrichment.title or card.title
                        card.summary = enrichment.summary or card.summary
                        card.tags = enrichment.tags or card.tags
                        if enrichment.folder_id is not None:
                            card.folder_id = enrichment.folder_id
                        if (
                            enrichment.content_type
                            and enrichment.content_type
                            in {"note", "task", "question", "decision", "insight"}
                        ):
                            card.content_type = enrichment.content_type
                        updated_card_title = card.title
                        if enrichment.entities:
                            card.entities = enrichment.entities or card.entities
                except Exception:  # noqa: BLE001
                    log.exception(
                        "[capture.llm.async] PATCH card %s failed", card_id
                    )

            # 2) Update the Document row in place (mirror the same fields so KB
            #    list reads the LLM-improved title / summary / tags / folder).
            if document_id is not None:
                try:
                    doc = (
                        await session.execute(
                            select(Document).where(Document.id == document_id)
                        )
                    ).scalar_one_or_none()
                    if doc is not None:
                        doc.title = enrichment.title or doc.title
                        doc.summary = enrichment.summary or doc.summary
                        doc.tags = enrichment.tags or doc.tags
                        if enrichment.folder_id is not None:
                            doc.folder_id = enrichment.folder_id
                except Exception:  # noqa: BLE001
                    log.exception(
                        "[capture.llm.async] PATCH document %s failed",
                        document_id,
                    )

            # 3) Refresh SearchIndex so global search picks up the new title /
            #    tags / summary immediately.
            try:
                target_object_id = card_id or document_id
                target_object_type = "card" if card_id is not None else "document"
                if target_object_id is not None:
                    existing_index = (
                        await session.execute(
                            select(SearchIndex).where(
                                SearchIndex.item_type == target_object_type,
                                SearchIndex.item_id == target_object_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if existing_index is not None:
                        existing_index.title = enrichment.title or existing_index.title
                        existing_index.summary = (
                            enrichment.summary or existing_index.summary
                        )
                        existing_index.tags = enrichment.tags or existing_index.tags
            except Exception:  # noqa: BLE001
                log.exception("[capture.llm.async] PATCH SearchIndex failed")

            # 4) Drop a notification so the FE knows the card has been
            #    auto-organised. Best effort; never block on this.
            try:
                folder_label = (
                    enrichment.folder_name
                    or enrichment.folder_hint
                    or "默认收件箱"
                )
                title = updated_card_title or enrichment.title or "新灵感"
                await create_notification(
                    session,
                    user_id=user_id,
                    type=NotificationType.JOB_COMPLETED,
                    title="AI 已为灵感卡片生成摘要",
                    content=f"AI 已为「{title}」生成摘要，归入「{folder_label}」",
                    object_type="inbox_item",
                    object_id=str(inbox_item_id),
                )
            except Exception:  # noqa: BLE001
                log.exception("[capture.llm.async] create_notification failed")

            try:
                await session.commit()
            except Exception:  # noqa: BLE001
                log.exception(
                    "[capture.llm.async] commit failed for inbox=%s",
                    inbox_item_id,
                )
                return None

            log.info(
                "[capture.llm.async] PATCHed card/doc for inbox=%s with LLM"
                " title=%r tags=%s folder=%r",
                inbox_item_id,
                enrichment.title,
                enrichment.tags,
                enrichment.folder_name or enrichment.folder_hint,
            )
            return enrichment
    except Exception:  # noqa: BLE001
        log.exception(
            "[capture.llm.async] outer scope crashed for inbox=%s", inbox_item_id
        )
        return None


__all__ = [
    "CaptureEnrichment",
    "enrich_capture_with_llm",
    "patch_card_with_enrichment",
]
