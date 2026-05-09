"""PRD10 Knowledge Base API router (§10)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.kb.auto_route import route_generated_document
from agent_os.kb.models import Chunk, Document, DocumentStatus, Folder
from agent_os.knowledge.models import Card
from agent_os.sources.models import Source

router = APIRouter(prefix="/api/v1/kb", tags=["Knowledge Base"])


class CreateFolderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    parent_id: uuid.UUID | None = None
    color: str | None = Field(default=None, max_length=20)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int = 0
    is_favorite: bool = False


class UpdateFolderRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    parent_id: uuid.UUID | None = None
    color: str | None = Field(default=None, max_length=20)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None
    is_favorite: bool | None = None


class DeleteFolderRequest(BaseModel):
    strategy: Literal["move_to_root", "delete_children"] = "move_to_root"


class UpdateDocumentRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    summary: str | None = None
    content: str | None = None
    folder_id: uuid.UUID | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None


class CreateDocumentRequest(BaseModel):
    """PRD10 §10.x — create a manually-authored document.

    Title is the only hard requirement. ``template`` lets the SPA's
    "新建文档" modal pre-fill the body with one of three skeletons; when
    ``content`` is also provided, the explicit content wins.
    """

    title: str = Field(..., min_length=1, max_length=500)
    summary: str | None = Field(default=None, max_length=2000)
    content: str | None = Field(default=None, max_length=200_000)
    folder_id: uuid.UUID | None = None
    document_type: Literal[
        "note", "markdown", "text", "pdf", "docx", "pptx", "link", "audio", "image"
    ] = "note"
    tags: list[str] | None = None
    is_favorite: bool = False
    template: Literal[
        "blank", "research_report", "solution_outline"
    ] | None = None


_DOCUMENT_TEMPLATES: dict[str, str] = {
    # Keys mirror the SPA's biz-modal `<select>` options. The bridge maps
    # display labels (空白文档 / 研究报告 / 方案框架) → these enum values.
    "blank": "",
    "research_report": (
        "# 研究目标\n\n"
        "（用一句话描述这次研究要回答的核心问题。）\n\n"
        "## 背景\n\n"
        "## 关键发现\n\n- \n- \n- \n\n"
        "## 数据与方法\n\n"
        "## 结论与下一步\n"
    ),
    "solution_outline": (
        "# 方案概述\n\n"
        "## 现状与问题\n\n"
        "## 推荐方案\n\n"
        "## 关键里程碑\n\n- 第 1 周：\n- 第 2 周：\n- 第 3 周：\n\n"
        "## 风险与缓解\n\n"
        "## 资源估算\n"
    ),
}


class MoveDocumentRequest(BaseModel):
    target_folder_id: uuid.UUID | None = None


class MoveFolderRequest(BaseModel):
    """PRD10 §10.4 explicit folder-move payload.

    ``parent_id=None`` moves the folder to the workspace root. The same
    transition is also reachable via ``PATCH /folders/{id}`` with the same
    field; the dedicated endpoint is provided as a more explicit/SPA-friendly
    surface and to match the PRD10 §25.1 first-screen API matrix.
    """

    parent_id: uuid.UUID | None = None


class RenameFolderRequest(BaseModel):
    """PRD10 §10.4 explicit folder-rename payload.

    ``PATCH /folders/{id}`` already accepts a ``name`` field. This dedicated
    endpoint is provided for clarity in the SPA's right-click menu wiring.
    """

    name: str = Field(..., min_length=1, max_length=200)


@router.get("/overview")
async def get_overview(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return PRD10 §10.1 KB overview stats and small previews."""

    folder_count = await _count(
        db,
        select(func.count(Folder.id)).where(
            Folder.user_id == current_user.id,
            Folder.deleted_at.is_(None),
        ),
    )
    document_count = await _count(
        db,
        select(func.count(Document.id)).where(
            Document.user_id == current_user.id,
            Document.deleted_at.is_(None),
        ),
    )
    favorite_count = await _count(
        db,
        select(func.count(Document.id)).where(
            Document.user_id == current_user.id,
            Document.deleted_at.is_(None),
            Document.is_favorite.is_(True),
        ),
    )

    recent_documents = (
        await db.execute(
            select(Document)
            .where(Document.user_id == current_user.id, Document.deleted_at.is_(None))
            .order_by(Document.updated_at.desc())
            .limit(5)
        )
    ).scalars().all()
    favorite_folders = (
        await db.execute(
            select(Folder)
            .where(
                Folder.user_id == current_user.id,
                Folder.deleted_at.is_(None),
                Folder.is_favorite.is_(True),
            )
            .order_by(Folder.sort_order.asc(), Folder.updated_at.desc())
            .limit(10)
        )
    ).scalars().all()

    return success_response(
        {
            "stats": {
                "folder_count": folder_count,
                "document_count": document_count,
                "favorite_count": favorite_count,
                "recent_updated_count": len(recent_documents),
            },
            "recent_documents": [d.to_prd10_dict() for d in recent_documents],
            "favorite_folders": [f.to_prd10_dict() for f in favorite_folders],
        },
        request=request,
    )


