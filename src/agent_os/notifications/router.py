"""PRD10 ``/api/v1/notifications/*`` router (§15)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.notifications.broker import encode_sse, get_broker
from agent_os.notifications.models import Notification

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("/unread-count")
async def unread_count(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the unread notification count for the current user."""

    stmt = select(func.count(Notification.id)).where(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
    )
    result = await db.execute(stmt)
    count = result.scalar_one() or 0
    return success_response({"count": int(count)}, request=request)


@router.get("")
async def list_notifications(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    is_read: bool | None = Query(default=None),
    type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    base = select(Notification).where(Notification.user_id == current_user.id)
    count_base = select(func.count(Notification.id)).where(
        Notification.user_id == current_user.id
    )

    if is_read is not None:
        base = base.where(Notification.is_read.is_(is_read))
        count_base = count_base.where(Notification.is_read.is_(is_read))
    if type:
        base = base.where(Notification.type == type)
        count_base = count_base.where(Notification.type == type)

    total = (await db.execute(count_base)).scalar_one() or 0

    rows = (
        await db.execute(
            base.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    items = [n.to_prd10_dict() for n in rows]
    return paginated_response(
        items,
        page=page,
        page_size=page_size,
        total=int(total),
        request=request,
    )


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Notification not found",
            },
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notification)

    return success_response(notification.to_prd10_dict(), request=request)


@router.post("/read-all")
async def mark_all_read(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC)
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    result = await db.execute(stmt)
    await db.commit()
    return success_response({"updated": int(result.rowcount or 0)}, request=request)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v1.4 §3.8 — `DELETE /notifications/:id` removes a notification row.

    Wired for the notifications drawer per-row "删除" action. Hard-delete
    in V1 (no recoverable trash for notifications); audit traces still live
    in the broker logs / structured access log.
    """

    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Notification not found",
            },
        )

    await db.delete(notification)
    await db.commit()
    return success_response(
        {"id": str(notification_id), "deleted": True}, request=request
    )


@router.get("/stream")
async def stream_notifications(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """PRD10 §15 real-time notification push via Server-Sent Events.

    The connection emits:

    - ``event: ready`` once when subscription is established (with a
      ``retry: 5000`` hint folded in so EventSource clients auto-reconnect
      after 5s on disconnect);
    - ``event: notification`` whenever ``create_notification`` fires for the
      current user;
    - ``event: ping`` every ~25s so proxies don't kill idle connections.

    Closing the request (e.g. tab close) drops the subscription.

    Headers ``Cache-Control: no-cache`` + ``X-Accel-Buffering: no`` keep
    proxies / nginx from buffering or recycling the response. See
    PRD10 §12.4 (SSE keepalive hardening).
    """

    broker = get_broker()
    user_id = current_user.id

    async def event_source():
        # PRD10 §15 contract: emit ``ready`` on subscribe, then ``notification``
        # for every published payload, with a ``ping`` heartbeat every ~25s so
        # idle connections survive proxies. We detect client disconnects by
        # racing the queue read against a short polling task that calls
        # ``request.is_disconnected`` (which actually reads from the ASGI
        # ``receive`` channel and observes ``http.disconnect`` messages).
        ping_at_ticks = 50  # 0.5s poll * 50 ticks ≈ 25s
        ticks = 0
        async with broker.subscribe(user_id) as queue:
            # First frame carries the SSE ``retry:`` hint so EventSource
            # clients automatically reconnect 5s after a TCP drop. We bake
            # it into the same block as the ``ready`` event to keep test
            # parsers (which split on blank lines) deterministic.
            yield (
                b"retry: 5000\n"
                + encode_sse("ready", {"user_id": str(user_id)})
            )
            queue_task: asyncio.Task | None = None
            try:
                queue_task = asyncio.create_task(queue.get())
                while True:
                    done, _pending = await asyncio.wait(
                        {queue_task},
                        timeout=0.5,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if queue_task in done:
                        payload = queue_task.result()
                        ticks = 0
                        queue_task = asyncio.create_task(queue.get())
                        yield encode_sse("notification", payload)
                        continue

                    if await request.is_disconnected():
                        return

                    # Neither completed (timeout) - emit periodic ping.
                    ticks += 1
                    if ticks >= ping_at_ticks:
                        ticks = 0
                        yield encode_sse("ping", {})
            except asyncio.CancelledError:
                return
            finally:
                if queue_task is not None and not queue_task.done():
                    queue_task.cancel()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

