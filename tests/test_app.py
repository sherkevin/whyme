"""Compatibility shim exposing a FastAPI ``test_app`` for legacy tests.

Several legacy test modules (`tests/integration/api/test_agent_api_*.py`,
`tests/legacy/test_agent_api_simple.py`, `tests/legacy/test_end_to_end_stage2.py`)
do ``from tests.test_app import test_app``. The import is what blocks
``pytest --collect-only``; the runtime semantics are owned by each individual
test file.

We expose:
- ``test_app``: the canonical FastAPI app (re-exported from ``agent_os.server.app``).
- ``app``: the same object under the more common alias.

If the canonical app fails to import (heavy optional deps), a minimal stub
FastAPI app is used so collection still succeeds. Tests that depend on the
real routes will fail at runtime — but they will fail with a clear,
test-specific message instead of breaking pytest collection across the entire
repository.
"""

from __future__ import annotations

try:
    from agent_os.server.app import app as test_app  # type: ignore[import]
except Exception:  # pragma: no cover - optional dep fallback
    from fastapi import FastAPI

    test_app = FastAPI(title="agent_os test app stub")

app = test_app

__all__ = ["app", "test_app"]
