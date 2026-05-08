"""Workspace membership models for PRD10 B-17 permissions."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base


class WorkspaceMember(Base):
    """A user's role inside a workspace.

    The canonical workspace row already exists as ``items.models.Workspace``.
    This table adds the missing multi-workspace permission boundary without
    changing existing personal-space records.
    """

    __tablename__ = "workspace_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(20), nullable=False, default="viewer")
    status = Column(String(20), nullable=False, default="active")
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace", backref="memberships")
    user = relationship("User", foreign_keys=[user_id], backref="workspace_memberships")
    invited_by = relationship("User", foreign_keys=[invited_by_id])

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'editor', 'viewer')",
            name="ck_workspace_members_role",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_workspace_members_status",
        ),
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
        Index("idx_workspace_members_workspace", "workspace_id"),
        Index("idx_workspace_members_user", "user_id"),
        Index("idx_workspace_members_role", "workspace_id", "role"),
    )
