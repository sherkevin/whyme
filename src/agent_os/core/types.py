from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RuntimeContext(BaseModel):
    """Request-scoped context to keep interfaces stateless."""

    session_id: str
    user_id: str
    trace_id: str
    sandbox_id: Optional[str] = None


class PruningReport(BaseModel):
    """Report for context pruning/processing results."""

    original_tokens: int
    remaining_tokens: int
    pruned_count: int
    strategy_used: str
    summary_content: Optional[str] = None
