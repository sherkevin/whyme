"""PRD10 Mydow AI conversations router.

Implements the §11 endpoint group:

* ``GET    /api/v1/ai/conversations``                    — list (with keyword + pagination)
* ``POST   /api/v1/ai/conversations``                    — create
* ``GET    /api/v1/ai/conversations/{id}``               — detail (header + messages)
* ``POST   /api/v1/ai/conversations/{id}/messages``      — send a user message, get a synchronous assistant reply (streaming is P1)
* ``POST   /api/v1/ai/messages/{message_id}/save-to-kb`` — queue a job that asks the KB pipeline to persist the assistant message as a Document
* ``POST   /api/v1/ai/messages/{message_id}/create-tasks`` — queue a job that asks the Tasks pipeline to persist tasks derived from the assistant message

Why a synchronous assistant reply for the MVP:

PRD10 §11.4 expects streaming via SSE (a P1 deliverable). To unblock end-to-end
contract testing today (and Agent 2's "save assistant output as document/task"
flows) we persist a deterministic placeholder reply with ``status="completed"``,
``citations=[]``, and ``model="placeholder"``. The streaming code path can swap
in a real LLM provider later without changing the persisted shape.

Save endpoints intentionally **only enqueue a Job** and do not yet write
``kb_documents`` / ``prd10_tasks`` rows directly. Agent 2 owns those tables;
this router gives them the trigger contract while keeping the API responsive.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.agent.react_agent import run_react_agent
from agent_os.ai.llm_provider import get_provider, is_llm_enabled
from agent_os.ai.models import (
    AIConversation,
    AIConversationMode,
    AIMessage,
    AIMessageRole,
    AIMessageStatus,
)
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.kb.models import Chunk as KBChunk
from agent_os.kb.models import Document as KBDocument
from agent_os.kb.models import Folder as KBFolder
from agent_os.search_engine.embeddings import (
    EMBEDDING_DIMENSION,
    cosine_similarity,
    embed_text,
    text_for_search_embedding,
    tokenize,
)
from agent_os.search_engine.models import SearchIndex

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/ai", tags=["ai-prd10"])


# ---------------------------------------------------------------------------
# SSE keepalive / reconnect helpers (PRD10 §12.4 — see todo-tasks.md)
# ---------------------------------------------------------------------------


# Default 15s. Cloudflare/nginx kill idle SSE around 60s by default; 15s
# gives ~4 keepalive frames per minute which is below every common proxy
# threshold. Override via ``AGENTOS_SSE_HEARTBEAT_SECONDS``.
_DEFAULT_SSE_HEARTBEAT_SECONDS = 15

# Hint to the EventSource client to retry after this many ms when the
# connection drops. Wrapped into the very first SSE block (alongside the
# ``meta`` event) so testbench parsers that group by blank-line boundaries
# still keep their event_types ordering intact.
_SSE_RETRY_HINT = "retry: 5000\n"


def _heartbeat_seconds() -> int:
    """Read ``AGENTOS_SSE_HEARTBEAT_SECONDS`` with a sane default."""

    raw = os.getenv("AGENTOS_SSE_HEARTBEAT_SECONDS")
    try:
        value = int(raw) if raw is not None else _DEFAULT_SSE_HEARTBEAT_SECONDS
    except (TypeError, ValueError):
        return _DEFAULT_SSE_HEARTBEAT_SECONDS
    return value if value > 0 else _DEFAULT_SSE_HEARTBEAT_SECONDS


_HEARTBEAT_SENTINEL = object()
_STREAM_END_SENTINEL = object()


async def _wrap_with_heartbeat(
    upstream: AsyncIterator[Any],
    heartbeat_seconds: float,
) -> AsyncIterator[Any]:
    """Pump ``upstream`` chunks through a queue and inject keepalive markers.

    Yields each chunk from ``upstream`` as it arrives, and also yields the
    sentinel ``_HEARTBEAT_SENTINEL`` whenever ``heartbeat_seconds`` elapses
    without a chunk. The consumer is expected to translate the sentinel
    into a ``keepalive`` SSE event so proxies / load balancers don't kill
    the idle TCP connection.

    Implementation note: we use a producer task + queue rather than wrapping
    the iterator with ``asyncio.wait_for`` directly, because cancelling
    ``__anext__`` on a real LLM provider's stream can leave the upstream
    HTTP connection in a half-broken state.
    """

    queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=16)
    error_box: list[BaseException] = []

    async def _producer() -> None:
        try:
            async for chunk in upstream:
                await queue.put(chunk)
        except BaseException as exc:  # pragma: no cover - defensive
            error_box.append(exc)
        finally:
            await queue.put(_STREAM_END_SENTINEL)

    task = asyncio.create_task(_producer())
    try:
        while True:
            try:
                item = await asyncio.wait_for(
                    queue.get(), timeout=float(heartbeat_seconds)
                )
            except TimeoutError:
                yield _HEARTBEAT_SENTINEL
                continue
            if item is _STREAM_END_SENTINEL:
                if error_box:
                    raise error_box[0]
                return
            yield item
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------


class ConversationCreate(BaseModel):
    """PRD10 §11.2 request body."""

    title: str | None = Field(default=None, max_length=255)
    mode: str | None = Field(
        default=AIConversationMode.GENERAL.value,
        description="One of general/knowledge/planning/report",
    )
    context_scope: dict[str, Any] | None = None


class MessageSend(BaseModel):
    """PRD10 §11.4 request body (streaming opt-in is a separate endpoint).

    v1.4 also threads two optional fields through:
    * ``model`` — audit-only display value. Product policy currently routes
      every v1.4 AI call to the configured DeepSeek v4 flash provider.
    * ``mode``  — ``"efficient"`` (default) or ``"all"``/``"agent"`` to
      activate the §15.49 ReAct agent loop with multi-step retrieval +
      progress events streamed as ``event: agent_step``.
    """

    content: str = Field(..., min_length=1)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context_scope: dict[str, Any] | None = None
    model: str | None = None
    mode: str | None = None


class SaveToKbRequest(BaseModel):
    """PRD10 §11.7 request body."""

    folder_id: str | None = None
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreateTasksRequest(BaseModel):
    """PRD10 §11.8 request body."""

    tasks: list[dict[str, Any]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    """v1.4 § ``POST /ai/messages/:id/feedback`` body — see business owner
    `Mydow_Web_API_Buttons_v1.1.md` §7 (赞 / 踩 / 文字反馈).

    Persisted as a `Notification(type="ai_feedback", object_type="ai_message",
    object_id=message_id)` so V1 ships without a schema migration. Future V2
    can promote this to a dedicated `ai_message_feedback` table without
    breaking the contract.
    """

    rating: str = Field(
        ...,
        pattern="^(up|down)$",
        description="up = 点赞 (`感谢反馈`); down = 点踩 (`已记录反馈`)",
    )
    comment: str | None = Field(default=None, max_length=2000)


class ConversationPatchRequest(BaseModel):
    """v1.4 §3.6 ``PATCH /ai/conversations/{id}``.

    Supports rename / change mode / pin without a schema migration. Mode is
    validated against the same allow-list used by ``POST /conversations``.
    """

    title: str | None = Field(default=None, max_length=255)
    mode: str | None = Field(default=None, description="general/knowledge/planning/report")
    context_scope: dict[str, Any] | None = None
    pinned: bool | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_MODES: tuple[str, ...] = tuple(m.value for m in AIConversationMode)

_PLACEHOLDER_REPLY = (
    "（占位回答）已收到你的请求；当前后端处于 PRD10 MVP 阶段，"
    "尚未接入真实 LLM。流式输出 (`/messages/{id}/stream`) 在 P1 交付。"
)


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": f"Invalid {field}"},
        )


async def _load_owned_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, user: User
) -> AIConversation:
    stmt = select(AIConversation).where(
        AIConversation.id == conversation_id,
        AIConversation.user_id == user.id,
        AIConversation.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Conversation not found"},
        )
    return conv


async def _load_owned_assistant_message(
    db: AsyncSession, message_id: uuid.UUID, user: User
) -> AIMessage:
    stmt = select(AIMessage).where(
        AIMessage.id == message_id,
        AIMessage.user_id == user.id,
    )
    result = await db.execute(stmt)
    msg = result.scalar_one_or_none()
    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Message not found"},
        )
    if msg.role != AIMessageRole.ASSISTANT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Only assistant messages may be saved to KB or tasks",
            },
        )
    return msg


def _context_item(
    row: SearchIndex,
    query: str = "",
    *,
    score: float = 0.0,
    folder_name: str | None = None,
    folder_id: str | None = None,
) -> dict[str, Any]:
    """Map SearchIndex to the right-side context/citation shape."""

    content = (row.summary or row.content or "").strip()
    snippet = _highlight_snippet(content, query, max_chars=240) or content[:240]

    obj_type = row.item_type or "document"
    obj_id = str(row.item_id)
    anchor_url: str | None = None
    if obj_type == "document":
        anchor_url = f"/mydow/biz_v14/#/doc/{obj_id}"
    elif obj_type == "card":
        anchor_url = f"/mydow/biz_v14/#card/{obj_id}"

    return {
        "object_type": obj_type,
        "object_id": obj_id,
        "title": row.title or "（无标题）",
        "summary": row.summary,
        "snippet": snippet,
        "score": float(round(score, 4)),
        "folder_id": folder_id,
        "folder_name": folder_name,
        "anchor_url": anchor_url,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _doc_context_item(
    doc: KBDocument,
    *,
    query: str = "",
    score: float = 0.0,
    folder_name: str | None = None,
) -> dict[str, Any]:
    """Map kb_documents row → citation shape (used when SearchIndex misses)."""

    body = (doc.content or doc.summary or "").strip()
    snippet = _highlight_snippet(body, query, max_chars=300) or body[:300]
    return {
        "object_type": "document",
        "object_id": str(doc.id),
        "title": doc.title or "（无标题）",
        "summary": doc.summary,
        "snippet": snippet,
        "full_text": body[:4000],
        "score": float(round(score, 4)),
        "folder_id": str(doc.folder_id) if doc.folder_id else None,
        "folder_name": folder_name,
        "anchor_url": f"/mydow/biz_v14/#/doc/{doc.id}",
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _sanitize_assistant_content(content: str) -> str:
    """Strip visible prompt-planning prose before persisting/rendering output.

    Some providers occasionally return meta-analysis such as "用户询问..." as
    ordinary content. That is not user-facing answer text, so we trim it while
    leaving normal citations and final answers intact.
    """

    text = (content or "").strip()
    if not text:
        return text
    probe = text[:900]
    internal_hits = (
        "用户询问",
        "我需要查看",
        "查看知识库内容",
        "根据指示",
        "我应该",
        "I need to",
        "We need to",
    )
    if not any(hit in probe for hit in internal_hits):
        return text

    process_sentence_hits = (
        "用户询问",
        "我需要",
        "我可以看到",
        "这正好是",
        "根据指示",
        "我应该",
        "I need to",
        "We need to",
    )
    sentence_parts = re.split(r"(?<=[。！？!?])\s*", text)
    if len(sentence_parts) > 1:
        filtered = [
            part for part in sentence_parts
            if part and not any(hit in part for hit in process_sentence_hits)
        ]
        cleaned_sentence_text = "".join(filtered).strip()
        if cleaned_sentence_text and cleaned_sentence_text != text:
            text = cleaned_sentence_text

    final_markers = [
        "知识库中没有",
        "根据您提供",
        "根据你提供",
        "基于文档",
        "从文档来看",
        "以下是",
        "可以这样",
        "建议",
    ]
    positions = [text.find(marker) for marker in final_markers if text.find(marker) > 80]
    if positions:
        return text[min(positions):].strip()

    cleaned_lines: list[str] = []
    skip_patterns = [
        r"^\s*用户询问",
        r"^\s*我需要",
        r"^\s*查看知识库内容",
        r"^\s*这些文档",
        r"^\s*根据指示",
        r"^\s*我应该",
        r"^\s*I need to",
        r"^\s*We need to",
    ]
    for line in text.splitlines():
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in skip_patterns):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or text


def _format_llm_provider_error(exc: Exception | str) -> str:
    """Return a clear user-facing error for real provider failures."""

    raw = str(exc or "").strip()
    lower = raw.lower()
    if "team not allowed to access model" in lower and "deepseek-v4-flash" in lower:
        return (
            "DeepSeek v4 flash 调用失败：当前 API Key 或团队没有 "
            "deepseek-v4-flash 访问权限，请更换具备该模型权限的 DeepSeek API Key。"
        )
    if "authenticationerror" in lower or "invalid api key" in lower or "unauthorized" in lower:
        return "LLM 调用鉴权失败：请检查 DeepSeek API Key 和 API Base 配置。"
    return raw or "LLM provider failed"


def _highlight_snippet(text: str, query: str, *, max_chars: int = 280) -> str:
    """Find the most-relevant slice of ``text`` for ``query`` and mark hits.

    Picks a window centered on the first matching keyword (or the document
    head when nothing overlaps), wraps every query token with ``<mark>``.
    """

    text = (text or "").strip()
    if not text:
        return ""
    query_tokens = [t for t in tokenize(query) if len(t) >= 2]
    lower = text.lower()

    # Find the first occurrence of any meaningful token to anchor the window.
    anchor = -1
    for token in query_tokens:
        idx = lower.find(token)
        if idx >= 0 and (anchor < 0 or idx < anchor):
            anchor = idx
    if anchor < 0:
        snippet = text[:max_chars]
    else:
        half = max_chars // 2
        start = max(0, anchor - half)
        end = min(len(text), start + max_chars)
        snippet = ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")

    if not query_tokens:
        return snippet
    # Highlight every distinct token (preserve casing of original text).
    out = snippet
    for token in dict.fromkeys(query_tokens):  # preserve order, dedupe
        if not token:
            continue
        # Case-insensitive replace using regex while preserving original casing.
        import re

        out = re.sub(
            re.escape(token),
            lambda m: f"<mark>{m.group(0)}</mark>",
            out,
            flags=re.IGNORECASE,
        )
    return out


def _citation_from_context(item: dict[str, Any]) -> dict[str, Any]:
    """PRD10 §11.4 citation shape — kept lean for SSE payload + UI chips.

    Includes ``chunk_id`` / ``folder_id`` / ``folder_name`` / ``score`` /
    ``anchor_url`` (deep-link into the KB doc) when available so the v1.4
    GPT-style chat bubbles can render real citation chips that link back
    to the knowledge base.
    """

    cite: dict[str, Any] = {
        "object_type": item["object_type"],
        "object_id": item["object_id"],
        "title": item["title"],
        "snippet": item["snippet"],
    }
    for k in ("score", "chunk_id", "folder_id", "folder_name", "anchor_url"):
        v = item.get(k)
        if v is not None:
            cite[k] = v
    return cite


def _normalize_agent_citation_item(c: dict[str, Any]) -> dict[str, Any]:
    """Map ``final_answer.citations[]`` into the dict shape ``_citation_from_context`` expects."""

    oid = str(c.get("object_id") or c.get("document_id") or "").strip()
    otype = (c.get("object_type") or "document").strip()
    title = (c.get("title") or "未命名").strip()
    snippet = (c.get("snippet") or "").strip()
    item: dict[str, Any] = {
        "object_type": otype or "document",
        "object_id": oid or "unknown",
        "title": title,
        "snippet": snippet[:500],
    }
    for optional in ("folder_name", "anchor_url", "score", "folder_id", "chunk_id"):
        v = c.get(optional)
        if v is not None:
            item[optional] = v
    return item


_AGENT_STOPWORDS_ZH = {
    "什么", "怎么", "如何", "请问", "请", "我", "我们", "你", "你们", "他", "她",
    "的", "了", "在", "是", "和", "与", "或", "也", "都", "就", "把", "给",
    "一下", "一个", "这", "那", "这个", "那个",
}
_AGENT_STOPWORDS_EN = {
    "what", "how", "the", "a", "an", "is", "are", "was", "were", "to", "of",
    "in", "for", "on", "at", "by", "with", "from", "about", "you", "i", "we",
    "please", "tell", "me", "show",
}


def _agent_subqueries(question: str, *, max_sub: int = 2) -> list[str]:
    """§15.49 — Cheap heuristic decomposition of a user question into 1-2
    sub-queries the RAG layer can fan-out over.

    Goal: surface KB material the user didn't literally mention without
    paying for an extra LLM round-trip. Strategy:

    * Tokenize (``embeddings.tokenize`` already gives us CJK bigrams +
      English words).
    * Drop common stopwords + 1-char tokens.
    * Prefer the longest distinct tokens — they are most likely the
      content nouns that anchor the user's intent.

    Returns an empty list when the question is too short or all-stopword.
    """

    if not question or not question.strip():
        return []
    raw_tokens = tokenize(question)
    keep: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        # Skip very short tokens (single CJK char, single letter).
        if len(token) < 4:
            continue
        # Skip likely stopword/filler English; CJK bigrams already filtered.
        lower = token.lower()
        if lower in _AGENT_STOPWORDS_EN or token in _AGENT_STOPWORDS_ZH:
            continue
        if lower in seen:
            continue
        seen.add(lower)
        keep.append(token)
    if not keep:
        return []
    # Sort by length desc with original-order tie-break — longer tokens
    # carry more semantic weight than 2-char CJK bigrams.
    keep.sort(key=lambda t: -len(t))
    return keep[:max_sub]


def _build_chat_messages(
    conv: AIConversation,
    history: list[AIMessage],
    user_content: str,
    related_context: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Render the LLM message list from PRD10 §11 conversation state.

    §16 — system prompt now spells out RAG semantics so the LLM:
      1. Replies in the user's language (中文 first by default for Mydow demo)
      2. Cites the context passages it actually uses, by ``[#1] [#2] …``
      3. Says "知识库里没有这条信息" instead of hallucinating when the
         provided context cannot answer the question
    """

    sys_prompt_parts = [
        "你是 Mydow AI —— 一个紧密绑定用户个人知识库的中文智能助手。",
        "用户提到「我的知识库」「我的笔记」「我的 KB」「这个项目」「我们」时，一定指下面【相关知识库内容】里给出的真实资料；不要回答「我没有访问权限」或「我无法访问您的私有数据」；这些片段就是用户的私有知识库内容。",
        "回答规则：",
        "- 默认用中文回答，简洁、有条理（要点 / 表格 / 步骤）；",
        "- 当下面提供了「相关知识库内容」时，**必须**基于这些内容作答，"
        "并用 `[#1] [#2]` 等引用标记把所用资料标到原句旁；",
        "- 引用片段后请尽量复述其中的关键词或短语，让用户清楚你看到了哪条；",
        "- 只有在所有提供片段都明显与问题无关时，才说「知识库中没有这条信息」"
        "并给出基于通识的简短建议；不要编造引用。",
    ]
    sys_prompt_parts.extend(
        [
            "Never reveal hidden reasoning, planning, prompt analysis, chain-of-thought, or phrases like '用户询问', '我需要查看', '根据指示', 'I need to'. Return only the final answer for the user.",
            "When attached documents are provided below, treat their passages as readable knowledge-base content. Do not claim you cannot see the document unless the passage itself is empty.",
        ]
    )

    if conv.mode:
        sys_prompt_parts.append(f"当前对话模式: `{conv.mode}`。")

    if related_context:
        passages = []
        for idx, item in enumerate(related_context, start=1):
            title = (item.get("title") or "").strip() or f"片段#{idx}"
            obj_type = item.get("object_type") or "doc"
            folder_name = (item.get("folder_name") or "").strip()
            snippet_raw = (
                item.get("full_text")
                or item.get("snippet")
                or item.get("summary")
                or ""
            ).strip()
            # Strip <mark>...</mark> wrappers — they live on the UI, not the LLM.
            snippet_clean = snippet_raw.replace("<mark>", "").replace("</mark>", "")
            head = f"[#{idx}] ({obj_type}) {title}"
            if folder_name:
                head += f" · 文件夹「{folder_name}」"
            passages.append(f"{head}\n  {snippet_clean[:1800]}")
        sys_prompt_parts.append(
            "相关知识库内容（按相关度排序，请按需引用 [#1] [#2] …）:\n"
            + "\n\n".join(passages)
        )
    else:
        sys_prompt_parts.append(
            "（本次没有命中知识库内容；如有需要，请告知用户去 capture 输入框记录新内容。）"
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "\n\n".join(sys_prompt_parts)}
    ]
    for past in history:
        if past.role not in (
            AIMessageRole.USER.value,
            AIMessageRole.ASSISTANT.value,
        ):
            continue
        messages.append({"role": past.role, "content": past.content})
    messages.append({"role": "user", "content": user_content})
    return messages


