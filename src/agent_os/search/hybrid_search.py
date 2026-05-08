"""Legacy hybrid search compatibility layer."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.search.keyword_search import KeywordSearchResult, KeywordSearchService


@dataclass(slots=True)
class HybridSearchResult:
    item_id: str
    title: str
    snippet: str
    final_score: float
    keyword_score: float
    semantic_score: float
    freshness_score: float
    match_type: str
    matched_terms: list[str]

    @property
    def content_snippet(self) -> str:
        return self.snippet


class HybridSearchService:
    """Blend keyword results with deterministic freshness/semantic signals."""

    def __init__(
        self,
        *,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        freshness_days: int = 30,
    ) -> None:
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.freshness_days = freshness_days
        self.keyword_service = KeywordSearchService()

    async def search(
        self,
        db_session: AsyncSession,
        *,
        workspace_id: str | uuid.UUID | None = None,
        query: str,
        limit: int = 20,
        item_types: list[str] | None = None,
    ) -> list[HybridSearchResult]:
        keyword_results = await self.keyword_service.search(
            db_session,
            workspace_id=workspace_id,
            query=query,
            limit=max(limit * 2, limit),
            item_types=item_types,
        )
        merged = self._merge_and_rank(keyword_results, {}, query)
        return merged[: max(0, limit)]

    def _merge_and_rank(
        self,
        keyword_results: list[KeywordSearchResult],
        semantic_results: dict[str, float] | None,
        query: str,
    ) -> list[HybridSearchResult]:
        semantic_results = semantic_results or {}
        max_keyword = max((result.score for result in keyword_results), default=1.0)
        by_id: dict[str, KeywordSearchResult] = {
            str(result.item_id): result for result in keyword_results
        }
        all_ids = set(by_id) | {str(item_id) for item_id in semantic_results}

        merged: list[HybridSearchResult] = []
        for item_id in all_ids:
            keyword = by_id.get(item_id)
            keyword_score = (keyword.score / max_keyword) if keyword else 0.0
            semantic_score = float(semantic_results.get(item_id, 0.0))
            freshness = self._calculate_freshness_boost(item_id)
            final = (
                keyword_score * self.keyword_weight
                + semantic_score * self.semantic_weight
                + freshness * 0.05
            )
            match_type = (
                "hybrid"
                if keyword_score and semantic_score
                else "keyword"
                if keyword_score
                else "semantic"
            )
            title = keyword.title if keyword else f"Result {item_id}"
            snippet = keyword.content_snippet if keyword else ""
            matched = list(keyword.matched_terms) if keyword else []
            merged.append(
                HybridSearchResult(
                    item_id=item_id,
                    title=title,
                    snippet=self._apply_highlight(snippet, [keyword] if keyword else []),
                    final_score=max(0.0, final),
                    keyword_score=max(0.0, min(1.0, keyword_score)),
                    semantic_score=max(0.0, min(1.0, semantic_score)),
                    freshness_score=freshness,
                    match_type=match_type,
                    matched_terms=matched,
                )
            )

        merged.sort(key=lambda result: result.final_score, reverse=True)
        return merged

    def _calculate_freshness_boost(self, item_id: str) -> float:
        try:
            parsed = uuid.UUID(str(item_id))
        except ValueError:
            return 0.0
        if parsed.version != 1:
            return 0.0

        created_at = datetime.fromtimestamp(
            (parsed.time - 0x01B21DD213814000) / 10_000_000,
            tz=UTC,
        )
        age_days = max(0.0, (datetime.now(UTC) - created_at).total_seconds() / 86400)
        if self.freshness_days <= 0:
            return 0.0
        return max(0.0, min(1.0, 1 - age_days / self.freshness_days))

    def _apply_highlight(
        self,
        text: str,
        keyword_results: list[KeywordSearchResult | None],
    ) -> str:
        highlighted = text or ""
        terms: list[str] = []
        for result in keyword_results:
            if result:
                terms.extend(result.matched_terms)
        for term in sorted(set(terms), key=len, reverse=True):
            if not term:
                continue
            highlighted = re.sub(
                f"({re.escape(term)})",
                r"**\1**",
                highlighted,
                flags=re.IGNORECASE,
            )
        return highlighted


async def hybrid_search(*args: Any, **kwargs: Any) -> list[HybridSearchResult]:
    """Run legacy hybrid search using ``HybridSearchService``."""

    return await HybridSearchService().search(*args, **kwargs)
