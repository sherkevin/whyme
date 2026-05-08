"""Skill marketplace listing and installation models."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class SkillMarketplaceListing(Base):
    """A sellable marketplace listing for a published skill."""

    __tablename__ = "skill_marketplace_listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    seller_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="listed")
    price_credits = Column(Integer, nullable=False, default=0)
    installs_count = Column(Integer, nullable=False, default=0)
    purchases_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('listed', 'unlisted', 'archived')", name="ck_skill_listing_status"),
        CheckConstraint("price_credits >= 0", name="ck_skill_listing_price_nonnegative"),
        UniqueConstraint("skill_id", name="uq_skill_marketplace_listing_skill"),
        Index("idx_skill_listing_status_price", "status", "price_credits"),
        Index("idx_skill_listing_seller", "seller_user_id"),
    )


class SkillInstallation(Base):
    """A user's installed marketplace skill."""

    __tablename__ = "skill_installations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("skill_marketplace_listings.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="installed")
    source = Column(String(30), nullable=False, default="marketplace")
    price_paid_credits = Column(Integer, nullable=False, default=0)
    installed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('installed', 'disabled', 'uninstalled')", name="ck_skill_installation_status"),
        CheckConstraint("price_paid_credits >= 0", name="ck_skill_installation_price_nonnegative"),
        UniqueConstraint("user_id", "skill_id", name="uq_skill_installation_user_skill"),
        Index("idx_skill_installation_user_status", "user_id", "status"),
        Index("idx_skill_installation_skill", "skill_id"),
    )