async def _invoke_llm_complete(
    messages: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None, str | None]:
    """Call the configured LLM provider.

    Returns ``(content, usage, error)``. When the real provider fails we
    surface the failure to the caller instead of fabricating a placeholder
    answer; product flows must never persist fake AI output as successful.
    """

    try:
        provider = get_provider()
        result = await provider.complete(messages)
        content = _sanitize_assistant_content(str((result or {}).get("content") or "").strip())
        if not content:
            if (result or {}).get("reasoning_only"):
                return (
                    "",
                    (result or {}).get("usage"),
                    "LLM 只返回了推理内容，没有返回可展示的最终回答；请增加 max_tokens 或检查模型输出配置。",
                )
            return "", (result or {}).get("usage"), "LLM provider returned empty content"
        usage = (result or {}).get("usage")
        return content, usage, None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("LLM provider failed: %s", exc)
        return "", None, _format_llm_provider_error(exc)


def _uuid_values(values: list[Any] | None) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    for value in values or []:
        try:
            parsed.append(uuid.UUID(str(value)))
        except (ValueError, TypeError):
            continue
    return parsed


def _safe_embedding_vector(value: Any) -> list[float] | None:
    """Coerce a stored embedding (list/JSON/None) into a list[float]."""

    if value is None:
        return None
    if isinstance(value, list):
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(data, list):
            try:
                return [float(v) for v in data]
            except (TypeError, ValueError):
                return None
    return None


