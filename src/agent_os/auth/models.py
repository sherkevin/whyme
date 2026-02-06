"""Authentication and Authorization Models - Stage 7 Implementation.

User management, API keys, sessions, and role-based access control.
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Index, CheckConstraint, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base


# ============================================================================
# User Model
# ============================================================================

class User(Base):
    """User account for authentication and authorization."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Authentication fields
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash

    # Profile fields
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Settings (JSONB for flexibility)
    settings = Column(JSONB, default=dict, nullable=False)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_username', 'username'),
        Index('idx_users_is_active', 'is_active'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


# ============================================================================
# API Key Model
# ============================================================================

class APIKey(Base):
    """API Key for programmatic access."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # API key fields
    key_hash = Column(String(255), unique=True, nullable=False, index=True)  # SHA-256 hash
    name = Column(String(255), nullable=False)  # Human-readable name
    prefix = Column(String(10), nullable=False)  # First 8 chars for identification

    # Scopes and permissions
    scopes = Column(JSONB, default=list, nullable=False)  # ["read:items", "write:items"]

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Metadata
    meta_data = Column(JSONB, default=dict, nullable=False)  # { "ip_whitelist": [...], "user_agent": "..." }

    # Relationship
    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index('idx_api_keys_user', 'user_id'),
        Index('idx_api_keys_key_hash', 'key_hash'),
        Index('idx_api_keys_is_active', 'is_active'),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.prefix})>"


# ============================================================================
# Session Model
# ============================================================================

class Session(Base):
    """User session for JWT token management."""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Session fields
    token_hash = Column(String(255), unique=True, nullable=False, index=True)  # JWT hash
    refresh_token_hash = Column(String(255), unique=True, nullable=True, index=True)

    # Device and location info
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index('idx_sessions_user', 'user_id'),
        Index('idx_sessions_token_hash', 'token_hash'),
        Index('idx_sessions_is_active', 'is_active'),
        Index('idx_sessions_expires_at', 'expires_at'),
    )

    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"


# ============================================================================
# Role Model
# ============================================================================

class Role(Base):
    """Role for RBAC (Role-Based Access Control)."""

    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Role fields
    name = Column(String(100), unique=True, nullable=False, index=True)  # "admin", "user", "viewer"
    description = Column(Text, nullable=True)

    # Permissions
    permissions = Column(JSONB, default=list, nullable=False)  # ["create:item", "read:item", ...]

    # Hierarchy (for role inheritance)
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    parent_role = relationship("Role", remote_side=[id], backref="child_roles")
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_roles_name', 'name'),
    )

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


# ============================================================================
# UserRole Model (Many-to-Many)
# ============================================================================

class UserRole(Base):
    """User-Role assignment for RBAC."""

    __tablename__ = "user_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    # Context (optional: role can be scoped to a workspace)
    workspace_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        Index('idx_user_roles_user', 'user_id'),
        Index('idx_user_roles_role', 'role_id'),
        Index('idx_user_roles_workspace', 'workspace_id'),
        # Ensure unique user-role per workspace
        Index('idx_user_roles_unique', 'user_id', 'role_id', 'workspace_id', unique=True),
    )

    def __repr__(self):
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


# ============================================================================
# Audit Log Model
# ============================================================================

class AuditLog(Base):
    """Audit log for security events."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event info
    event_type = Column(String(100), nullable=False, index=True)  # "user.login", "user.logout", "api_key.create"
    actor_id = Column(UUID(as_uuid=True), nullable=True)  # User who performed the action
    actor_type = Column(String(50), nullable=True)  # "user", "system"

    # Target info
    target_type = Column(String(50), nullable=True)  # "user", "api_key", "workspace"
    target_id = Column(UUID(as_uuid=True), nullable=True)

    # Details
    details = Column(JSONB, default=dict, nullable=False)  # Event-specific data
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Status
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index('idx_audit_logs_event_type', 'event_type'),
        Index('idx_audit_logs_actor', 'actor_id', 'actor_type'),
        Index('idx_audit_logs_target', 'target_type', 'target_id'),
        Index('idx_audit_logs_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, event_type={self.event_type}, success={self.success})>"
