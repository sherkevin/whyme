"""Deep research service helpers.

The `/research/tasks` endpoint persists jobs, insights, and documents. This
module handles retrieval and LLM synthesis so the router can stay focused on
the API contract.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.ai.llm_provider import get_provider, is_llm_enabled
from agent_os.auth.models import User
from agent_os.kb.models import Document
from agent_os.knowledge.models import Card


@dataclass(slots=True)
class ResearchSourceBundle:
    cards: list[Card]
    documents: list[Document]
    source_block: str


@dataclass(slots=True)
class ResearchDraft:
    body: str
    summary: str
    used_llm: bool
    model: str


async def collect_research_sources(
    db: AsyncSession,
    *,
    user: User,
    topic: str,
    scan_limit: int = 40,
    output_limit: int = 8,
) -> ResearchSourceBundle:
    """Retrieve real cards/documents related to a deep-research topic."""

    cards_q = await db.execute(
        select(Card)
        .where(Card.user_id == user.id, Card.deleted_at.is_(None))
        .order_by(Card.updated_at.desc())
        .limit(scan_limit)
    )
    all_cards = list(cards_q.scalars().all())

    docs_q = await db.execute(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.updated_at.desc())
        .limit(scan_limit)
    )
    all_documents = list(docs_q.scalars().all())

    needle = topic.lower().strip()

    def _matches(value: str | None) -> bool:
        if not needle:
            return True
        return needle in (value or "").lower()

    matched_cards = [
        c for c in all_cards
        if _matches(c.title) or _matches(c.summary) or _matches(c.content)
    ] or all_cards[:output_limit]
    matched_documents = [
        d for d in all_documents
        if _matches(d.title) or _matches(d.summary) or _matches(d.content)
    ] or all_documents[:output_limit]

    source_lines: list[str] = []
    for card in matched_cards[:output_limit]:
        source_lines.append(
            f"- [card:{card.id}] {card.title or 'Untitled'}: "
            f"{(card.summary or card.content or '')[:260]}"
        )
    for doc in matched_documents[:output_limit]:
        source_lines.append(
            f"- [doc:{doc.id}] {doc.title or 'Untitled'}: "
            f"{(doc.summary or doc.content or '')[:260]}"
        )

    return ResearchSourceBundle(
        cards=matched_cards,
        documents=matched_documents,
        source_block="\n".join(source_lines) or "- No matching knowledge assets yet.",
    )


async def synthesize_research_draft(
    *,
    topic: str,
    scope: str,
    output_hint: str,
    sources: ResearchSourceBundle,
) -> ResearchDraft:
    """Generate a research report from retrieved sources with LLM fallback."""

    fallback_body = (
        f"# Deep Research: {topic}\n\n"
        f"## Scope\n{scope or 'No explicit scope provided.'}\n\n"
        "## Findings\n"
        "Current knowledge assets are limited for this topic. Add more sources "
        "or enable the LLM provider to synthesize a richer research report.\n\n"
        f"## Retrieved Sources\n{sources.source_block}\n"
    )
    fallback_summary = (
        f"Deep research report for {topic} based on "
        f"{len(sources.cards)} cards and {len(sources.documents)} documents."
    )

    if not is_llm_enabled():
        return ResearchDraft(
            body=fallback_body,
            summary=fallback_summary,
            used_llm=False,
            model="",
        )

    try:
        completion = await asyncio.wait_for(
            get_provider().complete(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Mydow's deep research analyst. Write a concise, "
                            "source-grounded Chinese Markdown report. Do not invent facts; "
                            "only use the retrieved cards/documents and clearly state gaps."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"研究主题: {topic}\n"
                            f"研究范围: {scope or '未限定'}\n"
                            f"期望输出: {output_hint or '结构化研究报告'}\n\n"
                            f"真实检索素材:\n{sources.source_block}\n\n"
                            "请输出 Markdown，包含：结论摘要、关键发现、证据来源、风险/空白、下一步建议。"
                        ),
                    },
                ],
                temperature=0.35,
                max_tokens=1600,
            ),
            timeout=60.0,
        )
    except Exception:
        return ResearchDraft(
            body=fallback_body,
            summary=fallback_summary,
            used_llm=False,
            model="",
        )

    content_str: str | None = None
    if isinstance(completion, dict):
        value = completion.get("content")
        if isinstance(value, str):
            content_str = value
        if not content_str and isinstance(completion.get("message"), dict):
            message_content = completion["message"].get("content")
            if isinstance(message_content, str):
                content_str = message_content

    if not content_str or not content_str.strip():
        return ResearchDraft(
            body=fallback_body,
            summary=fallback_summary,
            used_llm=False,
            model="",
        )

    body = content_str.strip()
    summary = next(
        (line.strip("# ").strip() for line in body.splitlines() if line.strip()),
        fallback_summary,
    )[:240]
    return ResearchDraft(
        body=body,
        summary=summary,
        used_llm=True,
        model=str(completion.get("model") or "") if isinstance(completion, dict) else "",
    )