@router.get("/folders")
async def list_folders(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    parent_id: uuid.UUID | None = Query(default=None),
    keyword: str | None = Query(default=None),
    include_counts: bool = Query(default=False),
    is_favorite: bool | None = Query(
        default=None,
        description="When true, return only folders marked favorite (SPA §7.26).",
    ),
    sort_by: Literal["default", "updated_at"] = Query(
        default="default",
        description="default = sort_order then updated_at; updated_at = recent activity first.",
    ),
):
    stmt = select(Folder).where(
        Folder.user_id == current_user.id,
        Folder.deleted_at.is_(None),
    )
    if parent_id is None:
        stmt = stmt.where(Folder.parent_id.is_(None))
    else:
        stmt = stmt.where(Folder.parent_id == parent_id)
    if keyword:
        stmt = stmt.where(Folder.name.ilike(f"%{keyword}%"))
    if is_favorite is True:
        stmt = stmt.where(Folder.is_favorite.is_(True))

    if sort_by == "updated_at":
        stmt = stmt.order_by(Folder.updated_at.desc())
    else:
        stmt = stmt.order_by(Folder.sort_order.asc(), Folder.updated_at.desc())

    folders = (await db.execute(stmt)).scalars().all()
    items = []
    for folder in folders:
        payload = folder.to_prd10_dict()
        if include_counts:
            payload["document_count"] = await _count(
                db,
                select(func.count(Document.id)).where(
                    Document.user_id == current_user.id,
                    Document.folder_id == folder.id,
                    Document.deleted_at.is_(None),
                ),
            )
            payload["card_count"] = 0
        items.append(payload)

    return success_response({"items": items}, request=request)


@router.get("/folders/{folder_id}")
async def get_folder(
    folder_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_children: bool = Query(default=False),
    include_counts: bool = Query(default=True),
):
    """PRD10 §10.4 single-folder detail.

    Returns the folder payload plus optional document/card counts and an
    optional flat list of its direct children. Used by the SPA / biz
    prototype's folder-detail panel (§15.9 binding).
    """

    folder = await _load_folder(db, folder_id, current_user.id)
    payload = folder.to_prd10_dict()
    if include_counts:
        payload["document_count"] = await _count(
            db,
            select(func.count(Document.id)).where(
                Document.user_id == current_user.id,
                Document.folder_id == folder.id,
                Document.deleted_at.is_(None),
            ),
        )
        payload["card_count"] = await _count(
            db,
            select(func.count(Card.id)).where(
                Card.user_id == current_user.id,
                Card.folder_id == folder.id,
            ),
        )
        payload["subfolder_count"] = await _count(
            db,
            select(func.count(Folder.id)).where(
                Folder.user_id == current_user.id,
                Folder.parent_id == folder.id,
                Folder.deleted_at.is_(None),
            ),
        )
    if include_children:
        children = (
            await db.execute(
                select(Folder)
                .where(
                    Folder.user_id == current_user.id,
                    Folder.parent_id == folder.id,
                    Folder.deleted_at.is_(None),
                )
                .order_by(Folder.sort_order.asc(), Folder.updated_at.desc())
            )
        ).scalars().all()
        payload["children"] = [c.to_prd10_dict() for c in children]
    return success_response(payload, request=request)


