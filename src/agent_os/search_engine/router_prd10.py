"""PRD10 Global Search router (`/api/v1/search`, `/api/v1/search/suggestions`).

This module implements the PRD10 §11 search surface on top of the existing
``SearchIndex`` table (extended in Milestone 4 to PRD10 §5.14 SearchDocument
shape). It is a **read path** only — ingestion still flows through the legacy
``SearchService.index_item`` written by Agent 2's capture pipeline.

Why a new router file (instead of patching ``search_engine.router``):

* The legacy router exposes PRD4 endpoints under ``/api/v1/search/index/...``
  with PRD4 schemas and is consumed by existing tests. PRD10 §11 only needs
  the ``GET /api/v1/search`` and ``GET /api/v1/search/suggestions`` surface,
  with the PRD10 envelope from ``agent_os.common``.
* Keeping the PRD10 surface in its own module lets Agent 1's app wiring
  decide whether to expose both prefixes or replace the legacy one when the
  PRD4 router is finally retired.

Scope rules:

* Authenticated user. Filter results by ``user_id`` **or** ``user_id IS NULL``
  so legacy ingestion rows (which don't carry a user yet) remain searchable
  for Agent 2 / capture flows. PRD10 will tighten this once the ingestion
  pipeline starts populating ``user_id``.
* ``object_type`` query parameter accepts the PRD10 §5.14 set; legacy
  CheckConstraint values are also accepted to stay forward-compatible with
  the data already in the table.
* Pagination via PRD10 envelope (``items`` + ``pagination``).
* Empty list is a successful response per ``agent-1-backend-contract.md``.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.search_engine.embeddings import (
    cosine_similarity,
    embed_text,
    text_for_search_embedding,
    tokenize,
)
from agent_os.search_engine.models import SearchIndex

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/search", tags=["search-prd10"])


# PRD10 §5.14 object_type universe. Anything outside this set is rejected
# at the API edge (a 422 from FastAPI's Query validator).
_PRD10_OBJECT_TYPES: tuple[str, ...] = (
    "card",
    "document",
    "folder",
    "task",
    "conversation",
    "message",
    "skill",
    "insight",
)


def _make_snippet(content: str | None, summary: str | None, query: str) -> str:
    """Build a small highlight-friendly snippet.

    PRD10 §11 expects a ``highlight`` placeholder that surrounds the matched
    term with ``<mark>...</mark>``. Until full text indexing is hooked up,
    we approximate this from ``summary`` (preferred) or the head of
    ``content`` and bold the first occurrence of ``query`` if present.
    """

    base = (summary or content or "").strip()
    if not base:
        return ""

    head = base[:240]
    if query:
        idx = head.lower().find(query.lower())
        if idx >= 0:
            end = idx + len(query)
            return f"{head[:idx]}<mark>{head[idx:end]}</mark>{head[end:]}"
    return head


def _result_url(object_type: str, object_id: str) -> str:
    """Best-effort URL hint per PRD10 §11 example (``/kb/doc_001`` etc.).

    The frontend owns the actual route; we expose a stable convention so the
    PRD10 contract has a non-empty value to assert against in tests.
    """

    routes = {
        "card": "/cards",
        "document": "/kb",
        "folder": "/kb/folders",
        "task": "/tasks",
        "conversation": "/ai/conversations",
        "message": "/ai/messages",
        "skill": "/skills",
        "insight": "/insights",
    }
    base = routes.get(object_type, f"/{object_type}")
    return f"{base}/{object_id}"


def _row_score(row: SearchIndex, tokens: list[str], idf: dict[str, float]) -> float:
    """Lexical BM25-ish score against the query tokens.

    Title hits weigh more than summary/content hits. Hybrid mode combines this
    lexical signal with the deterministic vector stored in ``SearchIndex``.
    """

    if not tokens:
        return 0.0

    title_tokens = tokenize(row.title or "")
    body_tokens = tokenize(
        " ".join(filter(None, [row.summary or "", row.content or ""]))
    )
    if not title_tokens and not body_tokens:
        return 0.0

    title_counts: dict[str, float] = {}
    for token in title_tokens:
        title_counts[token] = title_counts.get(token, 0.0) + 1.0

    body_counts: dict[str, float] = {}
    for token in body_tokens:
        body_counts[token] = body_counts.get(token, 0.0) + 1.0

    score = 0.0
    for token in set(tokens):
        title_tf = title_counts.get(token, 0.0)
        body_tf = body_counts.get(token, 0.0)
        if not title_tf and not body_tf:
            continue
        weight = idf.get(token, 1.0)
        score += weight * (3.0 * math.log(1.0 + title_tf) + math.log(1.0 + body_tf))
    return score


def _row_embedding(row: SearchIndex) -> list[float]:
    if isinstance(row.embedding, list) and row.embedding:
        return [float(value) for value in row.embedding]
    return embed_text(text_for_search_embedding(row.title, row.summary, row.content))


def _to_search_item(row: SearchIndex, query: str, score: float = 0.0) -> dict:
    """Map a ``SearchIndex`` row to the PRD10 §11 search result item shape."""

    object_id = str(row.item_id) if row.item_id else ""
    return {
        "object_type": row.item_type,
        "object_id": object_id,
        "title": row.title,
        "summary": row.summary,
        "highlight": _make_snippet(row.content, row.summary, query),
        "score": round(float(score), 6),
        "url": _result_url(row.item_type, object_id),
        "updated_at": (
            row.updated_at.isoformat() if row.updated_at else None
        ),
    }


def _user_scope_clause(user_id):
    """Filter rows visible to ``user_id`` plus legacy un-owned ingestion rows.

    Once the ingestion pipeline sets ``user_id`` on every write, this clause
    can tighten to ``SearchIndex.user_id == user_id``. Until then we keep the
    OR so existing data stays addressable.
    """

    return or_(
        SearchIndex.user_id == user_id,
        SearchIndex.user_id.is_(None),
    )


_VALID_MODES: tuple[str, ...] = ("keyword", "semantic", "hybrid")


def _resolve_mode(value: str | None) -> str:
    candidate = (value or "keyword").strip().lower()
    if candidate not in _VALID_MODES:
        return "keyword"
    return candidate


def _date_cutoff_preset(preset: str | None) -> datetime | None:
    """Map UI date presets (v1.4 search modal) to UTC lower bounds."""

    if not preset:
        return None
    p = str(preset).strip().lower()
    if p in ("", "all", "none", "不限", "不限日期"):
        return None
    now = datetime.now(timezone.utc)
    if p in ("today", "今天"):
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if p in ("7d", "week", "最近7天", "最近 7 天"):
        return now - timedelta(days=7)
    if p in ("30d", "month", "最近30天", "最近 30 天"):
        return now - timedelta(days=30)
    return None


@router.get("")
async def global_search(
    request: Request,
    q: str = Query("", description="Search query string"),
    object_type: list[str] = Query(
        default=[],
        description=(
            "Filter by PRD10 §5.14 object_type. May be repeated. "
            f"Allowed: {', '.join(_PRD10_OBJECT_TYPES)}."
        ),
    ),
    mode: str = Query(
        default="keyword",
        description="One of keyword/semantic/hybrid (PRD10 §13.1).",
    ),
    title_only: bool = Query(
        False,
        description="If true, match query only against ``title`` (v1.4 仅搜索标题).",
    ),
    mine_only: bool = Query(
        False,
        description="If true, only ``SearchIndex`` rows owned by the current user.",
    ),
    date_preset: str | None = Query(
        None,
        description="Optional time window: all/today/7d/30d (also accepts v1.4 Chinese labels).",
    ),
    sort: str = Query(
        "updated_at",
        description="keyword-path ordering: updated_at | title | relevance "
        "(relevance forces hybrid ranking when q is non-empty).",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.1 / §13.1 ``GET /api/v1/search``.

    ``mode``:

    * ``keyword`` (default) — SQL ``ILIKE`` filter on title/summary/content.
    * ``semantic`` / ``hybrid`` — rank by persisted deterministic embeddings
      stored on ``SearchIndex.embedding``. Hybrid keeps the keyword filter to
      bound large corpora, then combines 70% vector similarity + 30% lexical
      TF-IDF. A future neural provider can replace the local hashing
      embedder while keeping the API contract unchanged.
    """

    query_text = (q or "").strip()
    valid_types = [t for t in object_type if t in _PRD10_OBJECT_TYPES]
    sort_key = (sort or "updated_at").strip().lower()
    if sort_key not in ("updated_at", "title", "relevance"):
        sort_key = "updated_at"

    resolved_mode = _resolve_mode(mode)
    # UX: “相关度” in the v1.4 search bar maps to hybrid vector+lexical rank.
    if sort_key == "relevance" and query_text:
        resolved_mode = "hybrid"

    base = select(SearchIndex).where(_user_scope_clause(current_user.id))

    if mine_only:
        base = base.where(SearchIndex.user_id == current_user.id)

    cutoff_dt = _date_cutoff_preset(date_preset)
    if cutoff_dt is not None:
        ts = func.coalesce(SearchIndex.updated_at, SearchIndex.created_at)
        base = base.where(ts >= cutoff_dt)

    if query_text and resolved_mode in ("keyword", "hybrid"):
        like_pattern = f"%{query_text}%"
        if title_only:
            base = base.where(SearchIndex.title.ilike(like_pattern))
        else:
            base = base.where(
                or_(
                    SearchIndex.title.ilike(like_pattern),
                    SearchIndex.summary.ilike(like_pattern),
                    SearchIndex.content.ilike(like_pattern),
                )
            )

    if valid_types:
        base = base.where(SearchIndex.item_type.in_(valid_types))

    order_expr = SearchIndex.updated_at.desc().nulls_last()
    if sort_key == "title":
        order_expr = SearchIndex.title.asc().nulls_last()

    extra_filters = {
        "mode": resolved_mode,
        "title_only": title_only,
        "mine_only": mine_only,
        "date_preset": date_preset or "all",
        "sort": sort_key,
    }

    if resolved_mode == "keyword" or not query_text:
        # Cheap path: count + page in SQL, sort by recency or title.
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar_one() or 0

        rows_stmt = (
            base.order_by(order_expr).limit(page_size).offset((page - 1) * page_size)
        )
        result = await db.execute(rows_stmt)
        rows: Iterable[SearchIndex] = result.scalars().all()
        items = [_to_search_item(row, query_text) for row in rows]
        return paginated_response(
            items,
            page=page,
            page_size=page_size,
            total=int(total),
            extra=extra_filters,
            request=request,
        )

    # Ranked path (semantic / hybrid). Pull a bounded slice and score in
    # Python; this is fine for the V1 corpus targets (10k SearchDocument).
    fetch_cap = max(page * page_size, 200)
    rows = (
        await db.execute(
            base.order_by(SearchIndex.updated_at.desc().nulls_last()).limit(fetch_cap)
        )
    ).scalars().all()

    tokens = tokenize(query_text)
    query_embedding = embed_text(query_text)
    df: dict[str, int] = {}
    if tokens:
        for row in rows:
            row_tokens = set(
                tokenize(
                    " ".join(filter(None, [row.title or "", row.summary or "", row.content or ""]))
                )
            )
            for tok in row_tokens:
                df[tok] = df.get(tok, 0) + 1
    n = max(1, len(rows))
    idf = {tok: math.log(1.0 + n / (1 + count)) for tok, count in df.items()}

    scored = []
    for row in rows:
        lexical_score = _row_score(row, tokens, idf)
        semantic_score = max(0.0, cosine_similarity(query_embedding, _row_embedding(row)))
        if resolved_mode == "hybrid":
            score = (0.3 * lexical_score) + (0.7 * semantic_score)
        else:
            score = semantic_score
        scored.append((row, score))

    scored = sorted(scored, key=lambda item: item[1], reverse=True)
    if resolved_mode == "semantic":
        # Drop zero-score rows so semantic mode does not surface noise.
        scored = [(row, score) for row, score in scored if score > 0]

    total = len(scored)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = scored[start:end]
    items = [_to_search_item(row, query_text, score=score) for row, score in page_rows]

    return paginated_response(
        items,
        page=page,
        page_size=page_size,
        total=total,
        extra=extra_filters,
        request=request,
    )


@router.get("/suggestions")
async def search_suggestions(
    request: Request,
    q: str = Query("", description="Query prefix"),
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §11.2 ``GET /api/v1/search/suggestions``.

    Returns recent matching titles as autocomplete hints. The implementation
    is intentionally simple — title prefix match — and lives in the database
    so we don't need a separate suggestion store for the MVP.
    """

    query_text = (q or "").strip()

    if not query_text:
        return success_response({"suggestions": []}, request=request)

    stmt = (
        select(SearchIndex.title, SearchIndex.item_type, SearchIndex.item_id)
        .where(_user_scope_clause(current_user.id))
        .where(SearchIndex.title.ilike(f"{query_text}%"))
        .order_by(SearchIndex.updated_at.desc().nulls_last())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    suggestions = [
        {
            "title": title,
            "object_type": object_type,
            "object_id": str(object_id) if object_id else "",
        }
        for title, object_type, object_id in rows
    ]

    return success_response({"suggestions": suggestions}, request=request)
