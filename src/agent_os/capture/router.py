"""PRD10 ``/api/v1/capture/*`` and ``/api/v1/uploads/*`` endpoints (§8).

Implements the synchronous side of PRD10's capture loop: the API persists an
``InboxItem`` and a queued ``Job`` immediately and returns the IDs, while the
heavy lifting (parsing, summarizing, indexing) is owned by background workers
that read from the same job table. V1 ships the persistence + envelope; later
slices wire actual workers.

For local development we don't run a real object store. ``POST /uploads/presign``
returns a pseudo presigned URL pointing back at this server's
``/api/v1/uploads/local/{upload_id}`` endpoint. ``POST /capture/file/commit``
treats any URL whose host is unknown as already-stored and just records the
``Source`` row.
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlparse

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.ai.llm_provider import is_llm_enabled
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.capture.llm_pipeline import (
    enrich_capture_with_llm,
    patch_card_with_enrichment,
)
from agent_os.capture.link_service import (
    build_link_enrichment_content,
    fetch_link_content,
    link_source_extra,
    merge_capture_tags,
)
from agent_os.capture.pipeline import reload_job, simulate_failure, simulate_processing
from agent_os.common import ApiErrorCode, error_json_response, paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.inbox.prd10_models import (
    InboxItemPriority,
    InboxItemProcessingStatus,
    InboxItemStatus,
    InboxItemType,
    Prd10InboxItem,
)
from agent_os.jobs import JobType, create_job
from agent_os.kb.models import Document, DocumentStatus, DocumentType
from agent_os.knowledge.models import Card
from agent_os.sources.models import Source, SourceType
from agent_os.uploads.presign import get_default_backend

router = APIRouter(prefix="/api/v1", tags=["Capture"])
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas (request bodies)
# ---------------------------------------------------------------------------


class CaptureTextRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=20000)
    title: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list)
    target_folder_id: uuid.UUID | None = None
    auto_process: bool = True
    priority: str = Field(default=InboxItemPriority.NORMAL.value)
    type: str | None = Field(
        default=None,
        description=(
            "Optional InboxItem.type override. Defaults to ``text``. Accepts "
            "any PRD10 §5.3 type, including ``manual_task`` for tasks captured "
            "from the home text input."
        ),
    )
    simulate_failure: str | None = Field(default=None, alias="_simulate_failure")

    model_config = {"populate_by_name": True}


class CaptureLinkRequest(BaseModel):
    url: HttpUrl
    note: str | None = Field(default=None, max_length=10000)
    tags: list[str] = Field(default_factory=list)
    target_folder_id: uuid.UUID | None = None
    auto_process: bool = True
    simulate_failure: str | None = Field(default=None, alias="_simulate_failure")

    model_config = {"populate_by_name": True}


class PresignRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=500)
    mime_type: str = Field(..., min_length=1, max_length=200)
    size_bytes: int = Field(..., ge=1, le=1024 * 1024 * 1024)


class FileCommitRequest(BaseModel):
    upload_id: uuid.UUID
    filename: str = Field(..., min_length=1, max_length=500)
    mime_type: str = Field(..., min_length=1, max_length=200)
    size_bytes: int = Field(..., ge=1)
    target_folder_id: uuid.UUID | None = None
    auto_process: bool = True
    checksum: str | None = Field(default=None, max_length=128)
    # Test-only hook: when ``simulate_failure`` is set the V1 pseudo-worker
    # writes a ``failed`` outcome and a PRD10 §15 ``upload_failed`` /
    # ``job_failed`` notification. The field is private (prefixed with an
    # underscore on the wire) so the public OpenAPI doesn't advertise it.
    simulate_failure: str | None = Field(default=None, alias="_simulate_failure")

    model_config = {"populate_by_name": True}


class InboxItemPatch(BaseModel):
    """PRD10 §8.6 ``PATCH /api/v1/inbox/{id}`` body.

    All fields optional; missing fields are left untouched. ``status`` accepts
    the PRD10 §5.3 ``InboxItemStatus`` enum.
    """

    status: str | None = None
    tags: list[str] | None = None
    target_folder_id: uuid.UUID | None = None
    priority: str | None = None
    title: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/capture/text")
async def capture_text(
    payload: CaptureTextRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """§17.1 — Create an InboxItem + LLM-enriched Card.

    The original content stays in ``inbox_item.raw_content``. When
    ``auto_process=True`` we call the LLM enrichment helper to derive a
    real title, abstract, and tags. The tags are merged with whatever the
    user supplied, and ``folder_hint`` is fuzzy-matched against the user's
    KB folders so the resulting card is dropped directly into the right
    bucket. LLM failures fall back to a deterministic heuristic so the
    capture path never blocks.
    """

    _ensure_priority(payload.priority)
    inbox_type = _normalize_inbox_type(payload.type)

    from agent_os.capture.llm_pipeline import _heuristic_enrichment

    # §16.1 — Fast path: never block the POST on LLM. We seed Card+Document
    # with the deterministic heuristic immediately (sub-100ms) and then
    # schedule a background ``patch_card_with_enrichment`` task that talks
    # to the real LLM and PATCHes title/summary/tags/folder when done. The
    # frontend can refresh ``/feed`` (or listen on the SSE notifications
    # channel) to pick up the LLM-improved card a few seconds later. This
    # mirrors how mature open-source LLM apps (LangChain agents, LlamaIndex
    # ingestion, Haystack pipelines) handle slow LLM calls — never on the
    # critical path of user-facing writes.
    enrichment = _heuristic_enrichment(
        payload.content, payload.title, list(payload.tags or [])
    )
    if (
        payload.auto_process
        and not payload.simulate_failure
        and inbox_type == InboxItemType.TEXT.value
        and is_llm_enabled()
    ):
        enrichment = await enrich_capture_with_llm(
            db,
            user_id=current_user.id,
            content=payload.content,
            fallback_title=payload.title,
            hint_tags=list(payload.tags or []),
            target_folder_id=payload.target_folder_id,
        )
    if payload.target_folder_id is not None:
        enrichment.folder_id = payload.target_folder_id
    schedule_async_llm = (
        payload.auto_process
        and not payload.simulate_failure
        and inbox_type == InboxItemType.TEXT.value
        and is_llm_enabled()
        and not bool(getattr(enrichment, "used_llm", False))
    )

    enriched_title = (
        (payload.title or "").strip() or (enrichment.title or None)
    )
    merged_tags: list[str] = []
    for t in list(payload.tags or []) + list(enrichment.tags or []):
        if t and t not in merged_tags:
            merged_tags.append(t)
    merged_tags = merged_tags[:8]

    target_folder_id = payload.target_folder_id
    if (
        target_folder_id is None
        and getattr(enrichment, "folder_id", None) is not None
    ):
        target_folder_id = enrichment.folder_id

    resolved_content_type = getattr(enrichment, "content_type", "note") or "note"

    inbox = Prd10InboxItem(
        user_id=current_user.id,
        type=inbox_type,
        title=enriched_title,
        raw_content=payload.content,
        target_folder_id=target_folder_id,
        status=InboxItemStatus.RECEIVED.value,
        processing_status=(
            InboxItemProcessingStatus.QUEUED.value
            if payload.auto_process
            else InboxItemProcessingStatus.COMPLETED.value
        ),
        priority=payload.priority,
        auto_process=payload.auto_process,
        tags=merged_tags,
    )
    db.add(inbox)
    await db.flush()

    document: Document | None = None
    if (
        payload.auto_process
        and inbox_type == InboxItemType.TEXT.value
        and not payload.simulate_failure
    ):
        summary_for_doc = (
            enrichment.summary
            if enrichment and enrichment.summary
            else _simple_summary(payload.title, payload.content)
        )
        document = Document(
            user_id=current_user.id,
            folder_id=target_folder_id,
            source_id=None,
            title=enriched_title or "未命名灵感",
            summary=summary_for_doc,
            content=payload.content,
            document_type=DocumentType.NOTE.value,
            status=DocumentStatus.PROCESSING.value,
            tags=merged_tags,
            extra={
                "kind": "capture_text",
                "inbox_item_id": str(inbox.id),
                "llm_used": bool(getattr(enrichment, "used_llm", False)),
                "model": getattr(enrichment, "model", "") or "",
            },
        )
        db.add(document)
        await db.flush()

    job: Any = None
    card: Card | None = None
    if payload.auto_process:
        job = await create_job(
            db,
            user_id=current_user.id,
            job_type=JobType.SUMMARIZE,
            payload={
                "kind": "capture_text",
                "inbox_item_id": str(inbox.id),
                "document_id": str(document.id) if document else None,
                "llm_used": bool(getattr(enrichment, "used_llm", False)),
            },
            correlation_id=f"inbox:{inbox.id}",
        )
        inbox.job_id = job.id

        if payload.simulate_failure:
            await simulate_failure(
                db,
                inbox_item=inbox,
                job=job,
                message=payload.simulate_failure,
            )
        else:
            summary_text = (
                enrichment.summary
                if enrichment and enrichment.summary
                else _simple_summary(payload.title, payload.content)
            )
            folder_label = (
                getattr(enrichment, "folder_name", None)
                or getattr(enrichment, "folder_hint", None)
                or None
            )
            notif_title = "AI 已整理灵感卡片"
            if folder_label:
                notif_content = (
                    f"AI 已为「{enriched_title or '新灵感'}」生成摘要，"
                    f"归入「{folder_label}」"
                )
            else:
                notif_content = summary_text or "记录已整理完成"
            card = await simulate_processing(
                db,
                inbox_item=inbox,
                job=job,
                document=document,
                summary=summary_text,
                entities=list(getattr(enrichment, "entities", None) or []),
                content_type=resolved_content_type,
                folder_id=target_folder_id,
                notification_title=notif_title,
                notification_content=notif_content,
            )

    await db.commit()
    await db.refresh(inbox)
    if document is not None:
        await db.refresh(document)

    if schedule_async_llm:
        # Starlette runs BackgroundTasks *after* the response is sent to the
        # client — safer than ``asyncio.create_task`` for fire-and-forget work
        # (no "task exception was never retrieved", runs after commit visible).
        card_id_for_patch: Any | None = None
        try:
            card_q = await db.execute(
                select(Card).where(
                    Card.inbox_item_id == inbox.id,
                    Card.user_id == current_user.id,
                )
            )
            card_row = card_q.scalar_one_or_none()
            if card_row is not None:
                card_id_for_patch = card_row.id
        except Exception:
            _log.exception(
                "[capture.text] async LLM: card lookup failed inbox=%s", inbox.id
            )

        doc_id_for_patch = document.id if document is not None else None
        if card_id_for_patch is None and doc_id_for_patch is None:
            _log.warning(
                "[capture.text] async LLM skipped: no card_id or document_id "
                "for inbox=%s",
                inbox.id,
            )
        else:
            background_tasks.add_task(
                patch_card_with_enrichment,
                user_id=current_user.id,
                inbox_item_id=inbox.id,
                card_id=card_id_for_patch,
                document_id=doc_id_for_patch,
                content=payload.content,
                fallback_title=payload.title,
                hint_tags=list(payload.tags or []),
            )

    job_dict = await reload_job(db, inbox.job_id)
    response = {
        "inbox_item": inbox.to_capture_response(),
        "job": job_dict,
    }
    if document is not None:
        response["document_id"] = str(document.id)
    if card is not None:
        card_payload = card.to_prd10_dict()
        card_payload["content"] = card.content
        response["card_id"] = str(card.id)
        response["card"] = card_payload
    response["enrichment"] = {
        "title": getattr(enrichment, "title", None),
        "summary": getattr(enrichment, "summary", None),
        "tags": list(getattr(enrichment, "tags", None) or []),
        "folder_hint": getattr(enrichment, "folder_hint", None),
        "folder_id": (
            str(enrichment.folder_id)
            if getattr(enrichment, "folder_id", None)
            else None
        ),
        "folder_name": getattr(enrichment, "folder_name", None),
        "content_type": getattr(enrichment, "content_type", "note"),
        "used_llm": bool(getattr(enrichment, "used_llm", False)),
        "model": getattr(enrichment, "model", "") or "",
        "entities": list(getattr(enrichment, "entities", None) or []),
    }
    return success_response(response, request=request)


@router.post("/capture/link")
async def capture_link(
    payload: CaptureLinkRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an InboxItem + Source(link) + queued parse job.

    §17.1 — Like ``/capture/text``, when ``auto_process=True`` and the LLM is
    enabled we feed the note + URL into the enrichment helper so the resulting
    Card has a real title / summary / tags + a fuzzy-matched KB folder. If
    the LLM is off (or the call fails) the helper returns a deterministic
    placeholder so the path never blocks.
    """

    source = Source(
        user_id=current_user.id,
        source_type=SourceType.LINK.value,
        name=str(payload.url),
        url=str(payload.url),
        parse_status="pending",
        extra={"note": payload.note} if payload.note else {},
    )
    db.add(source)
    await db.flush()

    fetched = None
    if payload.auto_process and not payload.simulate_failure:
        fetched = await fetch_link_content(str(payload.url))
        if fetched is not None:
            source.name = fetched.title or source.name
            source.extra = {**(source.extra or {}), **link_source_extra(note=payload.note, fetched=fetched)}

    enrichment = None
    if payload.auto_process and not payload.simulate_failure:
        enrichment = await enrich_capture_with_llm(
            db,
            user_id=current_user.id,
            content=build_link_enrichment_content(
                url=str(payload.url),
                note=payload.note,
                fetched=fetched,
            ),
            fallback_title=payload.note or (fetched.title if fetched else None),
            hint_tags=list(payload.tags or []),
        )

    # User note (if provided) wins over LLM-derived title for parity with
    # `/capture/text`. LLM is only used to fill the gaps.
    enriched_title = (
        (payload.note or "").strip()
        or (enrichment.title if enrichment else None)
        or None
    )
    merged_tags = merge_capture_tags(
        list(payload.tags or []),
        list(enrichment.tags if enrichment and enrichment.tags else []),
    )

    target_folder_id = payload.target_folder_id
    if (
        target_folder_id is None
        and enrichment is not None
        and enrichment.folder_id is not None
    ):
        target_folder_id = enrichment.folder_id

    inbox = Prd10InboxItem(
        user_id=current_user.id,
        type=InboxItemType.LINK.value,
        title=enriched_title,
        raw_content=str(payload.url),
        source_url=str(payload.url),
        source_id=source.id,
        target_folder_id=target_folder_id,
        status=InboxItemStatus.RECEIVED.value,
        processing_status=(
            InboxItemProcessingStatus.QUEUED.value
            if payload.auto_process
            else InboxItemProcessingStatus.COMPLETED.value
        ),
        priority=InboxItemPriority.NORMAL.value,
        auto_process=payload.auto_process,
        tags=merged_tags,
    )
    db.add(inbox)
    await db.flush()

    document: Document | None = None
    if payload.auto_process and not payload.simulate_failure and fetched is not None:
        summary_for_doc = (
            enrichment.summary
            if enrichment and enrichment.summary
            else (fetched.description or (fetched.text[:240] if fetched.text else None))
        )
        document = Document(
            user_id=current_user.id,
            folder_id=target_folder_id,
            source_id=source.id,
            title=enriched_title or fetched.title or str(payload.url),
            summary=summary_for_doc,
            content=fetched.text or str(payload.url),
            document_type=DocumentType.LINK.value,
            status=DocumentStatus.PROCESSING.value,
            tags=merged_tags,
            extra={
                "kind": "capture_link",
                "url": str(payload.url),
                "note": payload.note,
                "fetched_title": fetched.title,
                "description": fetched.description,
                "llm_used": bool(enrichment and enrichment.used_llm),
                "model": getattr(enrichment, "model", "") if enrichment else "",
            },
        )
        db.add(document)
        await db.flush()

    job: Any = None
    card: Card | None = None
    fetch_status = "pending"
    if payload.auto_process:
        job = await create_job(
            db,
            user_id=current_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "capture_link",
                "inbox_item_id": str(inbox.id),
                "source_id": str(source.id),
                "document_id": str(document.id) if document else None,
                "url": str(payload.url),
                "llm_used": bool(enrichment and enrichment.used_llm),
            },
            correlation_id=f"inbox:{inbox.id}",
        )
        inbox.job_id = job.id
        if payload.simulate_failure:
            await simulate_failure(
                db,
                inbox_item=inbox,
                job=job,
                source=source,
                message=payload.simulate_failure,
            )
            fetch_status = "failed"
        elif fetched is None:
            await simulate_failure(
                db,
                inbox_item=inbox,
                job=job,
                source=source,
                document=document,
                message=f"Unable to fetch URL: {payload.url}",
            )
            fetch_status = "failed"
        else:
            summary_text = (
                enrichment.summary
                if enrichment and enrichment.summary
                else (fetched.description or payload.note or fetched.text[:240] or str(payload.url))
            )
            inbox.raw_content = fetched.text or str(payload.url)
            card = await simulate_processing(
                db,
                inbox_item=inbox,
                job=job,
                source=source,
                document=document,
                summary=summary_text,
                entities=list(getattr(enrichment, "entities", None) or []),
                content_type=getattr(enrichment, "content_type", "note") if enrichment else "note",
                folder_id=target_folder_id,
            )
            fetch_status = "completed"

    await db.commit()
    await db.refresh(inbox)
    if document is not None:
        await db.refresh(document)
    job_dict = await reload_job(db, inbox.job_id)

    response = {
        "inbox_item_id": str(inbox.id),
        "source_id": str(source.id),
        "document_id": str(document.id) if document else None,
        "card_id": str(card.id) if card else None,
        "job_id": str(inbox.job_id) if inbox.job_id else None,
        "job": job_dict,
        "fetch_status": fetch_status,
        "fetched_title": fetched.title if fetched else "",
        "fetched_description": fetched.description if fetched else "",
        "content_excerpt": (fetched.text if fetched else "")[:1000],
    }
    if card is not None:
        card_payload = card.to_prd10_dict()
        card_payload["content"] = card.content
        card_payload["source_url"] = str(payload.url)
        card_payload["document_type"] = DocumentType.LINK.value
        response["card"] = card_payload
    if enrichment is not None:
        response["enrichment"] = {
            "title": enrichment.title,
            "summary": enrichment.summary,
            "tags": enrichment.tags,
            "folder_hint": enrichment.folder_hint,
            "folder_id": str(enrichment.folder_id) if enrichment.folder_id else None,
            "folder_name": enrichment.folder_name,
            "content_type": getattr(enrichment, "content_type", "note"),
            "used_llm": enrichment.used_llm,
            "model": getattr(enrichment, "model", "") or "",
            "entities": list(getattr(enrichment, "entities", None) or []),
        }
    return success_response(response, request=request)


