"""§16.8 — Real ReAct Agent for Mydow AI 「全能模式」.

Implements a tool-calling loop powered by LiteLLM's OpenAI-compatible
function-calling API (open-source dependency, no extra runtime).  The
agent can search the user's KB, read documents, create cards, run
skills, and search the global feed.  Each iteration is streamed back
to the frontend as SSE events so users see "thought / tool / result"
chips before the final answer.

Tool set (intentionally small for V1 — extend by appending to
`AVAILABLE_TOOLS` + a handler in `_dispatch_tool`):

  - kb_search(query, top_k=5)         — semantic search across user's KB
  - read_document(document_id)        — fetch full content of a KB doc
  - global_search(query, top_k=10)    — full-text search across indexed surfaces (not live web)
  - create_card(title, summary, tags) — file a new idea card
  - run_skill(skill_name, instruction)— enqueue a Skill via the worker

Why not LangChain/LangGraph? Both are already in the image, but adopting
their orchestration pulls in their model wrappers and prompt templates.
LiteLLM's native tool-calling is leaner and matches the rest of the
codebase's coding style (the same provider is used everywhere else).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.ai.llm_provider import get_provider, is_llm_enabled
from agent_os.auth.models import User
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.kb.models import Document as KBDocument
from agent_os.kb.models import Folder as KBFolder
from agent_os.knowledge.models import Card
from agent_os.search_engine.embeddings import (
    cosine_similarity,
    embed_text,
    text_for_search_embedding,
)
from agent_os.search_engine.models import SearchIndex
from agent_os.skills.models import Skill

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAI tool schema — what the LLM sees
# ---------------------------------------------------------------------------


AVAILABLE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": (
                "Search the user's personal knowledge base (documents + cards) using "
                "semantic similarity. Use this whenever the user asks about THEIR data, "
                "concepts they captured, or to find supporting evidence for an answer. "
                "Returns a list of {title, snippet, folder, score, document_id}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to look for. Use the user's language.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results (1-10).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": (
                "Fetch the full content of a single KB document by id. Use this AFTER "
                "kb_search when you need the body text to summarise / quote / cite. "
                "Returns {id, title, folder, summary, content (truncated to 4000 chars)}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "global_search",
            "description": (
                "Full-text search across ALL user surfaces (cards / docs / messages / "
                "skills / insights). Returns {title, object_type, object_id, snippet}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_card",
            "description": (
                "Create a new idea card (capture) in the user's feed. "
                "Use when the user asks to record / note / capture something new."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Free-form tags (3-7 keywords).",
                    },
                },
                "required": ["title", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_skill",
            "description": (
                "Enqueue a Skill against the user's data and let the worker execute it "
                "asynchronously (LLM-backed). Use when the user asks for a structured "
                "action like '总结本周' / '生成周报' / '提取标签'. Returns the queued "
                "job_id; the actual output will land in KB."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name fragment of an existing skill (case-insensitive substring).",
                    },
                    "instruction": {
                        "type": "string",
                        "description": "Natural-language input for the skill.",
                    },
                },
                "required": ["skill_name", "instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": (
                "Send the FINAL natural-language answer to the user. Call exactly once "
                "when you've gathered enough info. Markdown is welcome; cite sources "
                "via [#1] / [#2] when you used kb_search results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "object_type": {"type": "string"},
                                "object_id": {"type": "string"},
                                "snippet": {"type": "string"},
                                "folder_name": {"type": "string"},
                                "anchor_url": {"type": "string"},
                            },
                            "required": ["title"],
                        },
                        "default": [],
                    },
                },
                "required": ["answer"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations — pure async handlers operating on the user's DB
# ---------------------------------------------------------------------------


async def _tool_kb_search(
    db: AsyncSession, user: User, *, query: str, top_k: int = 5
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"results": [], "note": "empty query"}
    top_k = max(1, min(int(top_k or 5), 10))
    qvec = embed_text(q)

    folder_map: dict[str, str] = {}
    try:
        folder_rows = (
            await db.execute(select(KBFolder).where(KBFolder.user_id == user.id))
        ).scalars().all()
        folder_map = {str(f.id): f.name for f in folder_rows}
    except Exception:
        pass

    # Pull a wide candidate window from kb_documents + SearchIndex.
    docs = (
        await db.execute(
            select(KBDocument)
            .where(KBDocument.user_id == user.id, KBDocument.deleted_at.is_(None))
            .order_by(KBDocument.updated_at.desc().nulls_last())
            .limit(40)
        )
    ).scalars().all()

    scored: list[tuple[float, dict[str, Any]]] = []
    qlow = q.lower()
    for d in docs:
        body = " ".join(filter(None, [d.title or "", d.summary or "", d.content or ""]))
        score = cosine_similarity(qvec, embed_text(body))
        if qlow and qlow in body.lower():
            score += 0.12
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "object_type": "document",
                    "object_id": str(d.id),
                    "document_id": str(d.id),
                    "title": d.title or "(无标题)",
                    "snippet": (d.summary or d.content or "")[:240],
                    "folder_name": folder_map.get(str(d.folder_id)) if d.folder_id else None,
                    "score": round(float(score), 4),
                    "anchor_url": f"/mydow/biz_v14/#kb/doc/{d.id}",
                },
            )
        )

    # Also scan SearchIndex (cards / messages / inbox).
    try:
        idx_rows = (
            await db.execute(
                select(SearchIndex)
                .where(
                    or_(SearchIndex.user_id == user.id, SearchIndex.user_id.is_(None))
                )
                .order_by(SearchIndex.updated_at.desc().nulls_last())
                .limit(60)
            )
        ).scalars().all()
        for row in idx_rows:
            vec = list(row.embedding or [])
            if vec:
                score = cosine_similarity(qvec, vec)
            else:
                text = text_for_search_embedding(row.title, row.summary, row.content)
                score = cosine_similarity(qvec, embed_text(text))
            blob = " ".join([str(row.title or ""), str(row.summary or ""), str(row.content or "")]).lower()
            if qlow and qlow in blob:
                score += 0.05
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "object_type": row.item_type,
                        "object_id": str(row.item_id),
                        "title": row.title or "",
                        "snippet": (row.summary or row.content or "")[:240],
                        "folder_name": None,
                        "score": round(float(score), 4),
                        "anchor_url": f"/mydow/biz_v14/#card/{row.item_id}"
                        if row.item_type == "card"
                        else None,
                    },
                )
            )
    except Exception:
        pass

    # Dedup by (object_type, object_id) keeping highest score.
    best: dict[str, tuple[float, dict[str, Any]]] = {}
    for score, item in scored:
        key = f"{item['object_type']}:{item['object_id']}"
        cur = best.get(key)
        if cur is None or score > cur[0]:
            best[key] = (score, item)
    ranked = sorted(best.values(), key=lambda t: t[0], reverse=True)[:top_k]
    return {"results": [it for _, it in ranked]}


async def _tool_read_document(
    db: AsyncSession, user: User, *, document_id: str
) -> dict[str, Any]:
    try:
        doc_id = uuid.UUID(str(document_id))
    except (TypeError, ValueError):
        return {"error": "invalid_id"}
    doc = (
        await db.execute(
            select(KBDocument).where(
                KBDocument.id == doc_id,
                KBDocument.user_id == user.id,
                KBDocument.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        return {"error": "not_found"}
    folder_name: str | None = None
    if doc.folder_id is not None:
        f = (
            await db.execute(
                select(KBFolder).where(KBFolder.id == doc.folder_id)
            )
        ).scalar_one_or_none()
        folder_name = f.name if f else None
    return {
        "id": str(doc.id),
        "title": doc.title,
        "folder_name": folder_name,
        "summary": doc.summary,
        "content": (doc.content or "")[:4000],
        "tags": list(doc.tags or []),
        "anchor_url": f"/mydow/biz_v14/#kb/doc/{doc.id}",
    }


async def _tool_global_search(
    db: AsyncSession, user: User, *, query: str, top_k: int = 10
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"results": []}
    top_k = max(1, min(int(top_k or 10), 20))
    like = f"%{q}%"
    rows = (
        await db.execute(
            select(SearchIndex)
            .where(
                or_(SearchIndex.user_id == user.id, SearchIndex.user_id.is_(None)),
                or_(
                    SearchIndex.title.ilike(like),
                    SearchIndex.summary.ilike(like),
                    SearchIndex.content.ilike(like),
                ),
            )
            .order_by(SearchIndex.updated_at.desc().nulls_last())
            .limit(top_k)
        )
    ).scalars().all()
    return {
        "results": [
            {
                "object_type": r.item_type,
                "object_id": str(r.item_id),
                "title": r.title,
                "snippet": (r.summary or r.content or "")[:200],
            }
            for r in rows
        ]
    }


async def _tool_create_card(
    db: AsyncSession,
    user: User,
    *,
    title: str,
    summary: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    title = (title or "").strip()[:255] or "未命名"
    summary = (summary or "").strip()[:1000]
    tags = [str(t).strip() for t in (tags or []) if t]
    card = Card(
        user_id=user.id,
        title=title,
        summary=summary,
        content=summary,
        tags=tags,
        content_type="note",
        # Card has fields like source_type / extra; defaults are fine.
        extra={"source": "agent_create_card", "created_by": "react_agent"},
    )
    db.add(card)
    await db.flush()
    await db.commit()
    return {
        "id": str(card.id),
        "title": title,
        "anchor_url": f"/mydow/biz_v14/#card/{card.id}",
    }


async def _tool_run_skill(
    db: AsyncSession,
    user: User,
    *,
    skill_name: str,
    instruction: str,
) -> dict[str, Any]:
    name_q = (skill_name or "").strip()
    if not name_q:
        return {"error": "skill_name_required"}
    skill = (
        await db.execute(
            select(Skill)
            .where(Skill.is_active.is_(True))
            .where(Skill.name.ilike(f"%{name_q}%"))
            .limit(1)
        )
    ).scalar_one_or_none()
    if skill is None:
        return {"error": "skill_not_found", "query": name_q}
    job = Job(
        user_id=user.id,
        job_type=JobType.SKILL_RUN.value,
        status=JobStatus.QUEUED.value,
        progress=0,
        input={
            "skill_id": str(skill.id),
            "skill_name": skill.name,
            "input": {
                "instruction": instruction or "",
                "text": instruction or "",
            },
            "save_output": True,
        },
    )
    db.add(job)
    await db.flush()
    await db.commit()
    return {
        "job_id": str(job.id),
        "skill_id": str(skill.id),
        "skill_name": skill.name,
        "status": "queued",
        "note": "Skill enqueued; worker will produce a KB document shortly.",
    }


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_tool(
    db: AsyncSession, user: User, name: str, args: dict[str, Any]
) -> dict[str, Any]:
    args = args or {}
    try:
        if name == "kb_search":
            return await _tool_kb_search(db, user, **args)
        if name == "read_document":
            return await _tool_read_document(db, user, **args)
        if name == "global_search":
            return await _tool_global_search(db, user, **args)
        if name == "create_card":
            return await _tool_create_card(db, user, **args)
        if name == "run_skill":
            return await _tool_run_skill(db, user, **args)
        return {"error": "unknown_tool", "name": name}
    except Exception as exc:  # noqa: BLE001 — surface to LLM as observation
        logger.exception("[react] tool %s failed", name)
        return {"error": "tool_exception", "tool": name, "message": str(exc)[:300]}


# ---------------------------------------------------------------------------
# Reactor loop with SSE streaming
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """你是 Mydow AI 全能模式 (ReAct Agent)。