async def _rerank_chunks_for_documents(
    db: AsyncSession,
    document_ids: list[uuid.UUID],
    query_vec: list[float],
    *,
    top_per_doc: int = 1,
) -> dict[str, dict[str, Any]]:
    """For each document id pick the chunk with the highest cosine vs. query.

    Returns a mapping ``str(doc_id) → {chunk_id, chunk_index, content, score}``.
    Missing tables / chunks degrade to an empty dict so callers fall back to
    the document-level snippet.
    """

    if not document_ids or not query_vec:
        return {}
    try:
        rows = (
            await db.execute(
                select(KBChunk).where(KBChunk.document_id.in_(document_ids))
            )
        ).scalars().all()
    except SQLAlchemyError:
        return {}
    by_doc: dict[str, list[tuple[float, KBChunk]]] = {}
    for chunk in rows:
        emb = _safe_embedding_vector(chunk.embedding)
        if emb is None or len(emb) != len(query_vec):
            emb = embed_text(chunk.content or "", dimension=len(query_vec))
        score = cosine_similarity(query_vec, emb)
        if score > 0:
            by_doc.setdefault(str(chunk.document_id), []).append((score, chunk))
    out: dict[str, dict[str, Any]] = {}
    for doc_id, scored in by_doc.items():
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[:top_per_doc][0] if scored else None
        if top is None:
            continue
        score, chunk = top
        out[doc_id] = {
            "chunk_id": str(chunk.id),
            "chunk_index": chunk.chunk_index,
            "content": chunk.content or "",
            "score": float(score),
        }
    return out


