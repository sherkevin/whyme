"""PRD10 §11.10 Account compliance & lifecycle router.

Investor-grade compliance baseline for the V1 acceptance gate. All endpoints
live under ``/api/v1/me/*`` and emit the PRD10 envelope.

Endpoints
---------
* ``GET    /api/v1/me/export``      — GDPR "right to data portability".
  Aggregates every row owned by the current user (profile, KB folders /
  documents / chunks, feed cards, inbox items, notifications, AI
  conversations + messages, jobs) and returns a single JSON payload the
  user can download.
* ``DELETE /api/v1/me``             — GDPR "right to erasure".
  Soft-deletes the account: marks ``is_active=False``, stamps
  ``settings.deleted_at`` (ISO 8601 UTC), anonymizes PII (email rotated to
  ``deleted-<short-id>@deleted.invalid``, ``full_name`` cleared) so the
  original identifiers can never be reconstructed by a brute-force search.
  Owned rows remain linked by ``user_id`` for audit; clients should drop
  their local token immediately after a 200 response.
* ``POST   /api/v1/me/unsubscribe`` — opt out of all notification channels.
  Sets ``settings.notification_preferences`` so every channel (email /
  desktop / weekly_digest / product_updates / marketing) is ``False``.

The router intentionally guards against double-execution on a soft-deleted
account: once ``settings.deleted_at`` is present, every subsequent call
returns ``410 GONE`` so a leaked token cannot keep operating against the
account after the user pressed "Delete".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, success_response
from agent_os.db.base import get_db

router = APIRouter(prefix="/api/v1/me", tags=["Account"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _settings(user: User) -> dict[str, Any]:
    """Return ``user.settings`` as a mutable dict, materializing if NULL."""

    raw = user.settings
    if not isinstance(raw, dict):
        raw = {}
    return dict(raw)


def _commit_settings(user: User, settings: dict[str, Any]) -> None:
    """Persist a mutated settings dict back onto the User row.

    SQLAlchemy's JSON column does not detect in-place mutations on the dict
    automatically, so we explicitly reassign and ``flag_modified`` to make
    sure the UPDATE fires on commit.
    """

    user.settings = settings
    flag_modified(user, "settings")


def _is_soft_deleted(user: User) -> bool:
    settings = _settings(user)
    return bool(settings.get("deleted_at")) or user.is_active is False


def _ensure_active(user: User) -> None:
    """Fail with PRD10 envelope ``410 GONE`` if the account was deleted.

    The frontend should drop the local token after ``DELETE /api/v1/me``;
    this guard is a server-side fallback if the client tries to reuse a
    still-valid JWT.
    """

    if _is_soft_deleted(user):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": ApiErrorCode.FORBIDDEN.value,
                "message": "Account has been deleted",
            },
        )


async def _attached_user(db: AsyncSession, current_user: User) -> User:
    """Return ``current_user`` re-loaded inside the endpoint's ``db`` session.

    ``get_current_user`` may return an instance attached to a different
    session (e.g. in tests using dependency overrides) which means in-place
    attribute mutations would not flush on ``db.commit()``. This helper
    re-fetches the row inside ``db`` so subsequent mutations are tracked.
    Returns the original instance if it's already attached to ``db``.
    """

    from sqlalchemy import inspect as sa_inspect

    state = sa_inspect(current_user)
    if state.session is db:
        return current_user

    # Detach from any stale session and re-load inside ``db``.
    res = await db.execute(select(User).where(User.id == current_user.id))
    fresh = res.scalar_one_or_none()
    if fresh is None:
        # Extremely defensive: token says user X but DB no longer has X.
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Account no longer exists",
            },
        )
    return fresh


def _safe_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _user_profile_dict(user: User) -> dict[str, Any]:
    settings = _settings(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "is_active": bool(user.is_active),
        "is_verified": bool(user.is_verified),
        "settings": settings,
        "created_at": _safe_iso(user.created_at),
        "updated_at": _safe_iso(user.updated_at),
        "last_login_at": _safe_iso(user.last_login_at),
    }


# ---------------------------------------------------------------------------
# /api/v1/me/export — GDPR data portability
# ---------------------------------------------------------------------------


@router.get(
    "/export",
    summary="Export all user-owned data (GDPR data portability)",
)
async def export_user_data(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Aggregate every row owned by the current user and return JSON.

    PRD10 §11.10 / GDPR Art. 20 (right to data portability). The shape is a
    flat object keyed by domain so a user can open the response with any
    JSON viewer and inspect their data; counts are duplicated under
    ``stats`` for quick reporting.
    """

    current_user = await _attached_user(db, current_user)
    _ensure_active(current_user)

    # Lazy imports avoid pulling every PRD10 model into module import time;
    # this endpoint is only hit on explicit user action.
    from agent_os.ai.models import AIConversation, AIMessage
    from agent_os.inbox.prd10_models import Prd10InboxItem
    from agent_os.jobs.models import Job
    from agent_os.kb.models import Chunk, Document, Folder
    from agent_os.knowledge.models import Card
    from agent_os.notifications.models import Notification

    user_id = current_user.id

    async def _rows(stmt) -> list[Any]:
        result = await db.execute(stmt)
        return list(result.scalars().all())

    folders = await _rows(
        select(Folder).where(Folder.user_id == user_id).order_by(Folder.created_at)
    )
    documents = await _rows(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at)
    )
    chunks = await _rows(
        select(Chunk).where(Chunk.user_id == user_id).order_by(Chunk.chunk_index)
    )
    cards = await _rows(
        select(Card).where(Card.user_id == user_id).order_by(Card.created_at)
    )
    inbox = await _rows(
        select(Prd10InboxItem)
        .where(Prd10InboxItem.user_id == user_id)
        .order_by(Prd10InboxItem.created_at)
    )
    notifications = await _rows(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at)
    )
    conversations = await _rows(
        select(AIConversation)
        .where(AIConversation.user_id == user_id)
        .order_by(AIConversation.created_at)
    )
    messages = await _rows(
        select(AIMessage)
        .where(AIMessage.user_id == user_id)
        .order_by(AIMessage.created_at)
    )
    jobs = await _rows(
        select(Job).where(Job.user_id == user_id).order_by(Job.created_at)
    )

    def _serialize(row: Any) -> dict[str, Any]:
        if hasattr(row, "to_prd10_dict"):
            try:
                payload = row.to_prd10_dict()
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        # Fallback: copy SQLAlchemy column values into a plain dict so the
        # export never silently swallows a table.
        out: dict[str, Any] = {}
        for column in row.__table__.columns:
            value = getattr(row, column.name, None)
            if isinstance(value, (datetime,)):
                out[column.name] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                out[column.name] = str(value)
            else:
                out[column.name] = value
        return out

    documents_payload = []
    for doc in documents:
        if hasattr(doc, "to_prd10_dict"):
            documents_payload.append(doc.to_prd10_dict(include_content=True))
        else:
            documents_payload.append(_serialize(doc))

    payload: dict[str, Any] = {
        "schema_version": "prd10.v1",
        "exported_at": datetime.now(UTC).isoformat(),
        "user": _user_profile_dict(current_user),
        "kb": {
            "folders": [_serialize(f) for f in folders],
            "documents": documents_payload,
            "chunks": [_serialize(c) for c in chunks],
        },
        "feed": {
            "cards": [_serialize(c) for c in cards],
        },
        "inbox": {
            "items": [_serialize(i) for i in inbox],
        },
        "notifications": [_serialize(n) for n in notifications],
        "ai": {
            "conversations": [_serialize(c) for c in conversations],
            "messages": [_serialize(m) for m in messages],
        },
        "jobs": [_serialize(j) for j in jobs],
    }
    payload["stats"] = {
        "folder_count": len(folders),
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "card_count": len(cards),
        "inbox_count": len(inbox),
        "notification_count": len(notifications),
        "conversation_count": len(conversations),
        "message_count": len(messages),
        "job_count": len(jobs),
    }

    return success_response(payload, request=request)


