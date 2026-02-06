"""Insight Models - Stage 5 Implementation.

Extended data model for Insight items.
"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, ARRAY, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base


class InsightExtension(Base):
    """Insight 扩展 - PRD4 洞察挖掘字段

    扩展 Item 模型，用于存储 insight 类型的特殊字段。
    """

    __tablename__ = "insight_extensions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Insight 核心字段
    claim = Column(Text, nullable=False)  # 洞察陈述
    rationale = Column(Text, nullable=True)  # 推理过程
    implications = Column(JSON, nullable=True, default=list)  # 启示列表

    # 去重相关
    claim_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash

    # 来源引用
    source_refs = Column(JSON, nullable=True, default=list)  # 来源 Item IDs: ["uuid1", "uuid2"]

    # 元数据
    confidence_score = Column(JSON, nullable=True)  # {"score": 0.85, "factors": [...]}
    mining_metadata = Column(JSON, nullable=True, default=dict)  # {"cluster_size": 5, "trigger": "new_connection"}

    # 审核状态
    review_status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)  # FK to users.id

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    item = relationship("Item", backref="insight_extension")

    __table_args__ = (
        Index('idx_insight_claim_hash', 'claim_hash'),
        Index('idx_insight_review_status', 'review_status'),
    )


class InsightCluster(Base):
    """Insight 集群 - 用于挖掘过程中的临时聚类

    在挖掘过程中，将相关的 items 聚类成集群，然后从集群中生成洞察。
    """

    __tablename__ = "insight_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)

    # 集群元数据
    cluster_type = Column(String(50), nullable=False)  # 'strong_connection', 'temporal', 'topic'
    item_ids = Column(JSON, nullable=False)  # ["uuid1", "uuid2", ...]
    cluster_score = Column(JSON, nullable=True)  # {"avg_connection": 0.8, "size": 5}

    # 挖掘状态
    mining_status = Column(String(20), nullable=False, default="pending")  # pending, mining, completed, failed
    insight_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace", backref="insight_clusters")
    insight = relationship("Item", foreign_keys=[insight_id])

    __table_args__ = (
        Index('idx_insight_clusters_workspace', 'workspace_id'),
        Index('idx_insight_clusters_status', 'mining_status'),
    )


# ============================================================================
# Helper Functions
# ============================================================================

def generate_claim_hash(claim: str) -> str:
    """
    生成 Claim 的 Canonical Hash

    归一化 Claim 后计算 SHA-256 hash，用于去重。

    Args:
        claim: 原始 claim 文本

    Returns:
        SHA-256 hash (hex string)
    """
    # 归一化: 转小写，移除多余空格，移除标点
    normalized = claim.lower().strip()
    normalized = " ".join(normalized.split())

    # 移除常见标点
    for char in ".,!?;:，。！？；：":
        normalized = normalized.replace(char, "")

    # 计算 SHA-256
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def normalize_claim(claim: str) -> str:
    """
    归一化 Claim 用于去重比较

    Args:
        claim: 原始 claim

    Returns:
        归一化后的 claim
    """
    normalized = claim.lower().strip()
    normalized = " ".join(normalized.split())
    for char in ".,!?;:，。！？；：":
        normalized = normalized.replace(char, "")
    return normalized
