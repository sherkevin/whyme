"""Shared automatic folder routing for generated KB documents."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.kb.models import Folder


_GENERIC_TAGS = {
    "ai",
    "ai 生成",
    "ai 对话",
    "mydow ai",
    "skill",
    "skills",
    "知识库",
    "灵感",
    "自动归档",
}


@dataclass(slots=True)
class GeneratedDocumentRoute:
    folder_id: uuid.UUID | None
    folder_name: str
    title: str
    summary: str
    tags: list[str]
    folder_hint: str
    used_llm: bool
    model: str


def _clean_label(value: str | None, *, limit: int = 40) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    text = re.sub(r"[\\/:*?\"<>|#]+", "", text).strip(" .-_")
    return text[:limit].strip()


def _first_routing_tag(tags: list[str]) -> str:
    for tag in tags:
        cleaned = _clean_label(tag, limit=32)
        if not cleaned:
            continue
        if cleaned.lower() in _GENERIC_TAGS:
            continue
        return cleaned
    return ""


async def _load_or_create_folder(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    name: str,
) -> Folder | None:
    folder_name = _clean_label(name) or "自动归档"
    existing = (
        await db.execute(
            select(Folder).where(
                Folder.user_id == user_id,
                Folder.deleted_at.is_(None),
                Folder.name == folder_name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    folder = Folder(
        user_id=user_id,
        workspace_id=workspace_id,
        name=folder_name,
        description="AI 自动归类创建",
        icon="sparkles",
        color="#8ea2ff",
    )
    db.add(folder)
    await db.flush()
    return folder


async def route_generated_document(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    content: str,
    fallback_title: str | None = None,
    hint_tags: list[str] | None = None,
    explicit_folder_id: uuid.UUID | None = None,
) -> GeneratedDocumentRoute:
    """Resolve title/summary/tags/folder for generated KB documents.

    Rule: if a user explicitly selects a knowledge-base folder, respect it.
    Otherwise ask the real capture enrichment pipeline to produce
    title/summary/tags/folder_hint, then match or create the destination
    folder from that hint. If the provider returns no folder hint, fall back to
    the first meaningful AI tag, and finally to a single "自动归档" folder.
    """

    raw_content = str(content or "").strip()
    tags = [str(t).strip() for t in (hint_tags or []) if str(t).strip()]
    fallback = _clean_label(fallback_title, limit=120) or "未命名文档"
    if explicit_folder_id is not None:
        return GeneratedDocumentRoute(
            folder_id=explicit_folder_id,
            folder_name="",
            title=fallback,
            summary=raw_content[:500],
            tags=tags,
            folder_hint="",
            used_llm=False,
            model="",
        )

    from agent_os.capture.llm_pipeline import enrich_capture_with_llm

    enrichment = await enrich_capture_with_llm(
        db,
        user_id=user_id,
        content=raw_content or fallback,
        fallback_title=fallback,
        hint_tags=tags,
        target_folder_id=None,
    )
    final_tags = list(enrichment.tags or tags or [])
    folder_id = enrichment.folder_id
    folder_name = enrichment.folder_name or ""

    if folder_id is None:
        route_name = (
            _clean_label(enrichment.folder_hint)
            or _first_routing_tag(final_tags)
            or "自动归档"
        )
        folder = await _load_or_create_folder(
            db,
            user_id=user_id,
            workspace_id=workspace_id,
            name=route_name,
        )
        if folder is not None:
            folder_id = folder.id
            folder_name = folder.name or route_name

    return GeneratedDocumentRoute(
        folder_id=folder_id,
        folder_name=folder_name,
        title=(enrichment.title or fallback).strip() or fallback,
        summary=(enrichment.summary or raw_content[:500]).strip(),
        tags=final_tags,
        folder_hint=enrichment.folder_hint or folder_name,
        used_llm=bool(enrichment.used_llm),
        model=enrichment.model or "",
    )
