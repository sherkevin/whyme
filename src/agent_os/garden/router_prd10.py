"""PRD10 Garden router (`/api/v1/garden/*`).

Implements §18:

* ``GET /api/v1/garden/overview`` — counts + topics + recent insights
* ``GET /api/v1/garden/graph``    — nodes + edges, ready for the FE empty
  state when there is no data.

Edge derivation strategy (§18 ``rich graph algorithm``, todo §6.4):

The MVP `KnowledgeCardLink` table comes from PRD7 and references the legacy
`items.id` column, so it cannot be populated by PRD10 capture/feed which
writes to `cards.id`. To keep the biz-prototype Garden page
(`static/mydow/biz/index.html` `.garden-board`) visually alive *without* a
new migration, we derive **semantic edges** from card tag overlap (Jaccard
similarity) and merge them with any pre-existing `KnowledgeCardLink` rows.

* `_derive_semantic_edges(cards, ...)` returns `{source, target, weight,
  relation_type, shared_tags}` for every tag-overlapping card pair whose
  weight ≥ `_WEIGHT_THRESHOLD` (default 0.2). Edges between cards in the
  same folder upgrade their relation type from ``semantic_related`` →
  ``support`` (visual hint that they came from one body of work).
* `node.size` reflects the degree (incoming + outgoing edge count) so the
  most-connected cards visibly grow in the SVG graph.
* `recent_insights` and `top_topics` keep their original sources.

Reuses:

* ``knowledge.models.Card``  (PRD7+10 cards) for ``node_count`` /
  ``top_topics`` / derived edges.
* ``garden.models.KnowledgeCardLink`` (legacy) — still merged when present.
* ``garden.models.DailyInsight``       — ``recent_insights``.

PRD10 §18 explicitly says V1 may be a thin shim — empty result is a
successful empty payload, not an error. We honor that strictly.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import success_response
from agent_os.db.base import get_db
from agent_os.garden.models import DailyInsight, KnowledgeCardLink
from agent_os.knowledge.models import Card

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/garden", tags=["garden-prd10"])


_STRONG_EDGE_THRESHOLD = 0.7
_WEIGHT_THRESHOLD = 0.2  # PRD10 §18 derived-edge floor (Jaccard)
_TOP_TOPICS_LIMIT = 10
_RECENT_INSIGHTS_LIMIT = 5
_DERIVED_EDGES_LIMIT_DEFAULT = 200


def _norm_tags(raw: Any) -> set[str]:
    """Best-effort tag normalisation that ignores junk / non-strings."""

    if not raw:
        return set()
    out: set[str] = set()
    for tag in raw:
        if isinstance(tag, str):
            stripped = tag.strip()
            if stripped:
                out.add(stripped)
    return out


def _derive_semantic_edges(
    cards: list[Card],
    *,
    weight_threshold: float = _WEIGHT_THRESHOLD,
    max_edges: int = _DERIVED_EDGES_LIMIT_DEFAULT,
) -> list[dict[str, Any]]:
    """Return Jaccard-derived edges between cards that share tags.

    Algorithm:
        weight = |tags_a ∩ tags_b| / |tags_a ∪ tags_b|

    Edges with `weight ≥ _STRONG_EDGE_THRESHOLD` (default 0.7) are also
    counted as "strong" by the overview endpoint. Cards in the same
    folder use ``relation_type=support`` instead of ``semantic_related``
    so the FE can color/style them differently if needed.

    Stable ordering: highest weight first, ties broken by ``(source,
    target)`` lex order so re-runs return identical edge ids.
    """

    n = len(cards)
    if n < 2:
        return []

    tag_cache: dict[int, set[str]] = {}
    for idx, card in enumerate(cards):
        tag_cache[idx] = _norm_tags(card.tags)

    out: list[dict[str, Any]] = []
    for i in range(n):
        tags_i = tag_cache[i]
        if not tags_i:
            continue
        ai = cards[i]
        for j in range(i + 1, n):
            tags_j = tag_cache[j]
            if not tags_j:
                continue
            inter = tags_i & tags_j
            if not inter:
                continue
            union = tags_i | tags_j
            weight = len(inter) / len(union) if union else 0.0
            if weight < weight_threshold:
                continue
            bj = cards[j]
            same_folder = (
                ai.folder_id is not None
                and bj.folder_id is not None
                and ai.folder_id == bj.folder_id
            )
            relation_type = "support" if same_folder else "semantic_related"
            source_id = str(ai.id)
            target_id = str(bj.id)
            out.append(
                {
                    "id": f"derived:{source_id}:{target_id}",
                    "source": source_id,
                    "target": target_id,
                    "weight": round(weight, 4),
                    "relation_type": relation_type,
                    "shared_tags": sorted(inter),
                }
            )

    out.sort(key=lambda e: (-e["weight"], e["source"], e["target"]))
    return out[:max_edges]


def _serialize_insight(insight: DailyInsight) -> dict[str, Any]:
    return {
        "id": str(insight.id),
        "title": insight.title,
        "status": insight.status,
        "level": insight.level,
        "stability_score": (
            float(insight.stability_score)
            if insight.stability_score is not None
            else None
        ),
        "created_at": (
            insight.created_at.isoformat() if insight.created_at else None
        ),
    }


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview")
async def garden_overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    range: str = Query(default="all", description="7d|30d|90d|1y|all"),
    type: str = Query(default="all", description="all|note|link|audio|research|insight"),
) -> dict:
    """PRD10 §18.1 ``GET /api/v1/garden/overview``.

    Counts now include **derived semantic edges** (Jaccard similarity over
    ``Card.tags``) on top of any existing ``KnowledgeCardLink`` rows so the
    biz Garden page (`.garden-board`) shows a non-zero `edge_count` for
    real demo data without requiring the legacy `KnowledgeCardLink` table
    to be populated.

    §17.3 — accepts ``range`` (time window) and ``type`` (node type)
    filters from the v1.4 frontend's `data-inline-menu` chips. Card
    ``content_type`` and ``created_at`` columns drive the filter.
    """

    # Pull cards once so we can both count nodes and derive semantic edges
    # without re-hitting the DB.
    from datetime import UTC, datetime, timedelta
    range_to_days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
    type_alias = {
        "note": ("note",),
        "link": ("article", "link"),
        "audio": ("audio",),
        "research": ("research",),
        "insight": ("insight",),
    }

    stmt = select(Card).where(Card.user_id == current_user.id)
    if range in range_to_days:
        cutoff = datetime.now(UTC) - timedelta(days=range_to_days[range])
        stmt = stmt.where(Card.created_at >= cutoff)
    if type in type_alias:
        stmt = stmt.where(Card.content_type.in_(type_alias[type]))
    cards = (await db.execute(stmt)).scalars().all()
    node_count = len(cards)

    derived_edges = _derive_semantic_edges(cards)
    derived_edge_count = len(derived_edges)
    derived_strong_count = sum(
        1 for e in derived_edges if e["weight"] >= _STRONG_EDGE_THRESHOLD
    )

    # Legacy `KnowledgeCardLink` rows scoped to the user's cards (PRD7
    # carry-over). Use card ids regardless of FK strictness so PG and
    # SQLite behave identically here.
    card_ids = {card.id for card in cards}
    legacy_edge_count = 0
    legacy_strong_count = 0
    if card_ids:
        legacy_edge_count = (
            await db.execute(
                select(func.count(KnowledgeCardLink.id)).where(
                    and_(
                        KnowledgeCardLink.is_active.is_(True),
                        or_(
                            KnowledgeCardLink.from_id.in_(card_ids),
                            KnowledgeCardLink.to_id.in_(card_ids),
                        ),
                    )
                )
            )
        ).scalar_one() or 0
        legacy_strong_count = (
            await db.execute(
                select(func.count(KnowledgeCardLink.id)).where(
                    and_(
                        KnowledgeCardLink.is_active.is_(True),
                        KnowledgeCardLink.relation_strength
                        >= _STRONG_EDGE_THRESHOLD,
                        or_(
                            KnowledgeCardLink.from_id.in_(card_ids),
                            KnowledgeCardLink.to_id.in_(card_ids),
                        ),
                    )
                )
            )
        ).scalar_one() or 0

    edge_count = derived_edge_count + int(legacy_edge_count)
    strong_edge_count = derived_strong_count + int(legacy_strong_count)

    # Top topics: aggregate ``Card.tags`` JSON arrays in Python because the
    # JSON aggregation function set differs between PostgreSQL and SQLite.
    counter: Counter[str] = Counter()
    for card in cards:
        for tag in _norm_tags(card.tags):
            counter[tag] += 1
    top_topics = [tag for tag, _count in counter.most_common(_TOP_TOPICS_LIMIT)]

    # Recent insights for this user.
    recent_stmt = (
        select(DailyInsight)
        .where(DailyInsight.user_id == current_user.id)
        .order_by(DailyInsight.created_at.desc())
        .limit(_RECENT_INSIGHTS_LIMIT)
    )
    recent_insights = (await db.execute(recent_stmt)).scalars().all()

    data = {
        "node_count": int(node_count),
        "edge_count": int(edge_count),
        "strong_edge_count": int(strong_edge_count),
        "derived_edge_count": int(derived_edge_count),
        "legacy_edge_count": int(legacy_edge_count),
        "top_topics": top_topics,
        "recent_insights": [_serialize_insight(i) for i in recent_insights],
    }
    return success_response(data, request=request)


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


_VALID_RANGES = ("7d", "30d", "90d", "all")
_VALID_RELATION_TYPES = ("related", "support", "contradict", "reference")


@router.get("/graph")
async def garden_graph(
    request: Request,
    range: str = Query(
        "30d",
        description=f"Time window. Allowed: {', '.join(_VALID_RANGES)}",
    ),
    topic: str | None = Query(None, description="Filter cards by tag"),
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §18.2 ``GET /api/v1/garden/graph``.

    ``depth``/``range`` are accepted for forward compatibility; MVP returns
    a flat list of nodes (the user's own cards) and any edges in
    ``knowledge_card_links`` that touch those node ids. Empty graph is a
    success per ``agent-3-todo.md`` task 8.
    """

    if range not in _VALID_RANGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": (
                    f"Invalid range '{range}'. "
                    f"Allowed: {', '.join(_VALID_RANGES)}"
                ),
            },
        )

    card_stmt = (
        select(Card)
        .where(Card.user_id == current_user.id)
        .order_by(Card.created_at.desc())
        .limit(limit)
    )
    cards = (await db.execute(card_stmt)).scalars().all()

    if topic:
        # PRD10 §18 ``topic`` filter — JSON containment differs across
        # dialects, so we apply a Python-side filter once the rows are
        # in memory. The MVP corpus is small enough that this is fine.
        topic_clean = topic.strip()
        cards = [
            card
            for card in cards
            if isinstance(card.tags, list) and topic_clean in card.tags
        ]

    if not cards:
        return success_response(
            {"nodes": [], "edges": []}, request=request
        )

    derived_edges = _derive_semantic_edges(cards, max_edges=limit)
    derived_card_ids: set[str] = set()
    for edge in derived_edges:
        derived_card_ids.add(edge["source"])
        derived_card_ids.add(edge["target"])

    card_ids = {card.id for card in cards}

    legacy_edges_rows = (
        await db.execute(
            select(KnowledgeCardLink)
            .where(
                and_(
                    KnowledgeCardLink.is_active.is_(True),
                    or_(
                        KnowledgeCardLink.from_id.in_(card_ids),
                        KnowledgeCardLink.to_id.in_(card_ids),
                    ),
                )
            )
            .limit(limit)
        )
    ).scalars().all()

    legacy_edges: list[dict[str, Any]] = []
    legacy_seen_ids: set[str] = set()
    for edge in legacy_edges_rows:
        if edge.type not in _VALID_RELATION_TYPES:
            continue
        source = str(edge.from_id)
        target = str(edge.to_id)
        legacy_seen_ids.update((source, target))
        legacy_edges.append(
            {
                "id": str(edge.id),
                "source": source,
                "target": target,
                "weight": float(edge.relation_strength or 0.0),
                "relation_type": edge.type,
            }
        )

    edges = derived_edges + legacy_edges

    # ``node.size`` reflects degree so the FE can scale the SVG node by
    # how many connections it has. We always emit size>=1 so isolated
    # nodes still render.
    degree: Counter[str] = Counter()
    for edge in edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1

    nodes: list[dict[str, Any]] = []
    for card in cards:
        node_id = str(card.id)
        nodes.append(
            {
                "id": node_id,
                "label": card.title or "(untitled)",
                "type": "card",
                "size": 1 + degree.get(node_id, 0),
                "object_type": "card",
                "object_id": node_id,
            }
        )

    return success_response(
        {"nodes": nodes, "edges": edges}, request=request
    )