async def _enrich_with_chunks_and_folder(
    db: AsyncSession,
    rows: list[SearchIndex],
    query_text: str,
    query_vec: list[float] | None,
    folder_id_set: set[str],
    limit: int,
    *,
    score_lookup: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Convert SearchIndex rows into PRD10 §11.4 context items with citations.

    For ``object_type=document`` rows we run a 2nd-pass cosine over their
    ``kb_chunks`` to pick the most-relevant paragraph for the LLM prompt
    AND the citation chip displayed in the v1.4 GPT-style chat bubble.
    """

    if not rows:
        return []

    doc_ids: list[uuid.UUID] = []
    for row in rows:
        if row.item_type == "document":
            try:
                doc_ids.append(
                    row.item_id
                    if isinstance(row.item_id, uuid.UUID)
                    else uuid.UUID(str(row.item_id))
                )
            except (TypeError, ValueError):
                continue

    chunk_map: dict[str, dict[str, Any]] = {}
    folder_lookup: dict[str, str] = {}
    if doc_ids and query_vec is not None:
        chunk_map = await _rerank_chunks_for_documents(
            db, doc_ids, query_vec, top_per_doc=1
        )

    if doc_ids:
        try:
            doc_rows = (
                await db.execute(
                    select(KBDocument).where(KBDocument.id.in_(doc_ids))
                )
            ).scalars().all()
        except SQLAlchemyError:
            doc_rows = []
        if doc_rows:
            folder_ids_to_lookup = [
                d.folder_id for d in doc_rows if d.folder_id is not None
            ]
            if folder_ids_to_lookup:
                try:
                    fld_rows = (
                        await db.execute(
                            select(KBFolder).where(KBFolder.id.in_(folder_ids_to_lookup))
                        )
                    ).scalars().all()
                    folder_lookup = {str(f.id): f.name or "" for f in fld_rows}
                except SQLAlchemyError:
                    folder_lookup = {}
            for d in doc_rows:
                key = str(d.id)
                chunk = chunk_map.get(key) or {}
                body = (d.content or d.summary or "").strip()
                if body:
                    chunk.setdefault("full_text", body[:4000])
                if d.folder_id is not None:
                    chunk.setdefault("folder_id", str(d.folder_id))
                    chunk.setdefault(
                        "folder_name",
                        folder_lookup.get(str(d.folder_id), ""),
                    )
                chunk.setdefault("anchor_url", f"/mydow/biz_v14/#kb/doc/{key}")
                chunk_map[key] = chunk

    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        item = _context_item(row, query=query_text)
        item["score"] = float(
            (score_lookup or {}).get(str(row.item_id), item.get("score", 0.0))
        )
        chunk = chunk_map.get(str(row.item_id)) or {}
        if chunk:
            chunk_content = (chunk.get("content") or "").strip()
            if chunk_content:
                item["snippet"] = _highlight_snippet(chunk_content, query_text)
            for k in ("chunk_id", "folder_id", "folder_name", "anchor_url", "full_text"):
                v = chunk.get(k)
                if v:
                    item[k] = v
            chunk_score = chunk.get("score")
            if isinstance(chunk_score, (int, float)) and chunk_score > 0:
                item["score"] = round(
                    max(float(item["score"]), float(chunk_score)), 4
                )
        elif query_text:
            item["snippet"] = _highlight_snippet(item.get("snippet", ""), query_text)

        if folder_id_set and row.search_metadata:
            meta_str = json.dumps(row.search_metadata, ensure_ascii=False)
            for fid in folder_id_set:
                if fid in meta_str:
                    item["score"] = round(item["score"] + 0.5, 4)
                    break
        items.append(item)

    items.sort(key=lambda i: float(i.get("score") or 0), reverse=True)
    return items[:limit]


async def _load_related_context(
    db: AsyncSession,
    user: User,
    context_scope: dict[str, Any] | None,
    *,
    query: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """PRD10 §15.43 — embedding-driven RAG retrieval with chunk re-rank.

    Strategy:

    1. ``context_scope.document_ids`` → honour the explicit drawer pin.
    2. ``context_scope.folder_ids`` → narrow to those folders, still rank.
    3. Default path → embed the user query, cosine-rank a wide window of
       SearchIndex rows, then re-rank document hits at chunk level so the
       system prompt sees the actual matching paragraph.
    4. Recent-rows fallback when the query is empty (sidebar greeting).

    Missing tables / legacy embeddings are tolerated; the previous keyword
    LIKE behaviour acts as the safety net.
    """

    scope = context_scope or {}
    include_recent = bool(scope.get("include_recent", True))
    document_ids = _uuid_values(scope.get("document_ids"))
    folder_ids = [str(v) for v in scope.get("folder_ids") or [] if v]
    folder_id_set = set(folder_ids)
    query_text = (query or "").strip()
    query_tokens = [t for t in tokenize(query_text) if len(t) >= 2]
    query_vec: list[float] | None = None
    if query_tokens:
        query_vec = embed_text(query_text, dimension=EMBEDDING_DIMENSION)

    # ── Path 1 — explicit document pin (drawer "use these docs only") ────
    if document_ids:
        try:
            rows = (
                await db.execute(
                    select(SearchIndex)
                    .where(
                        or_(
                            SearchIndex.user_id == user.id,
                            SearchIndex.user_id.is_(None),
                        ),
                        SearchIndex.item_type == "document",
                        SearchIndex.item_id.in_(document_ids),
                    )
                    .order_by(SearchIndex.updated_at.desc().nulls_last())
                    .limit(limit * 2)
                )
            ).scalars().all()
        except SQLAlchemyError:
            return []
        if rows:
            return await _enrich_with_chunks_and_folder(
                db, rows, query_text, query_vec, folder_id_set, limit
            )
        try:
            folder_uuid_values = _uuid_values(folder_ids)
            if folder_uuid_values:
                docs = (
                    await db.execute(
                        select(KBDocument)
                        .where(
                            KBDocument.user_id == user.id,
                            KBDocument.deleted_at.is_(None),
                            KBDocument.folder_id.in_(folder_uuid_values),
                        )
                        .order_by(KBDocument.updated_at.desc().nulls_last())
                        .limit(max(limit * 2, 10))
                    )
                ).scalars().all()
            else:
                docs = []
            if docs:
                folder_rows = (
                    await db.execute(
                        select(KBFolder).where(KBFolder.id.in_(folder_uuid_values))
                    )
                ).scalars().all()
                folder_name_by_id = {str(f.id): f.name for f in folder_rows}
                return [
                    _doc_context_item(
                        doc,
                        query=query_text,
                        score=1.0 - (idx * 0.01),
                        folder_name=folder_name_by_id.get(str(doc.folder_id)),
                    )
                    for idx, doc in enumerate(docs[:limit])
                ]
        except SQLAlchemyError:
            return []

    # ── Path 2 — folder pin ────────────────────────────────────────────
    if folder_ids:
        try:
            folder_uuid_values = _uuid_values(folder_ids)
            if folder_uuid_values:
                docs = (
                    await db.execute(
                        select(KBDocument)
                        .where(
                            KBDocument.user_id == user.id,
                            KBDocument.deleted_at.is_(None),
                            KBDocument.folder_id.in_(folder_uuid_values),
                        )
                        .order_by(KBDocument.updated_at.desc().nulls_last())
                        .limit(max(limit * 2, 10))
                    )
                ).scalars().all()
                if docs:
                    folder_rows = (
                        await db.execute(
                            select(KBFolder).where(KBFolder.id.in_(folder_uuid_values))
                        )
                    ).scalars().all()
                    folder_name_by_id = {str(f.id): f.name for f in folder_rows}
                    return [
                        _doc_context_item(
                            doc,
                            query=query_text,
                            score=1.0 - (idx * 0.01),
                            folder_name=folder_name_by_id.get(str(doc.folder_id)),
                        )
                        for idx, doc in enumerate(docs[:limit])
                    ]
            folder_clause = or_(
                *[
                    cast(SearchIndex.search_metadata, String).ilike(f"%{fid}%")
                    for fid in folder_ids
                ]
            )
            rows = (
                await db.execute(
                    select(SearchIndex)
                    .where(
                        or_(
                            SearchIndex.user_id == user.id,
                            SearchIndex.user_id.is_(None),
                        )
                    )
                    .where(folder_clause)
                    .order_by(SearchIndex.updated_at.desc().nulls_last())
                    .limit(limit * 4)
                )
            ).scalars().all()
        except SQLAlchemyError:
            return []
        if rows:
            return await _enrich_with_chunks_and_folder(
                db, rows, query_text, query_vec, folder_id_set, limit
            )

    # ── Path 3 — semantic query (default RAG path) ─────────────────────
    # Hybrid retrieval: union of SearchIndex (cards / messages / inbox) and
    # KB Documents (real corpus), each scored by cosine similarity against
    # the query embedding. Documents bring the full body text into play so
    # RAG works even when SearchIndex is partially populated. Folder names
    # are joined so the citation chip shows "产品设计 / Mydow 落地页…" to
    # the user.
    if query_text and query_vec is not None:
        # 3a — SearchIndex candidates (existing path).
        try:
            candidates = (
                await db.execute(
                    select(SearchIndex)
                    .where(
                        or_(
                            SearchIndex.user_id == user.id,
                            SearchIndex.user_id.is_(None),
                        )
                    )
                    .order_by(SearchIndex.updated_at.desc().nulls_last())
                    .limit(max(limit * 10, 60))
                )
            ).scalars().all()
        except SQLAlchemyError:
            candidates = []
        idx_scored: list[tuple[float, SearchIndex]] = []
        query_lower = query_text.lower()
        for row in candidates:
            emb = _safe_embedding_vector(row.embedding)
            if emb is None or len(emb) != len(query_vec):
                emb = embed_text(
                    text_for_search_embedding(row.title, row.summary, row.content),
                    dimension=len(query_vec),
                )
            score = cosine_similarity(query_vec, emb)
            blob = " ".join(
                [str(row.title or ""), str(row.summary or ""), str(row.content or "")]
            ).lower()
            if query_lower and query_lower in blob:
                score += 0.05
            if score > 0:
                idx_scored.append((score, row))

        # 3b — KB Documents direct candidates (covers the part of corpus
        # that SearchIndex hasn't been populated with yet).
        kb_scored: list[tuple[float, KBDocument]] = []
        try:
            kb_docs = (
                await db.execute(
                    select(KBDocument)
                    .where(
                        KBDocument.user_id == user.id,
                        KBDocument.deleted_at.is_(None),
                    )
                    .order_by(KBDocument.updated_at.desc().nulls_last())
                    .limit(max(limit * 8, 40))
                )
            ).scalars().all()
        except SQLAlchemyError:
            kb_docs = []
        for d in kb_docs:
            text = text_for_search_embedding(d.title, d.summary, d.content)
            score = cosine_similarity(query_vec, embed_text(text, dimension=len(query_vec)))
            blob = " ".join(
                filter(None, [d.title or "", d.summary or "", d.content or ""])
            ).lower()
            if query_lower and query_lower in blob:
                score += 0.12  # weight literal hits higher to surface explicit topic mentions
            if score > 0:
                kb_scored.append((score, d))

        # Merge + dedup by (object_type, object_id), keeping the higher score.
        merged: dict[str, tuple[float, str, Any]] = {}
        for score, row in idx_scored:
            key = f"{row.item_type or 'document'}:{row.item_id}"
            cur = merged.get(key)
            if cur is None or score > cur[0]:
                merged[key] = (score, "search_index", row)
        for score, doc in kb_scored:
            key = f"document:{doc.id}"
            cur = merged.get(key)
            if cur is None or score > cur[0]:
                merged[key] = (score, "kb_document", doc)

        if merged:
            ranked = sorted(merged.values(), key=lambda t: t[0], reverse=True)[:limit]
            # Normalise both branches into the SearchIndex-shaped enrichment
            # for path 3a, plus a parallel doc-shaped list for path 3b.
            si_rows: list[SearchIndex] = []
            si_score_lookup: dict[str, float] = {}
            doc_only_items: list[dict[str, Any]] = []
            try:
                folder_rows = (
                    await db.execute(
                        select(KBFolder).where(KBFolder.user_id == user.id)
                    )
                ).scalars().all()
                folder_name_by_id = {str(f.id): f.name for f in folder_rows}
            except SQLAlchemyError:
                folder_name_by_id = {}

            for score, source, obj in ranked:
                if source == "search_index":
                    si_rows.append(obj)
                    si_score_lookup[str(obj.item_id)] = score
                else:  # kb_document
                    folder_name = (
                        folder_name_by_id.get(str(obj.folder_id))
                        if obj.folder_id else None
                    )
                    doc_only_items.append(
                        _doc_context_item(
                            obj,
                            query=query_text,
                            score=score,
                            folder_name=folder_name,
                        )
                    )

            enriched: list[dict[str, Any]] = []
            if si_rows:
                enriched.extend(
                    await _enrich_with_chunks_and_folder(
                        db,
                        si_rows,
                        query_text,
                        query_vec,
                        folder_id_set,
                        limit,
                        score_lookup=si_score_lookup,
                    )
                )
            enriched.extend(doc_only_items)
            # Re-sort merged enriched list by score.
            enriched.sort(key=lambda i: float(i.get("score") or 0), reverse=True)
            return enriched[:limit]

    # ── Path 4 — recent-rows fallback ──────────────────────────────────
    if not include_recent:
        return []
    try:
        rows = (
            await db.execute(
                select(SearchIndex)
                .where(
                    or_(
                        SearchIndex.user_id == user.id,
                        SearchIndex.user_id.is_(None),
                    )
                )
                .order_by(SearchIndex.updated_at.desc().nulls_last())
                .limit(limit)
            )
        ).scalars().all()
    except SQLAlchemyError:
        return []
    return await _enrich_with_chunks_and_folder(
        db, rows, query_text, query_vec, folder_id_set, limit
    )


# ---------------------------------------------------------------------------
# Conversation list / create / detail
# ---------------------------------------------------------------------------


@router.get("/conversations")
async def list_conversations(
    request: Request,
    keyword: str = Query("", description="Optional title filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.1."""

    base = select(AIConversation).where(
        AIConversation.user_id == current_user.id,
        AIConversation.deleted_at.is_(None),
    )

    keyword = (keyword or "").strip()
    if keyword:
        base = base.where(AIConversation.title.ilike(f"%{keyword}%"))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0

    rows_stmt = (
        base.order_by(AIConversation.updated_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await db.execute(rows_stmt)).scalars().all()

    items = [conv.to_prd10_dict() for conv in rows]
    return paginated_response(
        items,
        page=page,
        page_size=page_size,
        total=int(total),
        request=request,
    )


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.2."""

    mode = (payload.mode or AIConversationMode.GENERAL.value).strip()
    if mode not in _VALID_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"Invalid mode '{mode}'. Allowed: {', '.join(_VALID_MODES)}",
            },
        )

    conv = AIConversation(
        user_id=current_user.id,
        title=(payload.title or "新的对话").strip() or "新的对话",
        mode=mode,
        context_scope=payload.context_scope or {},
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return success_response(conv.to_prd10_dict(), request=request)


@router.get("/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.3."""

    cid = _parse_uuid(conversation_id, "conversation_id")
    conv = await _load_owned_conversation(db, cid, current_user)

    msg_stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conv.id)
        .order_by(AIMessage.created_at.asc())
    )
    messages = (await db.execute(msg_stmt)).scalars().all()

    related_context = await _load_related_context(
        db,
        current_user,
        conv.context_scope,
        limit=5,
    )

    data = {
        "conversation": conv.to_prd10_dict(),
        "messages": [m.to_prd10_dict() for m in messages],
        "related_context": related_context,
        "suggested_followups": [],
    }
    return success_response(data, request=request)


