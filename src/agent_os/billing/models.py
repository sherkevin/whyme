"""Subscription and credit ledger models for PRD10 B-18."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class BillingSubscription(Base):
    """A persisted subscription snapshot for a user or workspace."""

    __tablename__ = "billing_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    plan = Column(String(30), nullable=False, default="free")
    status = Column(String(30), nullable=False, default="active")
    billing_cycle = Column(String(20), nullable=False, default="monthly")
    source = Column(String(30), nullable=False, default="local")
    current_period_start = Column(DateTime(timezone=True), server_default=func.now())
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "plan IN ('free', 'pro', 'team', 'enterprise')",
            name="ck_billing_subscription_plan",
        ),
        CheckConstraint(
            "status IN ('active', 'trialing', 'past_due', 'canceled')",
            name="ck_billing_subscription_status",
        ),
        CheckConstraint(
            "billing_cycle IN ('monthly', 'yearly')",
            name="ck_billing_subscription_cycle",
        ),
        Index("idx_billing_subscription_user_workspace", "user_id", "workspace_id"),
        Index("idx_billing_subscription_status", "status"),
    )


class CreditLedger(Base):
    """Append-only credit movement ledger."""

    __tablename__ = "credit_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    amount = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    reason = Column(String(80), nullable=False)
    reference_type = Column(String(80), nullable=True)
    reference_id = Column(String(120), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount != 0", name="ck_credit_ledger_amount_nonzero"),
        Index("idx_credit_ledger_user_workspace_created", "user_id", "workspace_id", "created_at"),
        Index("idx_credit_ledger_reference", "reference_type", "reference_id"),
    )