你可以使用工具调用来：
1. 搜索用户的知识库 (kb_search) — 优先用这个；
2. 读取某个文档全文 (read_document)；
3. 全文检索 (global_search)；
4. 创建新卡片 (create_card)；
5. 运行 Skill 处理任务 (run_skill)；
6. 给出最终答案 (final_answer)。

工作流程：
- 首先 reasoning：用 1-2 句中文表达你打算怎么做（不要写 chain-of-thought 大段独白）。
- 如果需要数据，调用工具；不要凭空回答关于用户私人内容的问题。
- 用 final_answer 收尾，必要时携带 citations[]。

每轮你只能调用 1 个工具；最多 5 轮；如果工具返回的信息已足够，直接 final_answer。"""


async def run_react_agent(
    *,
    db: AsyncSession,
    user: User,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    max_iterations: int = 5,
    prefetched_context: list[dict[str, Any]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run the ReAct loop and yield SSE-shaped events.

    Yields events shaped as:
      {"event": "thought", "data": {...}}
      {"event": "tool_call", "data": {"name", "args"}}
      {"event": "tool_result", "data": {"name", "result"}}
      {"event": "final_answer", "data": {"answer", "citations"}}
      {"event": "error", "data": {"message"}}

    Always terminates within `max_iterations + 1` events for the answer.
    """

    history = list(history or [])

    if not is_llm_enabled():
        yield {
            "event": "final_answer",
            "data": {
                "answer": "（占位模式：AGENTOS_AI_LLM=off）启用真 LLM 后即可执行 ReAct 工具调用。",
                "citations": [],
            },
        }
        return

    provider = get_provider()
    prefetch_block = ""
    if prefetched_context:
        lines: list[str] = []
        for idx, it in enumerate(list(prefetched_context)[:10], start=1):
            title = str(it.get("title") or "")[:100]
            snip = str(it.get("snippet") or "")[:200].replace("\n", " ")
            if title or snip:
                lines.append(f"[{idx}] {title} — {snip}")
        if lines:
            prefetch_block = (
                "\n\n【系统预检索摘要（可配合 kb_search / read_document 核实）】\n"
                + "\n".join(lines)
            )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT + prefetch_block}
    ]
    for past in history[-6:]:  # keep last 6 turns for context
        if past.get("role") in ("user", "assistant") and past.get("content"):
            messages.append({"role": past["role"], "content": past["content"]})
    messages.append({"role": "user", "content": user_message})

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        try:
            result = await provider.complete(messages, tools=AVAILABLE_TOOLS)
        except Exception as exc:  # noqa: BLE001 — defensive; keep the loop safe
            logger.exception("[react] LLM call failed")
            yield {
                "event": "error",
                "data": {"message": f"LLM provider failed: {exc}"},
            }
            yield {
                "event": "final_answer",
                "data": {
                    "answer": "抱歉，模型调用失败。请稍后再试。",
                    "citations": [],
                },
            }
            return

        # The complete() return shape: {"content": "...", "tool_calls": [...], ...}
        content = (result or {}).get("content") or ""
        tool_calls = (result or {}).get("tool_calls") or []

        if content.strip():
            yield {"event": "thought", "data": {"text": content[:600], "iteration": iteration}}

        if not tool_calls:
            # No tool — treat content as the final answer.
            yield {
                "event": "final_answer",
                "data": {
                    "answer": content or "（无内容）",
                    "citations": [],
                    "iteration": iteration,
                },
            }
            return

        # Append assistant message with tool_calls so OpenAI tool-calling
        # protocol stays valid for the next turn.
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        # Process the first tool call (we throttle to 1 per round).
        call = tool_calls[0]
        fn = (call.get("function") or {})
        name = fn.get("name") or ""
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except Exception:
            args = {}

        # If LLM called final_answer, surface and stop.
        if name == "final_answer":
            yield {
                "event": "final_answer",
                "data": {
                    "answer": args.get("answer") or content or "(空)",
                    "citations": args.get("citations") or [],
                    "iteration": iteration,
                },
            }
            return

        yield {"event": "tool_call", "data": {"name": name, "args": args, "iteration": iteration}}

        observation = await _dispatch_tool(db, user, name, args)
        # Trim observation for SSE / LLM context window.
        obs_str = json.dumps(observation, ensure_ascii=False)[:3500]
        yield {
            "event": "tool_result",
            "data": {"name": name, "result": observation, "iteration": iteration},
        }

        # Feed observation back to the LLM as a tool message.
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.get("id") or "",
                "name": name,
                "content": obs_str,
            }
        )

    # Hit max iterations — ask LLM for a wrap-up answer with no further tools.
    try:
        wrap = await provider.complete(messages)
        wrap_content = (wrap or {}).get("content") or ""
    except Exception:
        wrap_content = ""
    yield {
        "event": "final_answer",
        "data": {
            "answer": wrap_content
            or "（达到最大工具调用次数；这里基于已检索内容给出概述。）",
            "citations": [],
            "iteration": iteration,
            "truncated": True,
        },
    }
