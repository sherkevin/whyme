"""PRD10 ``/api/v1/uploads/local/*`` endpoints (V1 filesystem backend).

These back the pseudo-presigned URLs handed out by
``POST /api/v1/uploads/presign``. The contract is intentionally close to a
typical S3 presigned setup so that a future swap to real object storage is a
storage-class change, not an API change:

- ``PUT /api/v1/uploads/local/{upload_id}`` writes raw bytes.
- ``GET /api/v1/uploads/local/{upload_id}/raw`` streams the bytes back with
  the right ``Content-Type`` / ``Content-Disposition`` headers.

Both endpoints require an authenticated user; cross-user access returns 404
to avoid leaking existence.

PRD10 §12.5 / §16.3 multipart upload (large files / resumable):

- ``POST /api/v1/uploads/multipart/init``                 — start a session
- ``PUT  /api/v1/uploads/multipart/{upload_id}/{index}``  — push a chunk
- ``GET  /api/v1/uploads/multipart/{upload_id}``          — resume status
- ``POST /api/v1/uploads/multipart/{upload_id}/complete`` — assemble + create Source
- ``DELETE /api/v1/uploads/multipart/{upload_id}``        — cancel session
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, success_response
from agent_os.db.base import get_db
from agent_os.sources.models import Source
from agent_os.uploads.storage import (
    MultipartSession,
    MultipartUploadError,
    StoredUpload,
    get_default_multipart_storage,
    get_default_storage,
)

router = APIRouter(prefix="/api/v1/uploads", tags=["Uploads"])


_DEFAULT_FILENAME = "upload.bin"


# ---------------------------------------------------------------------------
# Multipart upload — Pydantic request bodies
# ---------------------------------------------------------------------------


class MultipartInitRequest(BaseModel):
    """``POST /api/v1/uploads/multipart/init`` request body.

    PRD10 §16.3 contract: client tells the server the total size and
    (optionally) the chunk size; server replies with the multipart session
    descriptor including the assigned ``upload_id``, the **server's** chosen
    ``chunk_size`` (server may downsize an unreasonable client request) and
    the resulting ``total_chunks`` so the client knows how many PUTs to fire.
    """

    filename: str = Field(..., min_length=1, max_length=500)
    total_size_bytes: int = Field(..., gt=0)
    mime_type: str | None = Field(default=None, max_length=200)
    chunk_size: int | None = Field(
        default=None,
        ge=1024,
        le=64 * 1024 * 1024,
        description=(
            "Optional override for the chunk size in bytes (1 KiB – 64 MiB)."
            " Production clients typically omit this and accept the server's"
            " 5 MiB default."
        ),
    )

    model_config = ConfigDict(extra="forbid")


@router.put("/local/{upload_id}")
async def put_upload_bytes(
    upload_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_filename: str | None = Header(default=None, alias="X-Filename"),
    content_type: str | None = Header(default=None, alias="Content-Type"),
):
    """Receive the raw bytes of a previously presigned upload.

    The filename can come from the ``X-Filename`` header (preferred for the
    no-MIME-multipart path used by `fetch(PUT, body=Blob)`) or it falls back
    to the default ``upload.bin``. ``commit`` will replace this with the
    real filename anyway.
    """

    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": "Empty upload body",
            },
        )

    storage = get_default_storage()
    stored: StoredUpload = storage.write_bytes(
        user_id=current_user.id,
        upload_id=upload_id,
        filename=x_filename or _DEFAULT_FILENAME,
        data=body,
    )

    # Pre-create / refresh the Source row so commit can verify the file.
    existing = (
        await db.execute(
            select(Source).where(
                Source.id == upload_id,
                Source.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        source = Source(
            id=upload_id,
            user_id=current_user.id,
            source_type="file",
            name=stored.filename,
            url=_internal_url(request, upload_id),
            storage_path=stored.relative_path,
            mime_type=content_type,
            size_bytes=stored.size_bytes,
            parse_status="uploaded",
        )
        db.add(source)
    else:
        existing.name = stored.filename
        existing.url = _internal_url(request, upload_id)
        existing.storage_path = stored.relative_path
        existing.mime_type = content_type or existing.mime_type
        existing.size_bytes = stored.size_bytes
        existing.parse_status = "uploaded"
        existing.updated_at = datetime.now(UTC)

    await db.commit()

    return success_response(
        {
            "upload_id": str(upload_id),
            "filename": stored.filename,
            "size_bytes": stored.size_bytes,
            "file_url": _internal_url(request, upload_id),
        },
        request=request,
    )


@router.get("/local/{upload_id}/raw")
async def get_upload_bytes(
    upload_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream the previously uploaded bytes back to the caller."""

    source = (
        await db.execute(
            select(Source).where(
                Source.id == upload_id,
                Source.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    storage = get_default_storage()
    located = storage.open_stream(user_id=current_user.id, upload_id=upload_id)
    if located is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Upload not found",
            },
        )
    path, gen = located

    filename = source.name if source and source.name else path.name
    mime = (source.mime_type if source else None) or "application/octet-stream"

    return StreamingResponse(
        gen,
        media_type=mime,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


def _internal_url(request: Request, upload_id: uuid.UUID) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/uploads/local/{upload_id}/raw"


# ---------------------------------------------------------------------------
# Multipart upload helpers
# ---------------------------------------------------------------------------


def _multipart_session_payload(session: MultipartSession) -> dict:
    """Project a :class:`MultipartSession` into the wire shape the SPA reads."""

    received = session.received_indices()
    return {
        "upload_id": str(session.upload_id),
        "filename": session.filename,
        "mime_type": session.mime_type,
        "total_size_bytes": session.total_size_bytes,
        "chunk_size": session.chunk_size,
        "total_chunks": session.total_chunks,
        "received_chunks": received,
        "received_count": len(received),
        "missing_chunks": session.missing_indices(),
        "expires_at": session.expires_at.isoformat(),
        "created_at": session.created_at.isoformat(),
        "completed_at": (
            session.completed_at.isoformat() if session.completed_at else None
        ),
        "status": (
            "completed"
            if session.completed_at is not None
            else ("ready" if session.is_complete() else "in_progress")
        ),
    }


def _raise_multipart_error(exc: MultipartUploadError) -> None:
    """Translate a :class:`MultipartUploadError` into a PRD10 envelope HTTP error."""

    status_code = (
        status.HTTP_404_NOT_FOUND
        if exc.code == "NOT_FOUND"
        else status.HTTP_400_BAD_REQUEST
    )
    code_value = (
        ApiErrorCode.NOT_FOUND.value
        if exc.code == "NOT_FOUND"
        else ApiErrorCode.VALIDATION_ERROR.value
    )
    raise HTTPException(
        status_code=status_code,
        detail={"code": code_value, "message": exc.message},
    )


# ---------------------------------------------------------------------------
# POST /api/v1/uploads/multipart/init
# ---------------------------------------------------------------------------


@router.post("/multipart/init")
async def multipart_init(
    payload: MultipartInitRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Start a multipart upload session.

    Returns the assigned ``upload_id``, the server-resolved ``chunk_size``
    (clamped to 64 KiB – 64 MiB), the resulting ``total_chunks`` count and
    an ``expires_at`` timestamp so the client knows how long it has to push
    the chunks.
    """

    multipart = get_default_multipart_storage()
    try:
        session = multipart.init_session(
            user_id=current_user.id,
            upload_id=None,
            filename=payload.filename,
            total_size_bytes=payload.total_size_bytes,
            mime_type=payload.mime_type,
            chunk_size=payload.chunk_size,
        )
    except MultipartUploadError as exc:
        _raise_multipart_error(exc)

    return success_response(
        _multipart_session_payload(session),
        request=request,
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/uploads/multipart/{upload_id}/{chunk_index}
# ---------------------------------------------------------------------------


@router.put("/multipart/{upload_id}/{chunk_index}")
async def multipart_put_chunk(
    upload_id: uuid.UUID,
    chunk_index: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Upload one chunk of a multipart session.

    The body MUST contain exactly the chunk's bytes (no multipart/form-data
    wrapper) so the same client code can transparently swap to S3/R2 in
    the future. The server validates the chunk size (every chunk except
    the last must equal ``session.chunk_size``; the last chunk's expected
    size is computed from ``total_size_bytes``).
    """

    body = await request.body()
    multipart = get_default_multipart_storage()
    try:
        info = multipart.write_chunk(
            user_id=current_user.id,
            upload_id=upload_id,
            chunk_index=chunk_index,
            data=body,
        )
        session = multipart.get_session(
            user_id=current_user.id, upload_id=upload_id
        )
    except MultipartUploadError as exc:
        _raise_multipart_error(exc)

    payload = {
        "upload_id": str(upload_id),
        "chunk_index": info.index,
        "size_bytes": info.size_bytes,
        "sha256": info.sha256,
        "received_count": (
            len(session.received_indices()) if session is not None else 1
        ),
        "total_chunks": session.total_chunks if session is not None else None,
        "is_complete": (
            session.is_complete() if session is not None else False
        ),
    }
    return success_response(payload, request=request)


# ---------------------------------------------------------------------------
# GET /api/v1/uploads/multipart/{upload_id}  (status / resume)
# ---------------------------------------------------------------------------


@router.get("/multipart/{upload_id}")
async def multipart_status(
    upload_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return the current status of a multipart session for resume.

    The response includes the list of indexes already received so the
    client can skip them and re-PUT only what's missing. Cross-user lookup
    returns 404 to avoid leaking session existence.
    """

    multipart = get_default_multipart_storage()
    session = multipart.get_session(
        user_id=current_user.id, upload_id=upload_id
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Multipart session not found",
            },
        )
    return success_response(
        _multipart_session_payload(session),
        request=request,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/uploads/multipart/{upload_id}/complete
# ---------------------------------------------------------------------------


@router.post("/multipart/{upload_id}/complete")
async def multipart_complete(
    upload_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assemble the chunks into the final blob + create/refresh the Source row.

    Returns the same shape as ``PUT /api/v1/uploads/local/{upload_id}`` so
    the existing ``POST /api/v1/capture/file/commit`` consumer can flow
    end-to-end without knowing whether single-PUT or multipart was used.
    """

    multipart = get_default_multipart_storage()
    target_storage = get_default_storage()

    try:
        session, stored = multipart.assemble(
            user_id=current_user.id,
            upload_id=upload_id,
            target_storage=target_storage,
        )
    except MultipartUploadError as exc:
        _raise_multipart_error(exc)

    file_url = _internal_url(request, upload_id)

    existing = (
        await db.execute(
            select(Source).where(
                Source.id == upload_id,
                Source.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        source = Source(
            id=upload_id,
            user_id=current_user.id,
            source_type="file",
            name=stored.filename,
            url=file_url,
            storage_path=stored.relative_path,
            mime_type=session.mime_type,
            size_bytes=stored.size_bytes,
            parse_status="uploaded",
        )
        db.add(source)
    else:
        existing.name = stored.filename
        existing.url = file_url
        existing.storage_path = stored.relative_path
        existing.mime_type = session.mime_type or existing.mime_type
        existing.size_bytes = stored.size_bytes
        existing.parse_status = "uploaded"
        existing.updated_at = datetime.now(UTC)

    await db.commit()

    return success_response(
        {
            "upload_id": str(upload_id),
            "filename": stored.filename,
            "size_bytes": stored.size_bytes,
            "file_url": file_url,
            "completed_at": (
                session.completed_at.isoformat() if session.completed_at else None
            ),
            "total_chunks": session.total_chunks,
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/uploads/multipart/{upload_id}
# ---------------------------------------------------------------------------


@router.delete("/multipart/{upload_id}")
async def multipart_cancel(
    upload_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Cancel a multipart session and tear down the temporary chunk files.

    Idempotent: deleting a non-existent / already cancelled / already
    completed session also returns 200 so client retries are safe.
    """

    multipart = get_default_multipart_storage()
    removed = multipart.cancel(
        user_id=current_user.id, upload_id=upload_id
    )
    return success_response(
        {
            "upload_id": str(upload_id),
            "cancelled": bool(removed),
        },
        request=request,
    )


__all__ = ["router"]