@router.post("/uploads/presign")
async def presign_upload(
    payload: PresignRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """PRD10 §8.3 / §8.9 — presigned upload descriptor.

    Uses :mod:`agent_os.uploads.presign` (``local`` or ``s3`` via env). Clients
    ``PUT`` or ``POST`` raw bytes to ``upload_url`` and echo ``headers`` /
    ``fields`` as returned.
    """

    base = str(request.base_url).rstrip("/")
    try:
        result = get_default_backend().presign(
            user_id=current_user.id,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            base_url=base,
        )
    except ValueError as exc:
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            str(exc),
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except RuntimeError as exc:
        return error_json_response(
            ApiErrorCode.INTERNAL_ERROR,
            str(exc),
            request=request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return success_response(result.to_payload(), request=request)


@router.post("/capture/file/commit")
async def capture_file_commit(
    payload: FileCommitRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist the upload metadata and queue parsing/index jobs.

    If a real ``PUT /api/v1/uploads/local/{upload_id}`` happened first, the
    Source row already exists with ``parse_status='uploaded'`` and the bytes
    on disk; we only need to merge the user-declared metadata. Otherwise we
    fall back to recording the metadata against a brand-new ``Source`` row
    (useful for tests or pre-existing remote URLs that never went through
    our local storage).
    """

    base = str(request.base_url).rstrip("/")
    file_url = f"{base}/api/v1/uploads/local/{payload.upload_id}/raw"

    existing_source = (
        await db.execute(
            select(Source).where(
                Source.id == payload.upload_id,
                Source.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if existing_source is not None:
        # Real upload happened — keep the storage_path/size/url already on
        # the row (commit only refreshes the user-declared metadata).
        source = existing_source
        source.name = payload.filename or source.name
        source.mime_type = payload.mime_type or source.mime_type
        if payload.checksum:
            source.checksum = payload.checksum
        source.parse_status = "pending"
        source.url = file_url
    else:
        source = Source(
            id=payload.upload_id,
            user_id=current_user.id,
            source_type=_source_type_for_mime(payload.mime_type),
            name=payload.filename,
            url=file_url,
            storage_path=str(payload.upload_id),
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            checksum=payload.checksum,
            parse_status="pending",
        )
        db.add(source)
    await db.flush()

    document = Document(
        user_id=current_user.id,
        folder_id=payload.target_folder_id,
        source_id=source.id,
        title=payload.filename,
        document_type=_document_type_for_mime(payload.mime_type),
        status=DocumentStatus.PROCESSING.value if payload.auto_process else DocumentStatus.READY.value,
        tags=[],
        extra={"upload_id": str(payload.upload_id)},
    )
    db.add(document)
    await db.flush()

    inbox = Prd10InboxItem(
        user_id=current_user.id,
        type=InboxItemType.FILE.value,
        title=payload.filename,
        raw_content=None,
        source_url=file_url,
        source_id=source.id,
        target_folder_id=payload.target_folder_id,
        status=InboxItemStatus.PROCESSING.value if payload.auto_process else InboxItemStatus.RECEIVED.value,
        processing_status=(
            InboxItemProcessingStatus.QUEUED.value
            if payload.auto_process
            else InboxItemProcessingStatus.COMPLETED.value
        ),
        priority=InboxItemPriority.NORMAL.value,
        auto_process=payload.auto_process,
    )
    db.add(inbox)
    await db.flush()

    job: Any = None
    if payload.auto_process:
        job = await create_job(
            db,
            user_id=current_user.id,
            job_type=JobType.PARSE_FILE,
            payload={
                "kind": "capture_file",
                "inbox_item_id": str(inbox.id),
                "source_id": str(source.id),
                "document_id": str(document.id),
                "filename": payload.filename,
                "mime_type": payload.mime_type,
                "size_bytes": payload.size_bytes,
            },
            correlation_id=f"inbox:{inbox.id}",
        )
        inbox.job_id = job.id
        if payload.simulate_failure:
            await simulate_failure(
                db,
                inbox_item=inbox,
                job=job,
                source=source,
                document=document,
                message=payload.simulate_failure,
            )
        else:
            await simulate_processing(
                db,
                inbox_item=inbox,
                job=job,
                source=source,
                document=document,
                summary=f"已收到 {payload.filename}",
            )

    await db.commit()
    await db.refresh(inbox)
    await db.refresh(document)

    job_dict = await reload_job(db, inbox.job_id)
    job_id = str(inbox.job_id) if inbox.job_id else None
    job_status = job_dict["status"] if job_dict else (
        DocumentStatus.READY.value if not payload.auto_process else "completed"
    )

    return success_response(
        {
            "source_id": str(source.id),
            "document_id": str(document.id),
            "inbox_item_id": str(inbox.id),
            "job_id": job_id,
            "status": job_status,
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# Inbox listing / patching (PRD10 §8.5–§8.6)
# ---------------------------------------------------------------------------


@router.get("/inbox")
async def list_inbox_items(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """PRD10 §8.5 ``GET /api/v1/inbox``."""

    base = select(Prd10InboxItem).where(Prd10InboxItem.user_id == current_user.id)
    count_base = select(func.count(Prd10InboxItem.id)).where(
        Prd10InboxItem.user_id == current_user.id
    )

    if type:
        valid = {t.value for t in InboxItemType}
        if type not in valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": ApiErrorCode.VALIDATION_ERROR.value,
                    "message": f"Invalid type '{type}'",
                    "details": {"allowed": sorted(valid)},
                },
            )
        base = base.where(Prd10InboxItem.type == type)
        count_base = count_base.where(Prd10InboxItem.type == type)

    if status_filter:
        valid = {s.value for s in InboxItemStatus}
        if status_filter not in valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": ApiErrorCode.VALIDATION_ERROR.value,
                    "message": f"Invalid status '{status_filter}'",
                    "details": {"allowed": sorted(valid)},
                },
            )
        base = base.where(Prd10InboxItem.status == status_filter)
        count_base = count_base.where(Prd10InboxItem.status == status_filter)

    if keyword:
        like = f"%{keyword}%"
        cond = or_(
            Prd10InboxItem.title.ilike(like),
            Prd10InboxItem.raw_content.ilike(like),
        )
        base = base.where(cond)
        count_base = count_base.where(cond)

    total = (await db.execute(count_base)).scalar_one() or 0
    rows = (
        await db.execute(
            base.order_by(
                Prd10InboxItem.created_at.desc(),
                Prd10InboxItem.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return paginated_response(
        [item.to_prd10_dict() for item in rows],
        page=page,
        page_size=page_size,
        total=int(total),
        request=request,
    )


@router.patch("/inbox/{item_id}")
async def patch_inbox_item(
    item_id: uuid.UUID,
    payload: InboxItemPatch,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD10 §8.6 ``PATCH /api/v1/inbox/{id}``."""

    item = (
        await db.execute(
            select(Prd10InboxItem).where(
                Prd10InboxItem.id == item_id,
                Prd10InboxItem.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Inbox item not found",
            },
        )

    updates = payload.model_dump(exclude_unset=True)

    if "status" in updates:
        valid = {s.value for s in InboxItemStatus}
        if updates["status"] not in valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": ApiErrorCode.VALIDATION_ERROR.value,
                    "message": f"Invalid status '{updates['status']}'",
                    "details": {"allowed": sorted(valid)},
                },
            )
        item.status = updates["status"]

    if "priority" in updates:
        _ensure_priority(updates["priority"])
        item.priority = updates["priority"]

    if "tags" in updates:
        item.tags = list(updates["tags"] or [])

    if "title" in updates:
        item.title = updates["title"]

    if "target_folder_id" in updates:
        item.target_folder_id = updates["target_folder_id"]

    await db.commit()
    await db.refresh(item)

    return success_response(item.to_prd10_dict(), request=request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_priority(value: str) -> None:
    valid = {p.value for p in InboxItemPriority}
    if value not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": f"Invalid priority '{value}'",
                "details": {"allowed": sorted(valid)},
            },
        )


def _normalize_inbox_type(value: str | None) -> str:
    if not value:
        return InboxItemType.TEXT.value
    if value == "voice":
        return InboxItemType.TEXT.value
    valid = {t.value for t in InboxItemType}
    if value not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": f"Invalid type '{value}'",
                "details": {"allowed": sorted(valid)},
            },
        )
    return value


def _source_type_for_mime(mime: str) -> str:
    mime = (mime or "").lower()
    if mime.startswith("image/"):
        return SourceType.IMAGE.value
    if mime.startswith("audio/"):
        return SourceType.AUDIO.value
    return SourceType.FILE.value


def _document_type_for_mime(mime: str) -> str:
    mime = (mime or "").lower()
    if mime == "application/pdf":
        return DocumentType.PDF.value
    if mime.startswith("image/"):
        return DocumentType.IMAGE.value
    if mime.startswith("audio/"):
        return DocumentType.AUDIO.value
    if mime in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }:
        return DocumentType.DOCX.value
    if mime in {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
    }:
        return DocumentType.PPTX.value
    if mime in {"text/markdown", "text/x-markdown"}:
        return DocumentType.MARKDOWN.value
    if mime.startswith("text/"):
        return DocumentType.TEXT.value
    return DocumentType.NOTE.value


def _simple_summary(title: str | None, content: str) -> str:
    """V1 placeholder summarizer: pick title or first 80 chars of content."""

    base = (title or "").strip() or content.strip()
    return base[:200]


# Best-effort import to avoid `unused` lint when urlparse stays available.
_ = urlparse
