"""Compatibility shim re-exporting the FastAPI ``app`` for legacy callers.

Some legacy tests and scripts do ``from agent_os.main import app``. The
canonical entry point is ``agent_os.server.app:app``; this module simply
re-exports it.
"""

from __future__ import annotations

try:
    from agent_os.server.app import app  # type: ignore[import]
except Exception:  # pragma: no cover - optional dep fallback
    from fastapi import FastAPI

    app = FastAPI(title="agent_os main shim")

__all__ = ["app"]
