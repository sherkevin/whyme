"""Legacy keyword search compatibility layer.

PRD10's canonical search API lives in ``agent_os.search_engine``. This module
keeps the older ``agent_os.search`` import path functional for legacy tests and
internal callers by running a small real keyword search over PRD4 ``Item`` rows.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


@dataclass(slots=True)
class KeywordSearchResult:
    item_id: str
    title: str
    content_snippet: str
    score: float
    matched_terms: list[str]
    item_type: str | None = None


class KeywordSearchService:
    """Simple BM25-style keyword search for legacy PRD4 items."""

    def __init__(self, *, title_weight: float = 2.0, content_weight: float = 1.0) -> None:
        self.title_weight = title_weight
        self.content_weight = content_weight

    def _tokenize_query(self, query: str) -> list[str]:
        if not query or not query.strip():
            return []

        raw_terms = re.findall(r"[\w+#@.-]+", query.lower(), flags=re.UNICODE)
        seen: set[str] = set()
        terms: list[str] = []
        for term in raw_terms:
            normalized = term.strip("._-")
            if not normalized or normalized in _STOP_WORDS or normalized in seen:
                continue
            seen.add(normalized)
            terms.append(normalized)
        return terms

    def _calculate_bm25_score(
        self,
        item: Any,
        query_terms: list[str],
    ) -> tuple[float, list[str]]:
        title = str(getattr(item, "title", "") or "")
        content = str(getattr(item, "content", "") or "")
        title_l = title.lower()
        content_l = content.lower()

        score = 0.0
        matched: list[str] = []
        doc_length = max(1, len(self._tokenize_query(f"{title} {content}")))
        avg_doc_length = 80
        k1 = 1.2
        b = 0.75

        for term in query_terms:
            title_tf = title_l.count(term)
            content_tf = content_l.count(term)
            tf = (title_tf * self.title_weight) + (content_tf * self.content_weight)
            if tf <= 0:
                continue
            matched.append(term)
            # A compact BM25-like score without corpus-wide IDF. This keeps the
            # legacy path deterministic while still ranking denser matches first.
            denom = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))
            score += ((tf * (k1 + 1)) / denom) * (1 + math.log1p(title_tf))

        return score, matched

    def _generate_snippet(
        self,
        content: str | None,
        query_terms: list[str],
        *,
        max_length: int = 160,
    ) -> str:
        text = (content or "").strip()
        if not text:
            return ""
        if not query_terms:
            return text[:max_length]

        lower = text.lower()
        first_hit = min(
            (lower.find(term) for term in query_terms if lower.find(term) >= 0),
            default=0,
        )
        start = max(0, first_hit - max_length // 3)
        end = min(len(text), start + max_length)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet += "..."
        return snippet

    async def search(
        self,
        db_session: AsyncSession,
        *,
        workspace_id: str | uuid.UUID | None = None,
        query: str,
        limit: int = 20,
        item_types: list[str] | None = None,
    ) -> list[KeywordSearchResult]:
        terms = self._tokenize_query(query)
        if not terms:
            return []

        stmt = select(Item)
        if workspace_id:
            workspace_uuid = (
                workspace_id
                if isinstance(workspace_id, uuid.UUID)
                else uuid.UUID(str(workspace_id))
            )
            stmt = stmt.where(Item.workspace_id == workspace_uuid)
        if item_types:
            stmt = stmt.where(Item.type.in_(item_types))

        rows = (await db_session.execute(stmt)).scalars().all()
        results: list[KeywordSearchResult] = []
        for item in rows:
            score, matched_terms = self._calculate_bm25_score(item, terms)
            if score <= 0:
                continue
            results.append(
                KeywordSearchResult(
                    item_id=str(item.id),
                    title=str(item.title or ""),
                    content_snippet=self._generate_snippet(item.content, terms),
                    score=score,
                    matched_terms=matched_terms,
                    item_type=item.type,
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[: max(0, limit)]


async def search_by_keywords(*args: Any, **kwargs: Any) -> list[KeywordSearchResult]:
    """Run legacy keyword search using ``KeywordSearchService``."""

    return await KeywordSearchService().search(*args, **kwargs)