@router.post("/folders")
async def create_folder(
    payload: CreateFolderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.parent_id is not None:
        await _load_folder(db, payload.parent_id, current_user.id)

    folder = Folder(
        user_id=current_user.id,
        parent_id=payload.parent_id,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        icon=payload.icon,
        sort_order=payload.sort_order,
        is_favorite=payload.is_favorite,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return success_response(folder.to_prd10_dict(), request=request)


@router.patch("/folders/{folder_id}")
async def update_folder(
    folder_id: uuid.UUID,
    payload: UpdateFolderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = await _load_folder(db, folder_id, current_user.id)
    updates = payload.model_dump(exclude_unset=True)
    if "parent_id" in updates and updates["parent_id"] == folder.id:
        raise _validation_error("Folder cannot be its own parent")
    if updates.get("parent_id") is not None:
        await _load_folder(db, updates["parent_id"], current_user.id)

    for key, value in updates.items():
        setattr(folder, key, value)

    await db.commit()
    await db.refresh(folder)
    return success_response(folder.to_prd10_dict(), request=request)


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: uuid.UUID,
    request: Request,
    payload: DeleteFolderRequest = Body(default=DeleteFolderRequest()),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = await _load_folder(db, folder_id, current_user.id)
    now = datetime.now(UTC)

    documents = (
        await db.execute(
            select(Document).where(
                Document.user_id == current_user.id,
                Document.folder_id == folder.id,
                Document.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for document in documents:
        if payload.strategy == "move_to_root":
            document.folder_id = None
        else:
            document.deleted_at = now

    folder.deleted_at = now
    await db.commit()
    return success_response({"deleted": True, "id": str(folder.id)}, request=request)


@router.post("/folders/{folder_id}/move")
async def move_folder(
    folder_id: uuid.UUID,
    payload: MoveFolderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD10 §10.4 ``POST /api/v1/kb/folders/{id}/move``.

    Moves a folder under a new parent (or to the root when ``parent_id`` is
    ``null``). Equivalent to ``PATCH /folders/{id}`` with the same payload,
    exposed as a dedicated endpoint so the SPA can wire right-click "move"
    actions without ambiguity.
    """

    folder = await _load_folder(db, folder_id, current_user.id)
    target = payload.parent_id

    if target is not None:
        if target == folder.id:
            raise _validation_error("Folder cannot be its own parent")
        # PRD10: prevent moving into a descendant — would create a cycle.
        await _load_folder(db, target, current_user.id)
        if await _is_descendant(db, target, folder.id, current_user.id):
            raise _validation_error(
                "Folder cannot be moved under one of its own descendants"
            )

    folder.parent_id = target
    await db.commit()
    await db.refresh(folder)
    return success_response(folder.to_prd10_dict(), request=request)


@router.post("/folders/{folder_id}/rename")
async def rename_folder(
    folder_id: uuid.UUID,
    payload: RenameFolderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD10 §10.4 ``POST /api/v1/kb/folders/{id}/rename``.

    Renames a folder. Equivalent to ``PATCH /folders/{id}`` with a single
    ``name`` field. Surfaced separately for SPA right-click ergonomics.
    """

    folder = await _load_folder(db, folder_id, current_user.id)
    folder.name = payload.name.strip()
    await db.commit()
    await db.refresh(folder)
    return success_response(folder.to_prd10_dict(), request=request)


@router.get("/documents")
async def list_documents(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    folder_id: uuid.UUID | None = Query(default=None),
    document_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sort_by: Literal["updated_at", "created_at", "title"] = "updated_at",
    sort_order: Literal["desc", "asc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    base = select(Document).where(
        Document.user_id == current_user.id,
        Document.deleted_at.is_(None),
    )
    count_base = select(func.count(Document.id)).where(
        Document.user_id == current_user.id,
        Document.deleted_at.is_(None),
    )

    filters = []
    if folder_id is not None:
        filters.append(Document.folder_id == folder_id)
    if document_type:
        filters.append(Document.document_type == document_type)
    if status:
        filters.append(Document.status == status)
    if keyword:
        filters.append(
            or_(
                Document.title.ilike(f"%{keyword}%"),
                Document.summary.ilike(f"%{keyword}%"),
            )
        )
    for clause in filters:
        base = base.where(clause)
        count_base = count_base.where(clause)

    total = await _count(db, count_base)
    sort_col = getattr(Document, sort_by)
    if sort_order == "desc":
        sort_col = sort_col.desc()
    rows = (
        await db.execute(
            base.order_by(sort_col)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return paginated_response(
        [doc.to_prd10_dict() for doc in rows],
        page=page,
        page_size=page_size,
        total=total,
        request=request,
    )


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: CreateDocumentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD10 §10 — create a manually-authored knowledge-base document.

    Used by the biz-prototype "新建文档" modal (§15.23). Validates that any
    explicit ``folder_id`` belongs to the current user and is not soft-
    deleted. ``template`` populates a starter ``content`` body when no
    explicit content is provided so the document drawer renders something
    immediately. ``word_count`` is derived from the final content.
    """

    if payload.folder_id is not None:
        await _load_folder(db, payload.folder_id, current_user.id)

    explicit_content = payload.content
    if explicit_content is None and payload.template is not None:
        explicit_content = _DOCUMENT_TEMPLATES.get(payload.template, "")
    if explicit_content is None:
        explicit_content = ""

    word_count = len([w for w in explicit_content.split() if w]) if explicit_content else 0
    folder_id = payload.folder_id
    summary = payload.summary
    tags = list(payload.tags or [])
    auto_route_extra: dict[str, object] | None = None
    if folder_id is None and explicit_content.strip():
        route = await route_generated_document(
            db,
            user_id=current_user.id,
            workspace_id=None,
            content=explicit_content,
            fallback_title=payload.title,
            hint_tags=tags,
            explicit_folder_id=None,
        )
        folder_id = route.folder_id
        summary = summary or route.summary
        tags = route.tags or tags
        auto_route_extra = {
            "folder_hint": route.folder_hint,
            "folder_name": route.folder_name,
            "used_llm": route.used_llm,
            "model": route.model,
        }

    document = Document(
        user_id=current_user.id,
        folder_id=folder_id,
        title=payload.title,
        summary=summary,
        content=explicit_content,
        document_type=payload.document_type,
        status=DocumentStatus.READY.value,
        tags=tags,
        extra={
            "created_via": "manual_modal",
            "template": payload.template or "blank",
            **({"auto_route": auto_route_extra} if auto_route_extra else {}),
        },
        is_favorite=payload.is_favorite,
        word_count=word_count,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    body = document.to_prd10_dict(include_content=True)
    if document.folder_id:
        folder = await _load_folder(db, document.folder_id, current_user.id)
        body["folder"] = {"id": str(folder.id), "name": folder.name}
    else:
        body["folder"] = None
    return success_response(body, request=request)


@router.get("/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await _load_document(db, document_id, current_user.id)
    payload = document.to_prd10_dict(include_content=True)

    if document.folder_id:
        folder = await _load_folder(db, document.folder_id, current_user.id)
        payload["folder"] = {"id": str(folder.id), "name": folder.name}
    else:
        payload["folder"] = None

    source = None
    if document.source_id:
        source = (
            await db.execute(
                select(Source).where(
                    Source.id == document.source_id,
                    Source.user_id == current_user.id,
                )
            )
        ).scalar_one_or_none()
    payload["source"] = source.to_prd10_dict() if source else None
    payload["chunks_preview"] = [
        chunk.to_prd10_dict()
        for chunk in (
            await db.execute(
                select(Chunk)
                .where(Chunk.document_id == document.id, Chunk.user_id == current_user.id)
                .order_by(Chunk.chunk_index.asc())
                .limit(3)
            )
        ).scalars().all()
    ]

    # PRD10 §10.7 related_cards: cards that share the same source, the same
    # folder, or at least one tag with this document. Returns up to 5 cards;
    # most-recently created first; soft-deleted cards excluded.
    related_card_stmt = (
        select(Card)
        .where(
            Card.user_id == current_user.id,
            Card.deleted_at.is_(None),
            Card.id != None,  # noqa: E711 — explicit non-null guard
        )
        .order_by(Card.created_at.desc())
        .limit(20)
    )
    related_card_filters: list = []
    if document.source_id is not None:
        related_card_filters.append(Card.source_id == document.source_id)
    if document.folder_id is not None:
        related_card_filters.append(Card.folder_id == document.folder_id)
    if related_card_filters:
        related_card_stmt = related_card_stmt.where(or_(*related_card_filters))

    related_rows = (await db.execute(related_card_stmt)).scalars().all()
    doc_tags = set(getattr(document, "tags", None) or [])
    if doc_tags:
        related_rows = sorted(
            related_rows,
            key=lambda c: len(doc_tags & set(c.tags or [])),
            reverse=True,
        )
    payload["related_cards"] = [
        {
            "id": str(c.id),
            "title": c.title,
            "summary": c.summary,
            "tags": list(c.tags or []),
            "is_favorite": bool(c.is_favorite),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in related_rows[:5]
    ]

    # PRD10 §10.7 ai_suggestions: contextual prompts the SPA can render as
    # quick-action buttons in the document drawer. Always include the
    # generic summary action so even fresh documents have something to show.
    ai_suggestions: list[dict] = [
        {"type": "ask_ai", "label": "让 Mydow AI 总结这份文档", "prompt": f"请总结《{document.title or '该文档'}》的核心要点，并列出 3 条可执行建议。"},
    ]
    if (document.word_count or 0) > 800:
        ai_suggestions.append(
            {
                "type": "create_outline",
                "label": "生成大纲与笔记",
                "prompt": f"请基于《{document.title or '该文档'}》生成一份层级大纲与可复用的学习笔记。",
            }
        )
    if doc_tags:
        ai_suggestions.append(
            {
                "type": "tag_expand",
                "label": "扩写相关主题",
                "prompt": "结合该文档与我已有的知识库，沿用同样的主题扩写 3 条新的灵感。",
                "tags": sorted(doc_tags),
            }
        )
    if (document.status or "") in ("ready", "ready_for_review"):
        ai_suggestions.append(
            {
                "type": "create_tasks",
                "label": "拆成可执行任务",
                "prompt": f"请把《{document.title or '该文档'}》的待办拆成 3-5 条具体任务，给出预估时间和优先级。",
            }
        )
    payload["ai_suggestions"] = ai_suggestions

    return success_response(payload, request=request)


@router.patch("/documents/{document_id}")
async def update_document(
    document_id: uuid.UUID,
    payload: UpdateDocumentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await _load_document(db, document_id, current_user.id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("folder_id") is not None:
        await _load_folder(db, updates["folder_id"], current_user.id)

    for key, value in updates.items():
        setattr(document, key, value)

    await db.commit()
    await db.refresh(document)
    return success_response(document.to_prd10_dict(include_content=True), request=request)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await _load_document(db, document_id, current_user.id)
    document.deleted_at = datetime.now(UTC)
    await db.commit()
    return success_response({"deleted": True, "id": str(document.id)}, request=request)


@router.post("/documents/{document_id}/move")
async def move_document(
    document_id: uuid.UUID,
    payload: MoveDocumentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await _load_document(db, document_id, current_user.id)
    if payload.target_folder_id is not None:
        await _load_folder(db, payload.target_folder_id, current_user.id)

    document.folder_id = payload.target_folder_id
    await db.commit()
    await db.refresh(document)
    return success_response(document.to_prd10_dict(), request=request)


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _load_folder(db: AsyncSession, folder_id: uuid.UUID, user_id: uuid.UUID) -> Folder:
    folder = (
        await db.execute(
            select(Folder).where(
                Folder.id == folder_id,
                Folder.user_id == user_id,
                Folder.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if folder is None:
        raise _not_found("Folder not found")
    return folder


async def _is_descendant(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    ancestor_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    max_depth: int = 32,
) -> bool:
    """Return True if ``candidate_id`` is a (strict) descendant of ``ancestor_id``.

    Walks up from ``candidate_id`` through ``parent_id`` links. ``max_depth``
    is a defensive cap so a corrupted parent chain can't loop forever.
    """

    cur = candidate_id
    seen = set()
    for _ in range(max_depth):
        if cur is None or cur in seen:
            return False
        if cur == ancestor_id:
            return True
        seen.add(cur)
        parent = (
            await db.execute(
                select(Folder.parent_id).where(
                    Folder.id == cur,
                    Folder.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        cur = parent
    return False


async def _load_document(db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    document = (
        await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise _not_found("Document not found")
    return document


def _not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": ApiErrorCode.NOT_FOUND.value, "message": message},
    )


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": ApiErrorCode.VALIDATION_ERROR.value, "message": message},
    )
