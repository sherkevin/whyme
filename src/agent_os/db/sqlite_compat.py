"""SQLite dialect compatibility for PostgreSQL UUID columns.

The PRD10 ORM models (and most pre-existing AgentOS models) declare their
primary keys with ``sqlalchemy.dialects.postgresql.UUID(as_uuid=True)``. On
PostgreSQL this maps to the native ``uuid`` type. SQLAlchemy 2.x does **not**
provide a default DDL rendering for that type on SQLite, which is the dialect
used by the test suite (``sqlite+aiosqlite:///./test.db``). Without a fallback
the very first ``Workspace.__table__.create(connection)`` call fails with::

    sqlalchemy.exc.CompileError:
        Compiler ... can't render element of type UUID

This module installs a single ``@compiles`` rule so the existing
``postgresql.UUID`` columns transparently render as ``CHAR(32)`` on SQLite,
preserving the rest of the schema and behavior. Importing this module is
side-effecting; tests that need PRD10 ORM tables on SQLite import it once
from their conftest.

The patch is intentionally **scoped to SQLite only**: PostgreSQL deployments
keep the native ``uuid`` column type unchanged, and the helper does not try
to normalize value coercion (the existing ``as_uuid=True`` Python-side
conversion already handles CHAR(32) round-trips because aiosqlite returns
the stored hex string and SQLAlchemy parses it back to ``uuid.UUID``).
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles

_PATCH_INSTALLED = False


def install() -> None:
    """Idempotently install the SQLite UUID rendering rule.

    Calling this from multiple test conftests is safe: the underlying
    ``@compiles`` registry tolerates re-registration, but we still guard with
    a module-level flag to avoid re-running the decorator on every import.
    """

    global _PATCH_INSTALLED
    if _PATCH_INSTALLED:
        return

    @compiles(PG_UUID, "sqlite")
    def _render_uuid_as_char32_on_sqlite(element, compiler, **kwargs):  # type: ignore[no-redef]
        # SQLite stores UUIDs as their 32-char hex representation. Using
        # CHAR(32) (no dashes) keeps the on-disk footprint small and matches
        # how SQLAlchemy's generic ``Uuid`` type would render. The Python-side
        # ``as_uuid=True`` flag on the column declarations still drives
        # automatic conversion to/from ``uuid.UUID`` instances.
        return "CHAR(32)"

    _PATCH_INSTALLED = True


# Auto-install on import so the simplest usage (``import
# agent_os.db.sqlite_compat``) is sufficient.
install()