# ---------------------------------------------------------------------------
# Send message (synchronous placeholder assistant reply for MVP)
# ---------------------------------------------------------------------------


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    conversation_id: str,
    payload: MessageSend,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.4 (non-streaming MVP path)."""

    cid = _parse_uuid(conversation_id, "conversation_id")
    conv = await _load_owned_conversation(db, cid, current_user)

    # Persist the user message.
    user_msg = AIMessage(
        conversation_id=conv.id,
        user_id=current_user.id,
        role=AIMessageRole.USER.value,
        content=payload.content,
        status=AIMessageStatus.COMPLETED.value,
        attachments=payload.attachments,
    )
    db.add(user_msg)
    await db.flush()

    context_scope = payload.context_scope or conv.context_scope or {}
    related_context = await _load_related_context(
        db,
        current_user,
        context_scope,
        query=payload.content,
        limit=5,
    )

    # Queue an ai_chat job so the contract for "long-running operation"
    # is satisfied even though we reply synchronously below.
    job = Job(
        user_id=current_user.id,
        job_type=JobType.AI_CHAT.value,
        status=JobStatus.COMPLETED.value,
        progress=100,
        input={
            "conversation_id": str(conv.id),
            "user_message_id": str(user_msg.id),
            "context_scope": context_scope,
            "related_context": related_context,
        },
    )
    db.add(job)
    await db.flush()

    # Try the real LLM when enabled, otherwise keep the deterministic
    # placeholder. Persistence shape stays the same in both branches.
    assistant_content = _PLACEHOLDER_REPLY
    assistant_model = "placeholder"
    input_tokens = 0
    output_tokens = len(_PLACEHOLDER_REPLY)
    latency_ms = 0
    error_payload: dict[str, Any] | None = None

    if is_llm_enabled():
        history_stmt = (
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id)
            .where(AIMessage.id != user_msg.id)
            .order_by(AIMessage.created_at.asc())
        )
        history = (await db.execute(history_stmt)).scalars().all()
        chat_messages = _build_chat_messages(
            conv, list(history), payload.content, related_context
        )

        started = time.perf_counter()
        content, usage, error = await _invoke_llm_complete(chat_messages)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if error:
            error_payload = {
                "code": "AI_PROVIDER_ERROR",
                "message": error,
            }
            assistant_content = (
                "AI 调用失败，请检查 LLM API 配置或稍后重试："
                + str(error)
            )
            assistant_model = "litellm"
            output_tokens = 0
            latency_ms = elapsed_ms
            job.status = JobStatus.FAILED.value
            job.error = error_payload
        else:
            assistant_content = content
            assistant_model = "litellm"
            latency_ms = elapsed_ms
            if usage:
                input_tokens = int(usage.get("prompt_tokens") or 0)
                output_tokens = int(usage.get("completion_tokens") or 0)
            else:
                output_tokens = len(assistant_content)

    assistant_msg = AIMessage(
        conversation_id=conv.id,
        user_id=current_user.id,
        role=AIMessageRole.ASSISTANT.value,
        content=assistant_content,
        status=(
            AIMessageStatus.FAILED.value
            if error_payload
            else AIMessageStatus.COMPLETED.value
        ),
        citations=[_citation_from_context(item) for item in related_context],
        tool_calls=[],
        parent_message_id=user_msg.id,
        job_id=job.id,
        model=assistant_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        error=error_payload,
    )
    db.add(assistant_msg)

    # Update conversation rollup fields.
    conv.message_count = int(conv.message_count or 0) + 2
    conv.last_message_preview = assistant_content[:120]

    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    await db.refresh(job)
    await db.refresh(conv)

    return success_response(
        {
            "user_message": user_msg.to_prd10_dict(),
            "assistant_message": assistant_msg.to_prd10_dict(),
            "job": job.to_prd10_dict(),
            "conversation": conv.to_prd10_dict(),
            "related_context": related_context,
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# Streaming message endpoint (PRD10 §11.4)
# ---------------------------------------------------------------------------


def _sse_event(event: str, data: dict[str, Any], *, prefix: str = "") -> bytes:
    """Encode a Server-Sent Event frame.

    ``prefix`` (rare) lets the caller prepend extra non-event fields like
    the SSE ``retry:`` hint inside the same blank-line-separated block,
    so naive testbench parsers (which split on blank lines) keep emitting
    the expected ``event_types[0] == "meta"`` ordering.
    """

    payload = json.dumps(data, ensure_ascii=False)
    return (prefix + f"event: {event}\ndata: {payload}\n\n").encode("utf-8")


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    status_code=status.HTTP_200_OK,
)
async def post_message_stream(
    conversation_id: str,
    payload: MessageSend,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """PRD10 §11.4 streaming variant.

    Persists the user message + placeholder assistant message immediately,
    then streams assistant tokens as Server-Sent Events. The final ``done``
    event carries the assistant message id so the frontend can correlate.
    """

    cid = _parse_uuid(conversation_id, "conversation_id")
    conv = await _load_owned_conversation(db, cid, current_user)

    # §15.49 — derive the runtime mode. v1.4 sends "omni" (全能模式) /
    # "efficient" (高效模式); we also accept "all" / "agent" for forward
    # compat. Anything matching the agent set activates the multi-step
    # ReAct path with progress events; otherwise we run the single-shot
    # RAG path.
    request_mode = (payload.mode or "").strip().lower() or (conv.mode or "").lower()
    is_agent_mode = request_mode in {"omni", "all", "agent"}

    user_msg = AIMessage(
        conversation_id=conv.id,
        user_id=current_user.id,
        role=AIMessageRole.USER.value,
        content=payload.content,
        status=AIMessageStatus.COMPLETED.value,
        attachments=payload.attachments,
    )
    db.add(user_msg)
    await db.flush()

    context_scope = payload.context_scope or conv.context_scope or {}
    related_context = await _load_related_context(
        db,
        current_user,
        context_scope,
        query=payload.content,
        limit=8 if is_agent_mode else 5,
    )

    # §15.49 — for agent mode, also do a second-pass query decomposition so
    # we surface evidence the user didn't literally mention. We cap to two
    # extra sub-queries to keep latency down (each is a cosine pass over
    # the existing SearchIndex window).
    if is_agent_mode:
        for sub_q in _agent_subqueries(payload.content):
            extra = await _load_related_context(
                db,
                current_user,
                {"include_recent": True},  # ignore folder pin during expansion
                query=sub_q,
                limit=3,
            )
            for item in extra:
                if not any(
                    e.get("object_id") == item.get("object_id") for e in related_context
                ):
                    related_context.append(item)
        related_context = related_context[:10]

    job = Job(
        user_id=current_user.id,
        job_type=JobType.AI_CHAT.value,
        status=JobStatus.RUNNING.value,
        progress=10,
        input={
            "conversation_id": str(conv.id),
            "user_message_id": str(user_msg.id),
            "stream": True,
            "context_scope": context_scope,
        },
    )
    db.add(job)
    await db.flush()

    assistant_msg = AIMessage(
        conversation_id=conv.id,
        user_id=current_user.id,
        role=AIMessageRole.ASSISTANT.value,
        content="",
        status=AIMessageStatus.RUNNING.value,
        citations=[_citation_from_context(item) for item in related_context],
        tool_calls=[],
        parent_message_id=user_msg.id,
        job_id=job.id,
        model="litellm" if is_llm_enabled() else "placeholder",
    )
    db.add(assistant_msg)
    conv.message_count = int(conv.message_count or 0) + 2
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    await db.refresh(job)

    history_stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conv.id)
        .where(AIMessage.id.notin_([user_msg.id, assistant_msg.id]))
        .order_by(AIMessage.created_at.asc())
    )
    history = (await db.execute(history_stmt)).scalars().all()
    history_for_react = [
        {"role": str(m.role), "content": (m.content or "").strip()}
        for m in history
        if str(m.role) in (AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value)
        and (m.content or "").strip()
    ]
    chat_messages = _build_chat_messages(
        conv, list(history), payload.content, related_context
    )

    assistant_id = assistant_msg.id
    job_id = job.id
    use_llm = is_llm_enabled()

    async def _generate() -> AsyncIterator[bytes]:
        from agent_os.db.base import get_sessionmaker

        # The very first frame carries ``retry: 5000`` so the EventSource
        # client knows to auto-reconnect after 5s if the TCP connection
        # drops. Wrapping it inside the same block as ``event: meta`` keeps
        # naive blank-line SSE parsers (used in tests) consistent.
        yield _sse_event(
            "meta",
            {
                "user_message_id": str(user_msg.id),
                "assistant_message_id": str(assistant_id),
                "job_id": str(job_id),
                "heartbeat_seconds": _heartbeat_seconds(),
                "mode": "agent" if is_agent_mode else "chat",
                "agent_enabled": is_agent_mode,
            },
            prefix=_SSE_RETRY_HINT,
        )

        # §15.49 — Agent mode UX: replay pre-RAG retrieval; omit the synthetic
        # 「综合答案」chip here when LiteLLM ReAct is enabled — that chip is
        # emitted immediately before streaming ``final_answer`` tokens instead.
        if is_agent_mode:
            yield _sse_event(
                "agent_step",
                {
                    "step": 1,
                    "kind": "plan",
                    "title": "拆解问题",
                    "detail": (
                        f"识别到 {len(_agent_subqueries(payload.content))} 个子主题，"
                        "将逐一在你的知识库 / 数字花园中检索"
                    ),
                },
            )
            await asyncio.sleep(0.05)
            yield _sse_event(
                "agent_step",
                {
                    "step": 2,
                    "kind": "retrieve",
                    "title": "知识库检索",
                    "detail": f"已找到 {len(related_context)} 段相关上下文",
                    "context_count": len(related_context),
                    "top_titles": [
                        c.get("title") for c in related_context[:3] if c.get("title")
                    ],
                },
            )
            await asyncio.sleep(0.05)
            if not use_llm:
                yield _sse_event(
                    "agent_step",
                    {
                        "step": 3,
                        "kind": "synthesize",
                        "title": "综合答案",
                        "detail": "正在调用大模型，结合上下文生成回答…",
                    },
                )

        accumulated: list[str] = []
        started = time.perf_counter()
        error_payload: dict[str, Any] | None = None
        heartbeat_count = 0
        heartbeat_seconds = _heartbeat_seconds()
        react_tool_calls: list[dict[str, Any]] = []
        react_citations: list[dict[str, Any]] | None = None
        try:
            if is_agent_mode and use_llm:
                async with get_sessionmaker()() as agent_sess:
                    db_user = await agent_sess.get(User, current_user.id)
                    if db_user is None:
                        raise RuntimeError("User not found for ReAct agent")

                    async for react_evt in run_react_agent(
                        db=agent_sess,
                        user=db_user,
                        user_message=payload.content,
                        history=history_for_react,
                        prefetched_context=related_context,
                    ):
                        ev = react_evt["event"]
                        data = react_evt.get("data") or {}
                        if ev == "thought":
                            yield _sse_event(
                                "agent_step",
                                {
                                    "step": int(data.get("iteration") or 1),
                                    "kind": "plan",
                                    "title": "推理",
                                    "detail": (data.get("text") or "")[:500],
                                },
                            )
                        elif ev == "tool_call":
                            react_tool_calls.append(
                                {"name": data.get("name"), "args": data.get("args")}
                            )
                            yield _sse_event(
                                "agent_step",
                                {
                                    "step": int(data.get("iteration") or 1),
                                    "kind": "tool",
                                    "title": f"调用 {data.get('name')}",
                                    "detail": json.dumps(
                                        data.get("args") or {},
                                        ensure_ascii=False,
                                    )[:260],
                                },
                            )
                        elif ev == "tool_result":
                            yield _sse_event(
                                "agent_step",
                                {
                                    "step": int(data.get("iteration") or 1),
                                    "kind": "retrieve",
                                    "title": f"{data.get('name')} 完成",
                                    "detail": "已读取工具输出，继续推理…",
                                },
                            )
                        elif ev == "error":
                            error_payload = {
                                "code": "AI_PROVIDER_ERROR",
                                "message": str(data.get("message") or ""),
                            }
                            yield _sse_event("error", error_payload)
                        elif ev == "final_answer":
                            yield _sse_event(
                                "agent_step",
                                {
                                    "step": int(data.get("iteration") or 4),
                                    "kind": "synthesize",
                                    "title": "综合答案",
                                    "detail": "正在输出最终答复…",
                                },
                            )
                            ans = data.get("answer") or ""
                            raw_cites = data.get("citations")
                            if isinstance(raw_cites, list) and raw_cites:
                                react_citations = [
                                    _citation_from_context(
                                        _normalize_agent_citation_item(c)
                                    )
                                    for c in raw_cites
                                    if isinstance(c, dict)
                                ]
                            chunk_size = max(24, len(ans) // 80 or 24)
                            for i in range(0, len(ans), chunk_size):
                                piece = ans[i : i + chunk_size]
                                accumulated.append(piece)
                                yield _sse_event("token", {"delta": piece})

            elif use_llm:
                provider = get_provider()
                upstream = provider.stream_complete(chat_messages)
                async for chunk in _wrap_with_heartbeat(
                    upstream, heartbeat_seconds
                ):
                    if chunk is _HEARTBEAT_SENTINEL:
                        heartbeat_count += 1
                        yield _sse_event(
                            "keepalive",
                            {
                                "ts": time.time(),
                                "elapsed_ms": int(
                                    (time.perf_counter() - started) * 1000
                                ),
                                "count": heartbeat_count,
                            },
                        )
                        continue
                    delta = (chunk or {}).get("content") or ""
                    if not delta:
                        continue
                    accumulated.append(delta)
                    yield _sse_event("token", {"delta": delta})
            else:
                # Deterministic offline stream so frontend SSE wiring stays
                # testable without network access.
                for piece in (
                    "（占位流式回答）",
                    "已收到你的请求；",
                    "当前处于 PRD10 V1，",
                    f"接入 LLM 后将替换此回答。原始问题: {payload.content[:80]}",
                ):
                    accumulated.append(piece)
                    yield _sse_event("token", {"delta": piece})
        except Exception as exc:  # pragma: no cover - defensive
            error_payload = {
                "code": "AI_PROVIDER_ERROR",
                "message": _format_llm_provider_error(exc),
            }
            yield _sse_event("error", error_payload)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        final_content = "".join(accumulated)
        if not final_content:
            if error_payload:
                final_content = (
                    "AI 调用失败，请检查 LLM API 配置或稍后重试："
                    + str(error_payload.get("message") or "")
                )
            else:
                final_content = _PLACEHOLDER_REPLY
        sanitized_final_content = _sanitize_assistant_content(final_content)
        if sanitized_final_content != final_content:
            final_content = sanitized_final_content
            yield _sse_event("replace", {"content": final_content})

        citation_items = react_citations
        if citation_items is None:
            citation_items = [
                _citation_from_context(item) for item in related_context
            ]

        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            db_msg = await session.get(AIMessage, assistant_id)
            if db_msg is not None:
                db_msg.content = final_content
                db_msg.status = (
                    AIMessageStatus.FAILED.value
                    if error_payload
                    else AIMessageStatus.COMPLETED.value
                )
                db_msg.output_tokens = len(final_content)
                db_msg.latency_ms = elapsed_ms
                db_msg.citations = list(citation_items)
                if react_tool_calls:
                    db_msg.tool_calls = react_tool_calls
                if error_payload:
                    db_msg.error = error_payload

            db_job = await session.get(Job, job_id)
            if db_job is not None:
                db_job.status = (
                    JobStatus.FAILED.value
                    if error_payload
                    else JobStatus.COMPLETED.value
                )
                db_job.progress = 100
                if error_payload:
                    db_job.error = error_payload

            db_conv = await session.get(AIConversation, cid)
            if db_conv is not None:
                db_conv.last_message_preview = final_content[:120]

            await session.commit()

        yield _sse_event(
            "done",
            {
                "assistant_message_id": str(assistant_id),
                "job_id": str(job_id),
                "status": "failed" if error_payload else "completed",
                "latency_ms": elapsed_ms,
                # PRD10 §15.43 — emit citations so the FE renders source chips
                # without needing a follow-up GET. Frontend consumes
                # `payload.citations` in `streamV14AiReply` done branch.
                "citations": list(citation_items),
            },
        )

    # PRD10 §12.4 SSE hardening:
    # - ``Cache-Control: no-store`` and ``Connection: keep-alive`` keep proxies
    #   from buffering or recycling the response.
    # - ``X-Accel-Buffering: no`` opts the response out of nginx's
    #   default response buffering so token frames flush byte-for-byte.
    # - The heartbeat events emitted inside ``_generate`` (and the
    #   ``retry: 5000`` hint folded into the first SSE block) protect
    #   long-running LLM calls from idle disconnects on Cloudflare /
    #   nginx / Windows uvicorn, and let the EventSource client
    #   auto-reconnect on transient network drops.
    headers = {
        "Cache-Control": "no-store",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Cancel / regenerate / fetch an assistant message (PRD10 §11.5 / §11.6 / §16)
# ---------------------------------------------------------------------------


@router.get("/messages/{message_id}")
async def get_message(
    message_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """§16 — fetch a single AI message by id (used by FE to read citations).

    Citations carry the chunk title / snippet / object id from the §16 RAG
    retrieval. Frontend renders them as clickable chips below the assistant
    bubble so the user can drill back into the source document.
    """

    mid = _parse_uuid(message_id, "message_id")
    stmt = select(AIMessage).where(
        AIMessage.id == mid,
        AIMessage.user_id == current_user.id,
    )
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Message not found"},
        )
    return success_response(msg.to_prd10_dict(), request=request)


@router.post("/messages/{message_id}/cancel")
async def cancel_message(
    message_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.5 ``POST /api/v1/ai/messages/{id}/cancel``.

    Marks an in-flight assistant message as ``canceled`` and bubbles the
    cancellation onto its linked ``ai_chat`` job. Already-completed messages
    are returned unchanged so the call is idempotent. The PRD10 envelope
    carries the updated message + job state so the FE can update the UI
    without a follow-up roundtrip.
    """

    mid = _parse_uuid(message_id, "message_id")
    msg = await _load_owned_assistant_message(db, mid, current_user)

    job_obj: Job | None = None
    if msg.job_id is not None:
        job_obj = (
            await db.execute(select(Job).where(Job.id == msg.job_id))
        ).scalar_one_or_none()

    cancellable = (
        AIMessageStatus.PENDING.value,
        AIMessageStatus.RUNNING.value,
    )
    cancelled = False
    if msg.status in cancellable:
        msg.status = AIMessageStatus.CANCELED.value
        msg.completed_at = datetime.now(UTC)
        cancelled = True
    if job_obj is not None and job_obj.status in (
        JobStatus.QUEUED.value,
        JobStatus.RUNNING.value,
    ):
        job_obj.status = JobStatus.CANCELED.value
        job_obj.completed_at = datetime.now(UTC)
        cancelled = True

    if cancelled:
        await db.commit()
        await db.refresh(msg)
        if job_obj is not None:
            await db.refresh(job_obj)

    return success_response(
        {
            "message": msg.to_prd10_dict(),
            "job": job_obj.to_prd10_dict() if job_obj is not None else None,
            "cancelled": cancelled,
        },
        request=request,
    )


