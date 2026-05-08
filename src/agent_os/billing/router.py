"""PRD10 B-18 subscription and credit APIs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.billing.models import BillingSubscription, CreditLedger
from agent_os.common import ApiErrorCode, error_json_response, success_json_response
from agent_os.db.base import get_db

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])

PlanCode = Literal["free", "pro", "team", "enterprise"]
BillingCycle = Literal["monthly", "yearly"]


PLAN_CATALOG: dict[str, dict] = {
    "free": {
        "code": "free",
        "name": "Free",
        "monthly_price_cents": 0,
        "yearly_price_cents": 0,
        "monthly_credits": 100,
        "features": ["个人灵感采集", "基础知识库", "Mydow AI 轻量问答"],
    },
    "pro": {
        "code": "pro",
        "name": "Pro",
        "monthly_price_cents": 3900,
        "yearly_price_cents": 39000,
        "monthly_credits": 1000,
        "features": ["高级 RAG 问答", "AI 周报", "Skills 批量运行"],
    },
    "team": {
        "code": "team",
        "name": "Team",
        "monthly_price_cents": 19900,
        "yearly_price_cents": 199000,
        "monthly_credits": 5000,
        "features": ["多 workspace 协作", "成员权限", "团队知识资产"],
    },
    "enterprise": {
        "code": "enterprise",
        "name": "Enterprise",
        "monthly_price_cents": None,
        "yearly_price_cents": None,
        "monthly_credits": 20000,
        "features": ["专属部署", "审计与合规", "定制模型接入"],
    },
}


class SubscriptionUpdateRequest(BaseModel):
    plan: PlanCode
    billing_cycle: BillingCycle = "monthly"
    workspace_id: uuid.UUID | None = None


class CreditConsumeRequest(BaseModel):
    amount: int = Field(..., gt=0, le=100_000)
    reason: str = Field(..., min_length=1, max_length=80)
    reference_type: str | None = Field(default=None, max_length=80)
    reference_id: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    workspace_id: uuid.UUID | None = None


def _period_end(cycle: str) -> datetime:
    now = datetime.now(UTC)
    return now + (timedelta(days=365) if cycle == "yearly" else timedelta(days=30))


def _subscription_payload(sub: BillingSubscription) -> dict:
    return {
        "id": str(sub.id),
        "user_id": str(sub.user_id),
        "workspace_id": str(sub.workspace_id) if sub.workspace_id else None,
        "plan": sub.plan,
        "status": sub.status,
        "billing_cycle": sub.billing_cycle,
        "source": sub.source,
        "current_period_start": sub.current_period_start.isoformat()
        if sub.current_period_start
        else None,
        "current_period_end": sub.current_period_end.isoformat()
        if sub.current_period_end
        else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }


def _ledger_payload(entry: CreditLedger) -> dict:
    return {
        "id": str(entry.id),
        "user_id": str(entry.user_id),
        "workspace_id": str(entry.workspace_id) if entry.workspace_id else None,
        "amount": entry.amount,
        "balance_after": entry.balance_after,
        "reason": entry.reason,
        "reference_type": entry.reference_type,
        "reference_id": entry.reference_id,
        "note": entry.note,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def _workspace_predicate(model, workspace_id: uuid.UUID | None):
    return model.workspace_id.is_(None) if workspace_id is None else model.workspace_id == workspace_id


async def _credit_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
            CreditLedger.user_id == user_id,
            _workspace_predicate(CreditLedger, workspace_id),
        )
    )
    return int(result.scalar_one() or 0)


async def _append_credit_entry(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    amount: int,
    reason: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
    note: str | None = None,
) -> CreditLedger:
    balance = await _credit_balance(db, user_id, workspace_id)
    entry = CreditLedger(
        user_id=user_id,
        workspace_id=workspace_id,
        amount=amount,
        balance_after=balance + amount,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
        created_at=datetime.now(UTC),
    )
    db.add(entry)
    await db.flush()
    return entry


async def _current_subscription(
    db: AsyncSession,
    user: User,
    workspace_id: uuid.UUID | None,
) -> BillingSubscription | None:
    result = await db.execute(
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == user.id,
            _workspace_predicate(BillingSubscription, workspace_id),
            BillingSubscription.status.in_(("active", "trialing", "past_due")),
        )
        .order_by(desc(BillingSubscription.updated_at), desc(BillingSubscription.created_at))
    )
    return result.scalars().first()


async def _ensure_subscription(
    db: AsyncSession,
    user: User,
    workspace_id: uuid.UUID | None = None,
) -> BillingSubscription:
    sub = await _current_subscription(db, user, workspace_id)
    if sub is not None:
        return sub
    plan = (user.settings or {}).get("plan") or "free"
    if plan not in PLAN_CATALOG:
        plan = "free"
    sub = BillingSubscription(
        user_id=user.id,
        workspace_id=workspace_id,
        plan=plan,
        billing_cycle="monthly",
        status="active",
        source="local",
        current_period_end=_period_end("monthly"),
    )
    db.add(sub)
    await db.flush()
    if await _credit_balance(db, user.id, workspace_id) == 0:
        await _append_credit_entry(
            db,
            user_id=user.id,
            workspace_id=workspace_id,
            amount=int(PLAN_CATALOG[plan]["monthly_credits"]),
            reason="initial_plan_allowance",
            reference_type="subscription",
            reference_id=str(sub.id),
        )
    await db.commit()
    await db.refresh(sub)
    return sub


async def _recent_ledger(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    limit: int = 20,
) -> list[CreditLedger]:
    result = await db.execute(
        select(CreditLedger)
        .where(
            CreditLedger.user_id == user_id,
            _workspace_predicate(CreditLedger, workspace_id),
        )
        .order_by(desc(CreditLedger.created_at), desc(CreditLedger.id))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/plans")
async def get_plans(request: Request):
    return success_json_response({"items": list(PLAN_CATALOG.values())}, request=request)


@router.get("/subscription")
async def get_subscription(
    request: Request,
    workspace_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _ensure_subscription(db, current_user, workspace_id)
    return success_json_response(_subscription_payload(sub), request=request)


@router.patch("/subscription")
async def update_subscription(
    payload: SubscriptionUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _ensure_subscription(db, current_user, payload.workspace_id)
    old_plan = sub.plan
    sub.plan = payload.plan
    sub.billing_cycle = payload.billing_cycle
    sub.status = "active"
    sub.source = "local"
    sub.current_period_end = _period_end(payload.billing_cycle)

    settings = dict(current_user.settings or {})
    settings["plan"] = payload.plan
    current_user.settings = settings
    flag_modified(current_user, "settings")

    if old_plan != payload.plan:
        await _append_credit_entry(
            db,
            user_id=current_user.id,
            workspace_id=payload.workspace_id,
            amount=int(PLAN_CATALOG[payload.plan]["monthly_credits"]),
            reason="plan_allowance",
            reference_type="subscription",
            reference_id=str(sub.id),
            note=f"{old_plan}->{payload.plan}",
        )
    await db.commit()
    await db.refresh(sub)
    return success_json_response(_subscription_payload(sub), request=request)


@router.get("/overview")
async def get_billing_overview(
    request: Request,
    workspace_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _ensure_subscription(db, current_user, workspace_id)
    balance = await _credit_balance(db, current_user.id, workspace_id)
    entries = await _recent_ledger(db, current_user.id, workspace_id, limit=10)
    return success_json_response(
        {
            "subscription": _subscription_payload(sub),
            "plan": PLAN_CATALOG[sub.plan],
            "credit_balance": balance,
            "recent_transactions": [_ledger_payload(entry) for entry in entries],
        },
        request=request,
    )


@router.get("/credits")
async def get_credits(
    request: Request,
    workspace_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_subscription(db, current_user, workspace_id)
    balance = await _credit_balance(db, current_user.id, workspace_id)
    entries = await _recent_ledger(db, current_user.id, workspace_id, limit=limit)
    return success_json_response(
        {
            "balance": balance,
            "items": [_ledger_payload(entry) for entry in entries],
        },
        request=request,
    )


@router.post("/credits/consume", status_code=status.HTTP_201_CREATED)
async def consume_credits(
    payload: CreditConsumeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_subscription(db, current_user, payload.workspace_id)
    balance = await _credit_balance(db, current_user.id, payload.workspace_id)
    if balance < payload.amount:
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Insufficient credit balance",
            details={"balance": balance, "amount": payload.amount},
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    entry = await _append_credit_entry(
        db,
        user_id=current_user.id,
        workspace_id=payload.workspace_id,
        amount=-payload.amount,
        reason=payload.reason,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        note=payload.note,
    )
    await db.commit()
    await db.refresh(entry)
    return success_json_response(
        _ledger_payload(entry),
        request=request,
        status_code=status.HTTP_201_CREATED,
    )
