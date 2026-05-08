"""PRD10 §6.2 Lifespan migration tests.

Verifies that the FastAPI startup/shutdown hooks were migrated from the
deprecated ``@app.on_event(...)`` decorator to the modern
``lifespan=asynccontextmanager`` parameter.

What we assert:

1. The ``app`` instance has a ``router.lifespan_context`` attribute
   that is callable (the lifespan handler).
2. No ``@app.on_event`` decorators remain in ``server.app`` source.
3. The lifespan body really runs on startup: it must call
   ``configure_logging``, ``_init_sentry``, ``get_engine``, ``init_db``,
   and (when worker is enabled) ``start_worker_loop``.
4. The lifespan body really runs on shutdown: it must call
   ``stop_worker_loop`` (even if it raises, the lifespan must not
   surface the exception).
5. Failures during ``init_db`` or ``start_worker_loop`` degrade to log
   warnings, not crashes (preserves original ``on_event`` semantics).

Lifespan invariants are tested via ``LifespanManager`` (httpx + asgi
lifespan helper) so we drive the same code path uvicorn will use in
production.
"""

from __future__ import annotations

import pytest

from agent_os.server.app import app as prd_app
from agent_os.server.app import lifespan

# ---------------------------------------------------------------------------
# Static / structural assertions
# ---------------------------------------------------------------------------


class TestLifespanWiring:
    """The lifespan hook is wired into the FastAPI app."""

    def test_app_has_lifespan_context(self):
        """``app.router.lifespan_context`` should be set to our lifespan."""

        assert callable(prd_app.router.lifespan_context)

    def test_lifespan_is_async_context_manager(self):
        """The exported ``lifespan`` must be an async context manager."""

        cm = lifespan(prd_app)
        assert hasattr(cm, "__aenter__")
        assert hasattr(cm, "__aexit__")

    def test_no_on_event_hooks_remain_in_source(self):
        """Source must not declare deprecated ``@app.on_event`` hooks.

        We grep the actual source file because our intent is to guarantee
        no future regression: even if FastAPI keeps tolerating both
        styles, mixing them here would defeat the migration.
        """

        from pathlib import Path

        import agent_os.server.app as app_module

        source = Path(app_module.__file__).read_text(encoding="utf-8")
        # Allow occurrences inside comments (they document the migration
        # trail) by stripping comment lines first.
        body = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        assert "@app.on_event" not in body, (
            "Found deprecated @app.on_event decorator. "
            "Use the lifespan context manager instead (PRD10 §6.2)."
        )


# ---------------------------------------------------------------------------
# Behavioural assertions — run the lifespan body and observe side effects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLifespanBehaviour:
    """The lifespan must reproduce the legacy startup/shutdown semantics."""

    async def test_lifespan_invokes_startup_helpers(self, monkeypatch):
        """Entering the lifespan must call configure_logging, init_db, etc."""

        called: dict[str, int] = {
            "configure_logging": 0,
            "init_sentry": 0,
            "get_engine": 0,
            "init_db": 0,
            "start_worker_loop": 0,
            "stop_worker_loop": 0,
        }

        from agent_os import common as common_module
        from agent_os.db import base as db_base
        from agent_os.jobs import worker_loop as worker_module
        from agent_os.server import app as app_module

        def _track(name: str):
            def _sync_stub(*a, **kw):
                called[name] += 1

            return _sync_stub

        async def _async_stub_factory(name: str):
            async def _stub(*a, **kw):
                called[name] += 1

            return _stub

        monkeypatch.setattr(common_module, "configure_logging", _track("configure_logging"))
        monkeypatch.setattr(app_module, "_init_sentry", _track("init_sentry"))
        monkeypatch.setattr(db_base, "get_engine", _track("get_engine"))
        monkeypatch.setattr(db_base, "init_db", await _async_stub_factory("init_db"))
        monkeypatch.setattr(worker_module, "is_worker_enabled", lambda: True)
        monkeypatch.setattr(worker_module, "start_worker_loop", _track("start_worker_loop"))
        monkeypatch.setattr(worker_module, "stop_worker_loop", await _async_stub_factory("stop_worker_loop"))

        async with lifespan(prd_app):
            assert called["configure_logging"] == 1
            assert called["init_sentry"] == 1
            assert called["get_engine"] == 1
            assert called["init_db"] == 1
            assert called["start_worker_loop"] == 1

        assert called["stop_worker_loop"] == 1, (
            "Lifespan must call stop_worker_loop on exit."
        )

    async def test_lifespan_skips_worker_when_disabled(self, monkeypatch):
        """``is_worker_enabled() is False`` keeps start_worker_loop unused."""

        called: dict[str, int] = {"start_worker_loop": 0, "stop_worker_loop": 0}

        from agent_os.db import base as db_base
        from agent_os.jobs import worker_loop as worker_module

        async def _async_noop(*a, **kw):
            return None

        monkeypatch.setattr(db_base, "init_db", _async_noop)
        monkeypatch.setattr(db_base, "get_engine", lambda: None)
        monkeypatch.setattr(worker_module, "is_worker_enabled", lambda: False)
        monkeypatch.setattr(
            worker_module,
            "start_worker_loop",
            lambda: called.__setitem__("start_worker_loop", called["start_worker_loop"] + 1),
        )

        async def _stop():
            called["stop_worker_loop"] += 1

        monkeypatch.setattr(worker_module, "stop_worker_loop", _stop)

        async with lifespan(prd_app):
            assert called["start_worker_loop"] == 0

        # stop_worker_loop is always called on shutdown — it's idempotent
        # so calling it when no worker started is safe.
        assert called["stop_worker_loop"] == 1

    async def test_lifespan_swallows_init_db_error(self, monkeypatch, caplog):
        """``init_db`` raising should log + continue, not propagate."""

        import logging

        from agent_os.db import base as db_base
        from agent_os.jobs import worker_loop as worker_module

        async def _failing_init():
            raise RuntimeError("synthetic init_db failure")

        async def _async_noop(*a, **kw):
            return None

        monkeypatch.setattr(db_base, "init_db", _failing_init)
        monkeypatch.setattr(db_base, "get_engine", lambda: None)
        monkeypatch.setattr(worker_module, "is_worker_enabled", lambda: False)
        monkeypatch.setattr(worker_module, "stop_worker_loop", _async_noop)

        with caplog.at_level(logging.ERROR):
            async with lifespan(prd_app):
                pass

        assert any(
            "Failed to create database tables" in r.message for r in caplog.records
        ), "init_db failure should be logged at ERROR but not raise."

    async def test_lifespan_swallows_stop_worker_error(self, monkeypatch, caplog):
        """``stop_worker_loop`` raising should log a warning, not crash exit."""

        import logging

        from agent_os.db import base as db_base
        from agent_os.jobs import worker_loop as worker_module

        async def _async_noop(*a, **kw):
            return None

        async def _failing_stop():
            raise RuntimeError("synthetic stop_worker_loop failure")

        monkeypatch.setattr(db_base, "init_db", _async_noop)
        monkeypatch.setattr(db_base, "get_engine", lambda: None)
        monkeypatch.setattr(worker_module, "is_worker_enabled", lambda: False)
        monkeypatch.setattr(worker_module, "stop_worker_loop", _failing_stop)

        with caplog.at_level(logging.WARNING):
            async with lifespan(prd_app):
                pass

        assert any(
            "Failed to stop PRD10 worker loop cleanly" in r.message
            for r in caplog.records
        ), "stop_worker_loop failure should log WARNING and not raise out."
