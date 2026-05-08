"""Audit logging system for compliance and security.

Tracks all data access and modifications for:
- Compliance (GDPR, SOC2, HIPAA)
- Security investigations
- Debugging and troubleshooting
- User activity analytics
"""

from typing import Any, Dict, Optional

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from agent_os.db.base import Base


class AuditLog(Base):
    """Audit log for tracking data access and modifications.

    Records every create/read/update/delete operation on sensitive data.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # NULL for system operations

    # Action details
    action = Column(String(50), nullable=False, index=True)  # create, read, update, delete
    table_name = Column(String(50), nullable=False, index=True)  # cards, tasks, users, etc.
    record_id = Column(Integer, index=True)  # ID of affected record

    # Data changes
    old_values = Column(JSON, nullable=True)  # Values before change (for update/delete)
    new_values = Column(JSON, nullable=True)  # Values after change (for create/update)

    # Request context
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(100), nullable=True)  # For tracing

    # Result
    status = Column(String(20), default="success")  # success, failure, error
    error_message = Column(String(500), nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        CheckConstraint("action IN ('create', 'read', 'update', 'delete')", name='ck_audit_action'),
        CheckConstraint("status IN ('success', 'failure', 'error')", name='ck_audit_status'),
        # Composite indexes for common queries
        Index('idx_audit_org_action', 'organization_id', 'action'),
        Index('idx_audit_org_table', 'organization_id', 'table_name'),
        Index('idx_audit_user_action', 'user_id', 'action'),
        Index('idx_audit_created_at', 'created_at'),
    )


# ============================================================================
# Audit logger
# ============================================================================

class AuditLogger:
    """Audit logger for recording data operations.

    Usage:
        ```python
        from agent_os.db.audit import audit_logger

        # Record creation
        await audit_logger.log_create(
            db=session,
            organization_id=user.organization_id,
            user_id=user.id,
            table_name="cards",
            record_id=card.id,
            new_values={"title": "My Card", "content": "..."},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )

        # Record update
        await audit_logger.log_update(
            db=session,
            organization_id=user.organization_id,
            user_id=user.id,
            table_name="cards",
            record_id=card.id,
            old_values={"title": "Old Title"},
            new_values={"title": "New Title"},
        )
        ```
    """

    async def log_create(
        self,
        db: AsyncSession,
        organization_id: int,
        user_id: int | None,
        table_name: str,
        record_id: int,
        new_values: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ):
        """Log a create operation."""
        log_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="create",
            table_name=table_name,
            record_id=record_id,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            status=status,
            error_message=error_message,
        )
        db.add(log_entry)

    async def log_read(
        self,
        db: AsyncSession,
        organization_id: int,
        user_id: int | None,
        table_name: str,
        record_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ):
        """Log a read operation."""
        log_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="read",
            table_name=table_name,
            record_id=record_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            status="success",
        )
        db.add(log_entry)

    async def log_update(
        self,
        db: AsyncSession,
        organization_id: int,
        user_id: int | None,
        table_name: str,
        record_id: int,
        old_values: dict[str, Any],
        new_values: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ):
        """Log an update operation."""
        log_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="update",
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            status=status,
            error_message=error_message,
        )
        db.add(log_entry)

    async def log_delete(
        self,
        db: AsyncSession,
        organization_id: int,
        user_id: int | None,
        table_name: str,
        record_id: int,
        old_values: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ):
        """Log a delete operation."""
        log_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="delete",
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            status=status,
            error_message=error_message,
        )
        db.add(log_entry)

    async def log_error(
        self,
        db: AsyncSession,
        organization_id: int,
        user_id: int | None,
        table_name: str,
        action: str,
        error_message: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ):
        """Log a failed operation."""
        log_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            table_name=table_name,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            status="error",
            error_message=error_message,
        )
        db.add(log_entry)


# Global audit logger instance
audit_logger = AuditLogger()


# ============================================================================
# FastAPI dependency for audit logging
# ============================================================================

from fastapi import Request

from agent_os.auth.models import User


async def get_audit_context(
    request: Request,
    current_user: User
) -> dict[str, Any]:
    """Extract audit context from FastAPI request.

    Returns dict with:
    - organization_id
    - user_id
    - ip_address
    - user_agent
    - request_id

    Usage:
        ```python
        from fastapi import Depends
        from agent_os.db.audit import get_audit_context, audit_logger

        @router.post("/cards")
        async def create_card(
            card_in: CardCreate,
            db: AsyncSession = Depends(get_db),
            current_user: User = Depends(get_current_user),
            audit_context: Dict = Depends(get_audit_context)
        ):
            # Create card
            card = await create_card(db, card_in, current_user)

            # Log creation
            await audit_logger.log_create(
                db=db,
                organization_id=audit_context['organization_id'],
                user_id=audit_context['user_id'],
                table_name="cards",
                record_id=card.id,
                new_values=card_in.dict(),
                ip_address=audit_context['ip_address'],
                user_agent=audit_context['user_agent'],
                request_id=audit_context['request_id']
            )

            return card
        ```
    """
    return {
        "organization_id": current_user.organization_id,
        "user_id": current_user.id,
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request.headers.get("x-request-id"),
    }