@router.post(
    "/messages/{message_id}/regenerate",
    status_code=status.HTTP_201_CREATED,
)
async def regenerate_message(
    message_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.6 ``POST /api/v1/ai/messages/{id}/regenerate``.

    Re-asks the assistant for the prompt that produced ``message_id`` and
    persists a brand-new assistant message. The previous assistant message
    is left intact so the FE can show a "version" picker if desired. The
    response shape mirrors ``POST .../messages``:

        { user_message, assistant_message, job, conversation }

    The user-prompt is identified as the immediate predecessor of the
    target assistant message in the same conversation, ordered by
    ``created_at``. If the predecessor cannot be found (e.g. because the
    target is the very first message), we fall back to the most recent
    user message in the conversation.
    """

    mid = _parse_uuid(message_id, "message_id")
    target_msg = await _load_owned_assistant_message(db, mid, current_user)

    conv = await _load_owned_conversation(
        db, target_msg.conversation_id, current_user
    )

    # Locate the user prompt that produced this assistant message.
    pred_stmt = (
        select(AIMessage)
        .where(
            AIMessage.conversation_id == conv.id,
            AIMessage.user_id == current_user.id,
            AIMessage.role == AIMessageRole.USER.value,
            AIMessage.created_at <= target_msg.created_at,
        )
        .order_by(AIMessage.created_at.desc())
        .limit(1)
    )
    user_msg = (await db.execute(pred_stmt)).scalar_one_or_none()
    if user_msg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": (
                    "Cannot regenerate: no preceding user message found "
                    "for this assistant reply."
                ),
            },
        )

    # Reuse the regular send-message reply flow shape: queue a Job and, when
    # LLM is enabled, generate a fresh answer instead of replaying any stored
    # assistant content.
    context_scope = conv.context_scope or {}
    related_context = await _load_related_context(
        db, current_user, context_scope, query=user_msg.content, limit=5
    )

    job = Job(
        user_id=current_user.id,
        job_type=JobType.AI_CHAT.value,
        status=JobStatus.COMPLETED.value,
        progress=100,
        input={
            "conversation_id": str(conv.id),
            "user_message_id": str(user_msg.id),
            "context_scope": context_scope,
            "related_context": related_context,
            "regenerate_of": str(target_msg.id),
        },
    )
    db.add(job)
    await db.flush()

    assistant_content = _PLACEHOLDER_REPLY
    assistant_model = "placeholder"
    input_tokens = 0
    output_tokens = len(_PLACEHOLDER_REPLY)
    latency_ms = 0
    error_payload: dict[str, Any] | None = None

    if is_llm_enabled():
        history_stmt = (
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id)
            .where(AIMessage.created_at < user_msg.created_at)
            .order_by(AIMessage.created_at.asc())
        )
        history = (await db.execute(history_stmt)).scalars().all()
        chat_messages = _build_chat_messages(
            conv, list(history), user_msg.content, related_context
        )
        started = time.perf_counter()
        content, usage, error = await _invoke_llm_complete(chat_messages)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        assistant_model = "litellm"
        latency_ms = elapsed_ms
        if error:
            error_payload = {
                "code": "AI_PROVIDER_ERROR",
                "message": error,
            }
            assistant_content = (
                "AI 调用失败，请检查 LLM API 配置或稍后重试："
                + str(error)
            )
            output_tokens = 0
            job.status = JobStatus.FAILED.value
            job.error = error_payload
        else:
            assistant_content = content
            if usage:
                input_tokens = int(usage.get("prompt_tokens") or 0)
                output_tokens = int(usage.get("completion_tokens") or 0)
            else:
                output_tokens = len(assistant_content)

    assistant_msg = AIMessage(
        conversation_id=conv.id,
        user_id=current_user.id,
        role=AIMessageRole.ASSISTANT.value,
        content=assistant_content,
        status=(
            AIMessageStatus.FAILED.value
            if error_payload
            else AIMessageStatus.COMPLETED.value
        ),
        citations=[
            _citation_from_context(item) for item in related_context
        ] if related_context else [],
        tool_calls=[],
        parent_message_id=user_msg.id,
        job_id=job.id,
        model=assistant_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        error=error_payload,
    )
    db.add(assistant_msg)

    conv.message_count = int(conv.message_count or 0) + 1
    conv.last_message_preview = assistant_content[:120]

    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)
    await db.refresh(job)
    await db.refresh(conv)

    return success_response(
        {
            "user_message": user_msg.to_prd10_dict(),
            "assistant_message": assistant_msg.to_prd10_dict(),
            "job": job.to_prd10_dict(),
            "conversation": conv.to_prd10_dict(),
            "regenerate_of": str(target_msg.id),
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# Save assistant output to KB document / tasks (Job-only MVP)
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/save-to-kb",
    status_code=status.HTTP_202_ACCEPTED,
)
async def save_message_to_kb(
    message_id: str,
    payload: SaveToKbRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.7.

    The actual ``kb_documents`` write lives in Agent 2's KB pipeline. This
    endpoint persists a queued ``Job`` so the contract is testable today,
    and the consumer worker can pick it up when Agent 2's table lands.
    """

    mid = _parse_uuid(message_id, "message_id")
    msg = await _load_owned_assistant_message(db, mid, current_user)

    # PRD10 §5.15 doesn't list ``save_to_kb`` as a job_type; we reuse
    # ``parse_file`` as the closest semantic ("turn raw text into a KB
    # document") and pass the source kind in ``input.kind`` so the worker
    # can distinguish AI-output from raw uploads.
    job = Job(
        user_id=current_user.id,
        job_type=JobType.PARSE_FILE.value,
        status=JobStatus.QUEUED.value,
        input={
            "kind": "ai_message_to_kb",
            "message_id": str(msg.id),
            "conversation_id": str(msg.conversation_id),
            "folder_id": payload.folder_id,
            "title": payload.title,
            "tags": payload.tags,
            "content": msg.content,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return success_response(
        {
            "job_id": str(job.id),
            "status": job.status,
            # echo the assistant message id so the FE can correlate without
            # a second round-trip.
            "message_id": str(msg.id),
        },
        request=request,
    )


@router.post(
    "/messages/{message_id}/create-tasks",
    status_code=status.HTTP_202_ACCEPTED,
)
async def save_message_as_tasks(
    message_id: str,
    payload: CreateTasksRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.8.

    Same MVP shape as ``save-to-kb`` — only the Job entry is persisted; the
    actual ``prd10_tasks`` rows are written by Agent 2's task pipeline.
    """

    mid = _parse_uuid(message_id, "message_id")
    msg = await _load_owned_assistant_message(db, mid, current_user)

    if not payload.tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "tasks must be a non-empty list",
            },
        )

    # ``generate_report`` is the closest-fitting PRD10 §5.15 job_type for
    # "structured artifacts derived from an assistant message". The worker
    # branches on ``input.kind``.
    job = Job(
        user_id=current_user.id,
        job_type=JobType.GENERATE_REPORT.value,
        status=JobStatus.QUEUED.value,
        input={
            "kind": "ai_message_to_tasks",
            "message_id": str(msg.id),
            "conversation_id": str(msg.conversation_id),
            "tasks": payload.tasks,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return success_response(
        {
            "job_id": str(job.id),
            "status": job.status,
            "message_id": str(msg.id),
            "task_count": len(payload.tasks),
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# v1.4 §7 user feedback on assistant message (赞 / 踩 / 文字)
# ---------------------------------------------------------------------------


@router.post(
    "/messages/{message_id}/feedback",
    status_code=status.HTTP_201_CREATED,
)
async def submit_message_feedback(
    message_id: str,
    payload: FeedbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 business-owner contract:

    - `data-toast="感谢反馈"` (赞)  → ``rating="up"``
    - `data-toast="已记录反馈"` (踩) → ``rating="down"``

    Persists to ``prd10_notifications`` so:
    1. The user can see their own feedback history in the notifications
       drawer (filtered by ``type="ai_feedback"``).
    2. Later analytics can aggregate by ``object_id`` (message_id) without
       a separate dedicated table.

    Idempotent on (user_id, message_id) — repeated submissions overwrite
    the prior content while keeping the notification id stable.
    """

    from agent_os.notifications.models import Notification

    mid = _parse_uuid(message_id, "message_id")
    msg = await _load_owned_assistant_message(db, mid, current_user)

    rating_label = "👍 点赞" if payload.rating == "up" else "👎 点踩"
    title = f"对回答的反馈 · {rating_label}"
    body_text = (payload.comment or "").strip()
    content_payload = json.dumps(
        {
            "rating": payload.rating,
            "comment": body_text or None,
            "message_id": str(msg.id),
            "conversation_id": str(msg.conversation_id),
            "submitted_at": datetime.now(UTC).isoformat(),
        },
        ensure_ascii=False,
    )

    # Idempotency: replace any prior feedback row for the same (user, msg).
    existing = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.type == "ai_feedback",
            Notification.object_type == "ai_message",
            Notification.object_id == str(msg.id),
        )
    )
    notif = existing.scalars().first()
    if notif is None:
        notif = Notification(
            user_id=current_user.id,
            type="ai_feedback",
            title=title,
            content=content_payload,
            object_type="ai_message",
            object_id=str(msg.id),
            is_read=True,  # silent: don't bump the unread badge
        )
        db.add(notif)
    else:
        notif.title = title
        notif.content = content_payload
        notif.is_read = True

    await db.commit()
    await db.refresh(notif)

    return success_response(
        {
            "feedback_id": str(notif.id),
            "rating": payload.rating,
            "comment": body_text or None,
            "message_id": str(msg.id),
            "submitted_at": notif.created_at.isoformat() if notif.created_at else None,
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# v1.4 §3.6 — PATCH / DELETE conversation (rename / change mode / soft-delete)
# ---------------------------------------------------------------------------


@router.patch("/conversations/{conversation_id}")
async def patch_conversation(
    conversation_id: str,
    payload: ConversationPatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.6 — rename / change mode / pin / scope a conversation.

    Wired for the v1.4 AI history three-dot menu (`重命名` / `删除` / 模式切换).
    Pinned state lives in the ``extra`` JSON field so we ship without a
    schema migration; the sidebar can sort by ``extra.pinned == true`` first.
    """

    cid = _parse_uuid(conversation_id, "conversation_id")
    conv = await _load_owned_conversation(db, cid, current_user)

    changed = False
    if payload.title is not None:
        new_title = payload.title.strip()
        if not new_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "VALIDATION_ERROR", "message": "title 不能为空"},
            )
        if new_title != conv.title:
            conv.title = new_title
            changed = True
    if payload.mode is not None:
        if payload.mode not in _VALID_MODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid mode '{payload.mode}'. Allowed: {', '.join(_VALID_MODES)}",
                },
            )
        if payload.mode != conv.mode:
            conv.mode = payload.mode
            changed = True
    if payload.context_scope is not None:
        conv.context_scope = payload.context_scope
        changed = True
    if payload.pinned is not None:
        extra = dict(conv.extra or {})
        if bool(extra.get("pinned")) != bool(payload.pinned):
            extra["pinned"] = bool(payload.pinned)
            conv.extra = extra
            changed = True

    if changed:
        conv.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(conv)

    out = conv.to_prd10_dict()
    out["pinned"] = bool((conv.extra or {}).get("pinned"))
    return success_response(out, request=request)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
async def delete_conversation(
    conversation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.6 — soft-delete a conversation (hidden from history list).

    Wired for the v1.4 AI sidebar three-dot menu `删除` action. Soft-delete
    keeps message history queryable for analytics / support; the sidebar
    filters by ``deleted_at IS NULL``.
    """

    cid = _parse_uuid(conversation_id, "conversation_id")
    conv = await _load_owned_conversation(db, cid, current_user)
    if conv.deleted_at is None:
        conv.deleted_at = datetime.now(UTC)
        await db.commit()
    return success_response({"id": str(conv.id), "deleted": True}, request=request)


# ---------------------------------------------------------------------------
# v1.4 §3.6 — GET /ai/models — model menu (DeepSeek v4 flash only)
# ---------------------------------------------------------------------------


# Static catalog. The selector remains visible, but all production AI/RAG/
# capture enrichment/Skills routing is pinned to DeepSeek v4 flash until
# the business explicitly re-opens multi-model routing.
_AI_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "deepseek-v4-flash",
        "label": "DeepSeek V4 Flash",
        "vendor": "DeepSeek",
        "tier": "fast",
        "default": True,
        "description": "统一用于 Mydow AI 对话、RAG、灵感采集与 Skills。",
    },
]


@router.get("/models")
async def list_ai_models(request: Request) -> dict:
    """v1.4 §3.6 — model selector menu data.

    Open to authenticated and demo callers; no plan-gating in V1.
    """

    return success_response(
        {
            "items": _AI_MODEL_CATALOG,
            "default": next(
                (m["id"] for m in _AI_MODEL_CATALOG if m.get("default")), "deepseek-v4-flash"
            ),
        },
        request=request,
    )
