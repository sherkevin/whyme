"""Server-side session persistence for JWT token pairs."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.models import Session
from agent_os.auth.security import REFRESH_TOKEN_EXPIRE_DAYS, hash_token


def _utcnow() -> datetime:
    """Return naive UTC datetime for SQLite/Postgres portability."""

    return datetime.utcnow()


def _request_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def _request_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    value = request.headers.get("user-agent")
    return value[:1000] if value else None


async def create_session_record(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    access_token: str,
    refresh_token: str,
    request: Request | None = None,
    refresh_expires_delta: timedelta | None = None,
) -> Session:
    """Persist a login session for refresh-token rotation and device audit."""

    expires_at = _utcnow() + (
        refresh_expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    row = Session(
        user_id=user_id,
        token_hash=hash_token(access_token),
        refresh_token_hash=hash_token(refresh_token),
        user_agent=_request_user_agent(request),
        ip_address=_request_ip(request),
        is_active=True,
        last_activity_at=_utcnow(),
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def consume_refresh_session(
    db: AsyncSession,
    *,
    refresh_token: str,
) -> Session | None:
    """Deactivate and return the active session matching ``refresh_token``.

    Refresh tokens are single-use. A missing, expired, or inactive session
    returns ``None`` and the caller should reject the refresh request.
    """

    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(Session).where(Session.refresh_token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    now = _utcnow()
    if row is None or not row.is_active:
        return None
    if row.expires_at is not None and row.expires_at < now:
        row.is_active = False
        row.last_activity_at = now
        await db.commit()
        return None

    row.is_active = False
    row.last_activity_at = now
    await db.commit()
    return row


async def revoke_access_session(
    db: AsyncSession,
    *,
    access_token: str,
) -> bool:
    """Deactivate the server-side session matching an access token."""

    token_hash = hash_token(access_token)
    result = await db.execute(select(Session).where(Session.token_hash == token_hash))
    row = result.scalar_one_or_none()
    if row is None or not row.is_active:
        return False
    row.is_active = False
    row.last_activity_at = _utcnow()
    await db.commit()
    return True
