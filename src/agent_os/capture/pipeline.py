"""Synchronous "pseudo worker" used by V1 capture endpoints.

PRD10 §30 requires the minimal end-to-end loop (capture → InboxItem → Card /
Document → notification) to be observable by users **today**, before real
background workers exist. This module hides the simulation behind a single
entry point so production workers can replace it without touching the API
layer.

Behavior:

- Bumps the ``Job`` row through ``queued → running → completed`` (or ``failed``).
- Marks the ``InboxItem`` as ``processed`` with ``processing_status='completed'``.
- For file/link captures, sets ``Source.parse_status='parsed'`` and
  ``Document.status='ready'`` (with a stub summary derived from the title).
- For text captures, creates a lightweight ``Card`` record so the Feed has
  something to render once the Card slice ships. The Card insert is best
  effort: if the Card model is incompatible (e.g. legacy schema), the
  failure is swallowed so the capture loop stays observable.
- Writes a ``job_completed`` notification.

The whole simulation runs in the same transaction as the capture endpoint;
callers are responsible for ``await db.commit()`` afterwards.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.inbox.prd10_models import (
    InboxItemProcessingStatus,
    InboxItemStatus,
    InboxItemType,
    Prd10InboxItem,
)
from agent_os.jobs.models import Job, JobStatus
from agent_os.kb.models import Document, DocumentStatus
from agent_os.knowledge.models import Card
from agent_os.notifications import NotificationType, create_notification
from agent_os.search_engine.embeddings import (
    embed_text,
    embedding_id_for_text,
    text_for_search_embedding,
)
from agent_os.search_engine.models import SearchIndex
from agent_os.sources.models import Source

_INBOX_TYPE_TO_CONTENT_TYPE = {
    InboxItemType.TEXT.value: "note",
    InboxItemType.LINK.value: "article",
    InboxItemType.FILE.value: "file",
    InboxItemType.IMAGE.value: "image",
    InboxItemType.AUDIO.value: "audio",
    InboxItemType.VIDEO.value: "audio",
    InboxItemType.MANUAL_TASK.value: "task",
}


_FAILURE_NOTIFICATION_TYPE_BY_INBOX_TYPE = {
    # PRD10 §15 examples: upload_failed / job_failed.
    InboxItemType.FILE.value: NotificationType.UPLOAD_FAILED,
    InboxItemType.IMAGE.value: NotificationType.UPLOAD_FAILED,
    InboxItemType.AUDIO.value: NotificationType.UPLOAD_FAILED,
    InboxItemType.VIDEO.value: NotificationType.UPLOAD_FAILED,
}


async def simulate_processing(
    db: AsyncSession,
    *,
    inbox_item: Prd10InboxItem,
    job: Job | None,
    source: Source | None = None,
    document: Document | None = None,
    summary: str | None = None,
    create_card: bool = True,
    entities: list[str] | None = None,
    content_type: str | None = None,
    folder_id: Any | None = None,
    notification_title: str | None = None,
    notification_content: str | None = None,
) -> Card | None:
    """Run the synchronous V1 pseudo-worker for a capture call.

    Flushes intermediate updates so the ``Notification`` row sees the final
    job state. Caller still needs to ``commit()``. Returns the synthesized
    ``Card`` if ``create_card`` is true and a card was generated.
    """

    now = datetime.now(UTC)

    if job is not None:
        job.status = JobStatus.RUNNING.value
        job.started_at = now
        job.progress = 50
        await db.flush()

        job.status = JobStatus.COMPLETED.value
        job.progress = 100
        job.completed_at = datetime.now(UTC)
        job.output = {
            "kind": "v1_pseudo_worker",
            "inbox_item_id": str(inbox_item.id),
            "summary_present": bool(summary),
        }

    inbox_item.status = InboxItemStatus.PROCESSED.value
    inbox_item.processing_status = InboxItemProcessingStatus.COMPLETED.value

    if source is not None:
        source.parse_status = "parsed"

    if document is not None:
        document.status = DocumentStatus.READY.value
        if summary and not document.summary:
            document.summary = summary

    card: Card | None = None
    if create_card:
        resolved_content_type = (
            content_type
            if content_type in {"note", "task", "question", "decision", "insight"}
            else _INBOX_TYPE_TO_CONTENT_TYPE.get(inbox_item.type, "note")
        )
        resolved_folder_id = folder_id if folder_id is not None else inbox_item.target_folder_id
        card = Card(
            user_id=inbox_item.user_id,
            workspace_id=inbox_item.workspace_id,
            title=inbox_item.title or (summary[:80] if summary else "Untitled"),
            content=inbox_item.raw_content or summary or "",
            summary=summary,
            content_type=resolved_content_type,
            tags=list(inbox_item.tags or []),
            entities=list(entities or []),
            inbox_item_id=inbox_item.id,
            folder_id=resolved_folder_id,
            source_id=inbox_item.source_id,
        )
        db.add(card)

    await db.flush()

    # PRD10 §19.1 step 8 (Index) — write the freshly created Card / Document
    # into the unified SearchIndex (PRD10 §5.14 SearchDocument shape) so the
    # /api/v1/search endpoint can return the new content immediately. The
    # Stage4 search service still does its own indexing for the legacy code
    # path; doing this here as well is idempotent (we keep one row per
    # (object_type, object_id)).
    if document is not None:
        await _index_search_object(
            db,
            user_id=inbox_item.user_id,
            workspace_id=inbox_item.workspace_id,
            object_type="document",
            object_id=document.id,
            title=document.title or (inbox_item.title or "Untitled"),
            summary=document.summary or summary,
            content=(getattr(document, "content", None)
                     or inbox_item.raw_content
                     or summary
                     or ""),
            tags=list(getattr(document, "tags", None) or inbox_item.tags or []),
        )
    if card is not None:
        await _index_search_object(
            db,
            user_id=card.user_id,
            workspace_id=card.workspace_id,
            object_type="card",
            object_id=card.id,
            title=card.title or "Untitled",
            summary=card.summary or summary,
            content=card.content or "",
            tags=list(card.tags or []),
        )

    await create_notification(
        db,
        user_id=inbox_item.user_id,
        type=NotificationType.JOB_COMPLETED,
        title=notification_title or "记录已整理完成",
        content=notification_content or summary or inbox_item.title or "",
        object_type="inbox_item",
        object_id=str(inbox_item.id),
    )

    return card


async def _index_search_object(
    db: AsyncSession,
    *,
    user_id,
    workspace_id,
    object_type: str,
    object_id: uuid.UUID,
    title: str,
    summary: str | None,
    content: str,
    tags: list[str],
) -> None:
    """Idempotent upsert into the legacy ``search_indices`` table.

    PRD10 §5.14 / §13 require new captures to appear in ``/api/v1/search``
    immediately. We keep one row per ``(object_type, object_id)``; the
    ``ON CONFLICT`` semantics are emulated in Python because SQLite/PG share
    the same code path.
    """

    existing = (
        await db.execute(
            select(SearchIndex).where(
                SearchIndex.item_type == object_type,
                SearchIndex.item_id == object_id,
            )
        )
    ).scalar_one_or_none()

    embedding_text = text_for_search_embedding(title, summary, content)
    embedding = embed_text(embedding_text)
    embedding_id = embedding_id_for_text(embedding_text)

    if existing is None:
        db.add(
            SearchIndex(
                item_type=object_type,
                item_id=object_id,
                user_id=user_id,
                workspace_id=workspace_id,
                title=title,
                summary=summary,
                content=content,
                tags=list(tags or []),
                embedding=embedding,
                embedding_id=embedding_id,
            )
        )
    else:
        existing.title = title
        existing.summary = summary
        existing.content = content
        existing.tags = list(tags or [])
        existing.embedding = embedding
        existing.embedding_id = embedding_id
        if user_id is not None and existing.user_id is None:
            existing.user_id = user_id
        if workspace_id is not None and existing.workspace_id is None:
            existing.workspace_id = workspace_id

    await db.flush()


async def simulate_failure(
    db: AsyncSession,
    *,
    inbox_item: Prd10InboxItem,
    job: Job | None,
    source: Source | None = None,
    document: Document | None = None,
    message: str = "Simulated worker failure",
    code: str = "JOB_FAILED",
) -> None:
    """Run the synchronous V1 pseudo-worker but **fail** instead of completing.

    PRD10 §15 expects ``upload_failed`` / ``job_failed`` notifications when a
    long-running job ends in error. This helper wires the same end-to-end
    transition as :func:`simulate_processing` but flips the terminal state.
    """

    now = datetime.now(UTC)

    if job is not None:
        job.status = JobStatus.RUNNING.value
        job.started_at = now
        job.progress = 50
        await db.flush()

        job.status = JobStatus.FAILED.value
        job.completed_at = datetime.now(UTC)
        job.error = {"code": code, "message": message}

    inbox_item.status = InboxItemStatus.FAILED.value
    inbox_item.processing_status = InboxItemProcessingStatus.FAILED.value

    if source is not None:
        source.parse_status = "failed"
        source.parse_error = message

    if document is not None:
        document.status = DocumentStatus.FAILED.value

    await db.flush()

    notif_type = _FAILURE_NOTIFICATION_TYPE_BY_INBOX_TYPE.get(
        inbox_item.type,
        NotificationType.JOB_FAILED,
    )
    title = "上传失败" if notif_type == NotificationType.UPLOAD_FAILED else "处理失败"
    await create_notification(
        db,
        user_id=inbox_item.user_id,
        type=notif_type,
        title=title,
        content=message,
        object_type="inbox_item",
        object_id=str(inbox_item.id),
    )


async def reload_job(db: AsyncSession, job_id: uuid.UUID | None) -> dict[str, Any] | None:
    """Convenience helper used by capture endpoints to ship the latest job DTO."""

    if job_id is None:
        return None
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    return job.to_prd10_dict() if job is not None else None
