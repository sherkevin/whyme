"""PRD10 §10.7 — Demo account periodic reset entrypoint.

Wraps :func:`scripts.seed_prd10.main` so the live demo account in the
investor environment stays clean across days. Designed for unattended
execution under cron, systemd timer, or Windows Task Scheduler — see
``docs/11-deployment/demo-seed-reset.md`` for deployment recipes.

Behavior matrix
---------------

* Default (``python scripts/demo_seed_reset.py``):
  Idempotent reseed of the demo user. Equivalent to
  ``python scripts/seed_prd10.py --email demo@mydow.example
  --password demo123 --reset``.

* ``--check-only``:
  Emit a JSON health report on stdout without modifying the database.
  Reports today's capture count, total seed cards/folders, and whether
  the threshold has been crossed. Exit 0 when no action is needed,
  exit 10 when reset is recommended.

* ``--threshold N``:
  Only reseed when the demo user has accumulated more than ``N``
  captures today (default 60). Use this for cron-mode "drift detector":
  no-op on quiet days, reseed only when an investor session left noise.

* ``--force``:
  Reseed unconditionally. Useful for nightly resets where you always
  want a known-good baseline regardless of churn.

* ``--lock-file PATH``:
  Acquire a flock-style advisory lock at ``PATH`` for the duration of
  the run; exit 11 immediately if another reset is already running.
  Defaults to ``<workspace>/.tmp/demo_seed_reset.lock`` so concurrent
  cron invocations cannot collide.

Exit codes
----------

* 0   — success, including check-only "no action needed".
* 10  — check-only tripped: caller should reseed (advisory).
* 11  — another reset is already running (lock contention).
* 20  — reseed failed (see structured log line for ``error``).
* 30  — environment misconfigured (e.g. DATABASE_URL not set, or the
        demo user could not be located after seeding).

Structured logging
------------------

Every run emits a single ``info`` JSON record to stdout with these keys:

::

    {
      "event": "demo_seed_reset",
      "decision": "reseed" | "skipped" | "error" | "lock_busy",
      "threshold": 60,
      "today_captures_before": 73,
      "today_captures_after": 16,
      "duration_ms": 4823,
      "email": "demo@mydow.example",
      "ts": "2026-05-07T02:14:55+00:00"
    }

This is the contract observability tooling (Prometheus textfile
exporter / Sentry / Logstash) keys off, so don't reshape it without
updating the documented schema.

Usage
-----

::

    # Local one-shot
    python scripts/demo_seed_reset.py

    # Health check only (cron probe)
    python scripts/demo_seed_reset.py --check-only

    # Cron mode: reseed only if today's captures > 80
    python scripts/demo_seed_reset.py --threshold 80

    # Force reset, regardless of activity
    python scripts/demo_seed_reset.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Re-use seed_prd10 so we share the exact data shape PRD10 §25.3 expects.
import seed_prd10  # noqa: E402  — adjacent script in scripts/

# Defaults aligned with the live demo environment (see PRD10 §10.1).
DEFAULT_EMAIL = "demo@mydow.example"
DEFAULT_PASSWORD = "demo123"
DEFAULT_FULL_NAME = "Demo User"
DEFAULT_THRESHOLD = 60  # ≥ §25.3 baseline (30 cards) but well below noise


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PRD10 §10.7 demo seed periodic reset entrypoint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--email",
        default=os.getenv("AGENTOS_DEMO_EMAIL", DEFAULT_EMAIL),
        help=f"Demo account email (default: {DEFAULT_EMAIL})",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("AGENTOS_DEMO_PASSWORD", DEFAULT_PASSWORD),
        help="Demo account password (only used on first-run create)",
    )
    parser.add_argument(
        "--full-name",
        default=os.getenv("AGENTOS_DEMO_FULL_NAME", DEFAULT_FULL_NAME),
        help="Display name for the demo user",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Override DATABASE_URL for the reset run",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=int(os.getenv("AGENTOS_DEMO_RESET_THRESHOLD", DEFAULT_THRESHOLD)),
        help=(
            f"Skip reset when today_capture_count <= threshold "
            f"(default: {DEFAULT_THRESHOLD})"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Emit health report and exit; never write to DB.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Always reseed, ignoring --threshold.",
    )
    parser.add_argument(
        "--lock-file",
        default=str(ROOT / ".tmp" / "demo_seed_reset.lock"),
        help="Advisory lock file path (set to '' to disable locking).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed forwarded to seed_prd10 for deterministic content.",
    )
    return parser.parse_args(argv)


# ----------------------------------------------------------------------------
# Health probe — read-only count of today's captures + seed totals.
# ----------------------------------------------------------------------------


async def _probe_demo_health(email: str) -> dict[str, Any]:
    """Return today_capture_count + seed totals for the demo account.

    Returns a dict with at least ``user_found``, ``today_captures``,
    ``seed_card_count``, ``seed_folder_count``. Exceptions bubble up so
    the caller can map them to exit code 30.
    """
    from datetime import datetime as _dt
    from datetime import time as _time

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agent_os.auth.models import User
    from agent_os.db.base import get_engine, init_db
    from agent_os.inbox.prd10_models import (
        InboxItemType,
        Prd10InboxItem,
    )
    from agent_os.kb.models import Folder
    from agent_os.knowledge.models import Card

    engine = get_engine()
    await init_db()
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if user is None:
            return {
                "user_found": False,
                "today_captures": 0,
                "seed_card_count": 0,
                "seed_folder_count": 0,
            }

        today_start = _dt.combine(
            _dt.now(tz=timezone.utc).date(),
            _time.min,
        ).replace(tzinfo=timezone.utc)

        today_captures = (
            await session.execute(
                select(func.count(Prd10InboxItem.id))
                .where(Prd10InboxItem.user_id == user.id)
                .where(Prd10InboxItem.created_at >= today_start)
                .where(Prd10InboxItem.type == InboxItemType.TEXT)
            )
        ).scalar_one()

        seed_card_count = (
            await session.execute(
                select(func.count(Card.id))
                .where(Card.user_id == user.id)
            )
        ).scalar_one()

        seed_folder_count = (
            await session.execute(
                select(func.count(Folder.id))
                .where(Folder.user_id == user.id)
            )
        ).scalar_one()

        return {
            "user_found": True,
            "today_captures": int(today_captures or 0),
            "seed_card_count": int(seed_card_count or 0),
            "seed_folder_count": int(seed_folder_count or 0),
        }


# ----------------------------------------------------------------------------
# Cross-platform advisory lock (best-effort, no third-party deps).
# ----------------------------------------------------------------------------


def _acquire_lock(path: Path) -> tuple[Any, bool]:
    """Try to grab an advisory lock at ``path``.

    Returns ``(handle, ok)``. On Windows we use ``msvcrt.locking``; on
    POSIX we use ``fcntl.flock``. Either way the lock auto-releases when
    the handle is closed, so callers must keep the returned handle alive
    for the duration of the protected work.

    When ``path`` is empty we skip locking entirely and return
    ``(None, True)``.
    """
    if not str(path):
        return None, True
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+")
    try:
        if os.name == "nt":
            import msvcrt  # noqa: WPS433 — platform-specific
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                handle.close()
                return None, False
        else:
            import fcntl  # noqa: WPS433 — POSIX-only
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                handle.close()
                return None, False
    except Exception:
        handle.close()
        raise
    return handle, True


def _release_lock(handle: Any) -> None:
    if handle is None:
        return
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
    finally:
        try:
            handle.close()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Main.
# ----------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Return ``(exit_code, log_record)`` for the requested operation."""

    started = time.monotonic()
    # Apply env overrides before any agent_os import that reads settings.
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    elif not os.getenv("DATABASE_URL"):
        return 30, {
            "event": "demo_seed_reset",
            "decision": "error",
            "error": "DATABASE_URL not set; refusing to run",
            "email": args.email,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }

    log: dict[str, Any] = {
        "event": "demo_seed_reset",
        "email": args.email,
        "threshold": args.threshold,
        "ts": datetime.now(tz=timezone.utc).isoformat(),
    }

    try:
        before = await _probe_demo_health(args.email)
    except Exception as exc:  # pragma: no cover — env misconfig
        log["decision"] = "error"
        log["error"] = f"probe_failed: {type(exc).__name__}: {exc}"
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return 30, log

    log["today_captures_before"] = before["today_captures"]
    log["seed_card_count_before"] = before["seed_card_count"]
    log["seed_folder_count_before"] = before["seed_folder_count"]
    log["user_found_before"] = before["user_found"]

    if args.check_only:
        # Health probe mode: tell the caller whether reseed is recommended.
        needs_reset = (
            args.force
            or not before["user_found"]
            or before["today_captures"] > args.threshold
        )
        log["decision"] = "reseed_recommended" if needs_reset else "skipped"
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return (10 if needs_reset else 0), log

    needs_reset = (
        args.force
        or not before["user_found"]
        or before["today_captures"] > args.threshold
    )
    if not needs_reset:
        log["decision"] = "skipped"
        log["reason"] = (
            f"today_captures {before['today_captures']} <= "
            f"threshold {args.threshold}"
        )
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return 0, log

    # Forward to the canonical seeder with --reset semantics.
    seed_argv: list[str] = [
        "--email", args.email,
        "--password", args.password,
        "--full-name", args.full_name,
        "--reset",
        "--seed", str(args.seed),
    ]
    if args.database_url:
        seed_argv.extend(["--database-url", args.database_url])

    try:
        seed_rc = await seed_prd10.main(seed_argv)
    except SystemExit as exc:  # argparse may raise SystemExit(2) on bad args
        log["decision"] = "error"
        log["error"] = f"seed_systemexit: {exc.code}"
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return 20, log
    except Exception as exc:  # pragma: no cover — seeder-internal failure
        log["decision"] = "error"
        log["error"] = f"seed_failed: {type(exc).__name__}: {exc}"
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return 20, log

    if seed_rc not in (None, 0):
        log["decision"] = "error"
        log["error"] = f"seed_returned_nonzero: {seed_rc}"
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return 20, log

    try:
        after = await _probe_demo_health(args.email)
    except Exception as exc:  # pragma: no cover
        log["decision"] = "error"
        log["error"] = f"post_probe_failed: {type(exc).__name__}: {exc}"
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return 30, log

    if not after["user_found"]:
        log["decision"] = "error"
        log["error"] = "user_missing_after_seed"
        log["duration_ms"] = int((time.monotonic() - started) * 1000)
        return 30, log

    log["decision"] = "reseed"
    log["today_captures_after"] = after["today_captures"]
    log["seed_card_count_after"] = after["seed_card_count"]
    log["seed_folder_count_after"] = after["seed_folder_count"]
    log["duration_ms"] = int((time.monotonic() - started) * 1000)
    return 0, log


async def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    lock_path = Path(args.lock_file) if args.lock_file else Path("")
    handle, ok = _acquire_lock(lock_path)
    if not ok:
        record = {
            "event": "demo_seed_reset",
            "decision": "lock_busy",
            "lock_file": str(lock_path),
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }
        print(json.dumps(record, ensure_ascii=False))
        return 11

    try:
        rc, record = await _run(args)
    finally:
        _release_lock(handle)

    print(json.dumps(record, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
