"""Unified Items Model - PRD4 Implementation."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Float, Boolean, Integer, Index, CheckConstraint, ARRAY, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

# Try to import pgvector, fallback to ARRAY
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    Vector = None
    PGVECTOR_AVAILABLE = False

from agent_os.db.base import Base


class ItemType(str, Enum):
    """Item 类型枚举 - PRD4 规范"""
    NOTE = "note"
    TASK = "task"
    RESOURCE = "resource"
    PLAN = "plan"
    INSIGHT = "insight"


class ItemStatus(str, Enum):
    """Item 状态枚举 - PA 阶段二扩展"""
    RAW = "raw"               # 新增：原始输入，未处理
    PROCESSED = "processed"     # 新增：已由 Agent 处理
    ACTIVE = "active"          # 保留：活跃状态
    ARCHIVED = "archived"      # 保留：已归档
    DELETED = "deleted"        # 保留：已删除


class RelationType(str, Enum):
    """关系类型枚举 - 用于 Graph Edges"""
    TOPIC = "topic"
    CAUSAL = "causal"
    SUPPLEMENT = "supplement"


class Workspace(Base):
    """Workspace 模型 - PRD4 单 Workspace 设计"""

    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(UUID(as_uuid=True), nullable=False)  # FK to users.id
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_workspace_owner', 'owner_id'),
    )


class Area(Base):
    """Area 模型 - PRD4 层次结构"""

    __tablename__ = "areas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # hex color
    icon = Column(String(50), nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("areas.id", ondelete="CASCADE"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="areas")
    parent = relationship("Area", remote_side=[id], backref="children")

    __table_args__ = (
        Index('idx_areas_workspace', 'workspace_id'),
        Index('idx_areas_parent', 'parent_id'),
    )


class Project(Base):
    """Project 模型 - PRD4 层次结构"""

    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active, archived, completed
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="projects")
    area = relationship("Area", backref="projects")

    __table_args__ = (
        Index('idx_projects_workspace', 'workspace_id'),
        Index('idx_projects_area', 'area_id'),
    )


class Item(Base):
    """统一内容索引 - PRD4 核心模型"""

    __tablename__ = "items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    creator_id = Column(UUID(as_uuid=True), nullable=False)  # FK to users.id
    type = Column(String(20), nullable=False)  # note, task, resource, plan, insight

    # 核心内容 (参与混合检索)
    title = Column(Text, nullable=True)  # 权重最高
    content = Column(Text, nullable=True)  # 原始内容 (Source of Truth)
    summary = Column(Text, nullable=True)  # Agent 生成的摘要/结构化表达
    # Conditional embedding column (pgvector or JSON fallback)
    if PGVECTOR_AVAILABLE and Vector:
        embedding = Column(Vector(1536), nullable=True)
    else:
        embedding = Column(JSON, nullable=True)  # Fallback to JSON for SQLite

    # 全文搜索支持 (混合检索 - Stage 2)
    title_tsv = Column(Text, nullable=True)  # 预处理的标题 (小写化)
    content_tsv = Column(Text, nullable=True)  # 预处理的内容 (小写化)

    # 结构化归属 (V1 冻结结构)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    # 来源追踪 (WeChat/Web Clip)
    source_type = Column(String(20), nullable=True)  # 'manual', 'wechat', 'chrome_extension'
    source_meta = Column(JSON, nullable=True, default=dict)  # { "url": "...", "wechat_sender": "...", "thumb": "..." }

    # 状态
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="items")
    area = relationship("Area", backref="items")
    project = relationship("Project", backref="items")
    process_events = relationship("AgentProcessEvent", back_populates="item", cascade="all, delete-orphan")

    # Properties for enum access (backward compatibility with card_generator)
    @property
    def item_type(self):
        """Get type as ItemType enum."""
        if self.type:
            try:
                return ItemType(self.type)
            except (ValueError, KeyError):
                # If type is not a valid ItemType, return None
                return None
        return None

    @item_type.setter
    def item_type(self, value):
        """Set type from ItemType enum."""
        if value is None:
            self.type = None
        elif isinstance(value, ItemType):
            self.type = value.value
        else:
            self.type = str(value)

    @property
    def status_enum(self):
        """Get status as ItemStatus enum."""
        if self.status:
            try:
                return ItemStatus(self.status)
            except (ValueError, KeyError):
                # If status is not a valid ItemStatus, return None
                return None
        return None

    @status_enum.setter
    def status_enum(self, value):
        """Set status from ItemStatus enum."""
        if value is None:
            self.status = None
        elif isinstance(value, ItemStatus):
            self.status = value.value
        else:
            self.status = str(value)

    __table_args__ = (
        Index('idx_items_workspace_user', 'workspace_id', 'creator_id'),
        Index('idx_items_type', 'type'),
        Index('idx_items_area', 'area_id'),
        Index('idx_items_project', 'project_id'),
        Index('idx_items_status', 'status'),
        Index('idx_items_title', 'title'),  # 标题搜索索引
        Index('idx_items_content', 'content'),  # 内容搜索索引
        Index('idx_items_updated', 'updated_at'),  # 时间排序索引
        # pgvector IVFFlat index (需要单独创建)
    )


class TaskExtension(Base):
    """Task 扩展 - PRD4 决策审计字段"""

    __tablename__ = "task_extensions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, unique=True)

    # PRD4 扩展字段
    goal = Column(Text, nullable=True)  # 任务目标
    constraints = Column(Text, nullable=True)  # 约束条件
    risk_level = Column(String(20), nullable=False, default="low")  # Low / Medium / High
    execution_status = Column(String(20), nullable=False, default="draft")  # Draft / Planning / Decision / Executing / Done

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    item = relationship("Item", backref="task_extension")

    __table_args__ = (
        CheckConstraint("risk_level IN ('low', 'medium', 'high')", name='check_risk_level'),
        CheckConstraint("execution_status IN ('draft', 'planning', 'decision', 'executing', 'done')", name='check_execution_status'),
    )


class DecisionPoint(Base):
    """决策点 - PRD4 Agent Accountability"""

    __tablename__ = "decision_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)

    type = Column(String(20), nullable=False)  # Selection / Info / Boundary
    options = Column(JSON, nullable=False, default=list)  # [{ "summary": "...", "risks": "...", "cost": "..." }]
    user_choice = Column(UUID(as_uuid=True), nullable=True)  # 记录用户最终选择的 option_id
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    task = relationship("Item", backref="decision_points")

    __table_args__ = (
        Index('idx_decision_points_task', 'task_id'),
        CheckConstraint("type IN ('selection', 'info', 'boundary')", name='check_decision_type'),
    )


class LedgerEvent(Base):
    """不可篡改审计日志 - PRD4 Agent Accountability"""

    __tablename__ = "ledger_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(50), nullable=False)  # AgentSuggested / UserConfirmed / DeliverableGenerated
    snapshot = Column(JSON, nullable=False, default=dict)  # 记录当时的完整上下文快照

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    task = relationship("Item", backref="ledger_events")

    __table_args__ = (
        Index('idx_ledger_events_task', 'task_id'),
        CheckConstraint("event_type IN ('agent_suggested', 'user_confirmed', 'deliverable_generated')", name='check_event_type'),
    )

    # 设计约束: 此表只增不改 (Append Only) - 需在应用层实现


class GraphEdge(Base):
    """认知图谱边 - PRD4 Cognitive Graph"""

    __tablename__ = "graph_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_node_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    to_node_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)

    weight = Column(Float, nullable=False, default=0.0)
    relation_type = Column(String(20), nullable=False)  # Topic / Causal / Supplement
    is_strong = Column(Boolean, nullable=False, default=False)  # 是否为强连接

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    from_node = relationship("Item", foreign_keys=[from_node_id], backref="outgoing_edges")
    to_node = relationship("Item", foreign_keys=[to_node_id], backref="incoming_edges")

    __table_args__ = (
        Index('idx_graph_from', 'from_node_id'),
        Index('idx_graph_to', 'to_node_id'),
        Index('idx_graph_strong', 'is_strong'),
        # 防止重复边
        Index('unique_edge', 'from_node_id', 'to_node_id', unique=True),
        CheckConstraint("relation_type IN ('topic', 'causal', 'supplement')", name='check_relation_type'),
        CheckConstraint("weight >= 0 AND weight <= 1", name='check_weight_range'),
    )