# ---------------------------------------------------------------------------
# v1.4 §3.4 — `/garden/insights/*` (current / list / create / delete / source)
#
# These map to the existing `/api/v1/insights` PRD10 surface so we don't
# re-implement insight storage. The frontend (bridge_v14.js) calls the
# garden-domain path; this router translates that into the shared
# Prd10Insight model. ``connectedNoteIds`` from v1.4's "新建洞察" modal is
# stored under ``Prd10Insight.refs`` so we don't need a new column.
# ---------------------------------------------------------------------------


@router.get("/insights")
async def list_garden_insights(
    request: Request,
    range: str | None = Query(default="month", description="all/week/month"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.4 ``GET /garden/insights`` — recent insights for the garden side panel.

    Returns the same shape as ``GET /api/v1/insights`` (PRD10 §12) so the
    bridge can re-use rendering logic, just narrowed by user + status="ready".
    """
    from agent_os.insights.models import Prd10Insight

    stmt = (
        select(Prd10Insight)
        .where(
            Prd10Insight.user_id == current_user.id,
            Prd10Insight.status == "ready",
        )
        .order_by(Prd10Insight.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [r.to_prd10_dict() for r in rows]
    return success_response(
        {"items": items, "total": len(items), "range": range},
        request=request,
    )


@router.get("/insights/current")
async def get_garden_current_insight(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.4 ``GET /garden/insights/current`` — most recent ready insight."""
    from agent_os.insights.models import Prd10Insight

    stmt = (
        select(Prd10Insight)
        .where(
            Prd10Insight.user_id == current_user.id,
            Prd10Insight.status == "ready",
        )
        .order_by(Prd10Insight.created_at.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalars().first()
    if row is None:
        return success_response({"insight": None}, request=request)
    return success_response({"insight": row.to_prd10_dict()}, request=request)


class _GardenInsightCreate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255)
    connected_note_ids: list[str] = Field(default_factory=list)


@router.post("/insights", status_code=status.HTTP_201_CREATED)
async def create_garden_insight(
    payload: _GardenInsightCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.4 ``POST /garden/insights`` — user creates a custom insight.

    Wired for v1.4's "新建洞察" modal (`data-generate-insight`). Stores the
    selected card / document ids in ``refs`` so the bridge can render the
    "已关联 N 条笔记" footer without a join query.
    """
    from agent_os.insights.models import Prd10Insight

    insight = Prd10Insight(
        user_id=current_user.id,
        title=payload.topic.strip(),
        summary=f"{payload.topic.strip()} · 由用户在数字花园里创建",
        insight_type="connection",
        status="ready",
        extra={
            "connected_note_ids": payload.connected_note_ids,
            "source": "garden_custom",
        },
    )
    db.add(insight)
    await db.commit()
    await db.refresh(insight)
    out = insight.to_prd10_dict()
    out["connectedNoteIds"] = payload.connected_note_ids
    out["connected_note_ids"] = payload.connected_note_ids
    return success_response(out, request=request)


@router.delete("/insights/{insight_id}", status_code=status.HTTP_200_OK)
async def delete_garden_insight(
    insight_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """v1.4 §3.4 ``DELETE /garden/insights/:id`` — drop an insight from the panel.

    Soft-delete: sets status="dismissed" so the row stays auditable but the
    UI list filter (``status=ready``) no longer surfaces it.
    """
    import uuid as _uuid

    from agent_os.insights.models import Prd10Insight

    try:
        iid = _uuid.UUID(insight_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "Invalid insight_id"},
        )

    insight = (
        await db.execute(
            select(Prd10Insight).where(
                Prd10Insight.id == iid,
                Prd10Insight.user_id == current_user.id,
            )
        )
    ).scalars().first()
    if insight is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Insight not found"},
        )
    if insight.status != "dismissed":
        insight.status = "dismissed"
        await db.commit()
    return success_response({"id": str(iid), "deleted": True}, request=request)