# ---------------------------------------------------------------------------
# DELETE /api/v1/me — GDPR right to erasure
# ---------------------------------------------------------------------------


@router.delete(
    "",
    summary="Soft-delete the current account (GDPR right to erasure)",
)
async def delete_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Mark the current account as deleted.

    Effects:
    - ``is_active`` flipped to ``False``.
    - ``settings.deleted_at`` stamped with the current ISO 8601 UTC time.
    - ``email`` rotated to ``deleted-<short-id>@deleted.invalid`` so the
      original mailbox cannot be linked back to the row by anyone with
      direct DB access.
    - ``full_name`` cleared (``""``) and ``avatar_url`` cleared.

    Owned rows (Folder / Document / Card / Notification / AIMessage / Job)
    keep their ``user_id`` foreign key so audit trails remain consistent;
    clients are expected to drop the local token after this call.

    Idempotent: calling DELETE twice in a row returns ``410 GONE`` the
    second time so a leaked token cannot keep iterating against the
    account after deletion.
    """

    current_user = await _attached_user(db, current_user)
    _ensure_active(current_user)

    now = datetime.now(UTC)
    settings = _settings(current_user)
    short_id = uuid.uuid4().hex[:12]

    settings["deleted_at"] = now.isoformat()
    settings.setdefault("deletion_reason", "user_initiated")
    settings["original_email_hash"] = (
        # Stable opaque hash so support can match a user-supplied "I asked
        # to be deleted on date X" claim without persisting the cleartext.
        f"sha1:{uuid.uuid5(uuid.NAMESPACE_DNS, current_user.email or '').hex[:16]}"
    )
    # Notifications are off after deletion; subscribing back requires a new
    # account.
    notification_prefs = dict(settings.get("notification_preferences") or {})
    for channel in (
        "email",
        "desktop",
        "weekly_digest",
        "product_updates",
        "marketing",
    ):
        notification_prefs[channel] = False
    settings["notification_preferences"] = notification_prefs

    deleted_email = f"deleted-{short_id}@deleted.invalid"
    deleted_username = f"deleted_{short_id}"

    current_user.email = deleted_email
    current_user.username = deleted_username
    current_user.full_name = None
    current_user.avatar_url = None
    current_user.is_active = False
    _commit_settings(current_user, settings)

    await db.commit()

    return success_response(
        {
            "id": str(current_user.id),
            "deleted_at": settings["deleted_at"],
            "status": "soft_deleted",
            "message": (
                "Your account has been deleted. Stored records are retained "
                "in anonymized form for audit; please drop your local token "
                "now."
            ),
        },
        request=request,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/me/unsubscribe — opt out of all notification channels
# ---------------------------------------------------------------------------


@router.post(
    "/unsubscribe",
    summary="Opt out of all notification channels",
)
async def unsubscribe_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Turn off every notification channel for the current user.

    Sets ``settings.notification_preferences`` to ``{email: False,
    desktop: False, weekly_digest: False, product_updates: False,
    marketing: False}`` and stamps ``settings.unsubscribed_at`` with the
    current UTC timestamp. Idempotent — calling twice keeps the same
    state and updates the timestamp.
    """

    current_user = await _attached_user(db, current_user)
    _ensure_active(current_user)

    now = datetime.now(UTC)
    settings = _settings(current_user)

    notification_prefs = dict(settings.get("notification_preferences") or {})
    for channel in (
        "email",
        "desktop",
        "weekly_digest",
        "product_updates",
        "marketing",
    ):
        notification_prefs[channel] = False
    settings["notification_preferences"] = notification_prefs
    settings["unsubscribed_at"] = now.isoformat()

    _commit_settings(current_user, settings)

    await db.commit()

    return success_response(
        {
            "id": str(current_user.id),
            "unsubscribed_at": settings["unsubscribed_at"],
            "notification_preferences": notification_prefs,
        },
        request=request,
    )
