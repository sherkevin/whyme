"""Agent-related data models for PA 1.0 Stage 2.

This module contains database models for tracking agent processing events.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship

from agent_os.db.base import Base


class AgentProcessEvent(Base):
    """Agent 处理事件记录.

    用于追踪 Agent 对每个 InboxItem 的处理历史。
    """
    __tablename__ = "agent_process_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()), index=True)

    # 关联的 Item
    item_id = Column(String(36), ForeignKey("items.id"), nullable=False, index=True)

    # 状态转换
    from_status = Column(String(50), nullable=False)  # 处理前状态
    to_status = Column(String(50), nullable=False)    # 处理后状态

    # 处理结果
    result_summary = Column(JSON, nullable=True, default=dict)
    # 示例: {
    #     "title": "Generated Title",
    #     "summary_length": 150,
    #     "item_type": "task",
    #     "confidence": "high"
    # }

    # 错误信息（如果处理失败）
    error_message = Column(Text, nullable=True)

    # 处理元数据
    event_metadata = Column(JSON, nullable=True, default=dict)
    # 示例: {
    #     "processing_time_ms": 123,
    #     "processor_version": "1.0",
    #     "forced_reprocess": false
    # }

    # 时间戳
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关系
    item = relationship("Item", back_populates="process_events")

    def __repr__(self):
        return (
            f"<AgentProcessEvent(id={self.id}, "
            f"item_id={self.item_id}, "
            f"from_status={self.from_status}, "
            f"to_status={self.to_status})>"
        )


# 在 Item 模型中添加反向关系（需要在 items/models.py 中添加）
# process_events = relationship("AgentProcessEvent", back_populates="item", cascade="all, delete-orphan")
