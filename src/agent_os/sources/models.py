"""PRD10 ``Source`` ORM table (§5.4)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class SourceType(str, enum.Enum):
    """PRD10 §5.4 source type."""

    LINK = "link"
    FILE = "file"
    AUDIO = "audio"
    IMAGE = "image"


class Source(Base):
    """Raw source artifact (file, link, audio, image).

    A Source is created by Capture endpoints **before** parsing happens.
    Documents and Cards reference the source via ``source_id`` so the
    pipeline can re-parse / replay if needed.
    """

    __tablename__ = "prd10_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    source_type = Column(String(20), nullable=False, index=True)

    name = Column(String(500), nullable=True)
    url = Column(String(2000), nullable=True)
    storage_path = Column(String(500), nullable=True)
    storage_bucket = Column(String(100), nullable=True)

    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    checksum = Column(String(128), nullable=True)

    extra = Column(JSON, default=dict, nullable=False)

    parse_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    parse_error = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index('idx_prd10_sources_user_type_created', 'user_id', 'source_type', 'created_at'),
        Index('idx_prd10_sources_parse_status', 'parse_status'),
    )

    def __repr__(self) -> str:
        return (
            f"<Source(id={self.id}, type={self.source_type}, "
            f"name={self.name!r})>"
        )

    def to_prd10_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "source_type": self.source_type,
            "name": self.name,
            "url": self.url,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "parse_status": self.parse_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
