"""Authentication and user models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base


class Organization(Base):
    """Organization/Tenant model for multi-tenancy."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    plan = Column(String(20), default="free")  # free, pro, enterprise
    max_users = Column(Integer, default=1)
    max_storage_gb = Column(Integer, default=1)
    is_active = Column(Boolean, default=True, index=True)

    # 独立数据库配置（用于企业客户）
    db_host = Column(String(255))  # 独立数据库主机
    db_port = Column(Integer)  # 端口
    db_name = Column(String(100))  # 独立数据库名
    db_user = Column(String(100))  # 数据库用户
    db_password = Column(String(255))  # 加密存储的密码

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="organization")

    __table_args__ = (
        Index('idx_org_plan_active', 'plan', 'is_active'),
    )


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)  # 移除 unique，改为复合约束
    email = Column(String(100), nullable=False, index=True)  # 移除 unique，改为复合约束
    hashed_password = Column(String(255), nullable=False)

    # 状态字段
    is_active = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False)  # 组织管理员

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="users")
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    inbox_items = relationship("InboxItem", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        # 同一组织内用户名唯一
        UniqueConstraint('organization_id', 'username', name='uq_org_username'),
        # 同一组织内邮箱唯一
        UniqueConstraint('organization_id', 'email', name='uq_org_email'),
        # 复合索引用于常见查询
        Index('idx_user_org_active', 'organization_id', 'is_active'),
    )


class UserSettings(Base):
    """User settings and preferences."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    daily_goal = Column(Integer, default=10)  # Daily goal (节奏/KPI)
    theme = Column(String(20), default="light")  # Theme preference
    language = Column(String(10), default="zh")  # Language preference
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="settings")
