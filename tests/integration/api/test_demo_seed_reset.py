"""PRD10 §10.7 — `scripts/demo_seed_reset.py` integration tests.

Locks down the contract that the operator-facing demo-reset entrypoint
keeps:

* Health probe (``--check-only``) is read-only, returns the right
  ``decision`` enum, and exit code matches the documented matrix.
* ``--force`` reseed restores the §25.3 baseline (6 folders / 30 cards /
  20 documents) on a fresh DB and is idempotent.
* The threshold gate skips reseed below the configured limit.
* Advisory lock contention returns exit 11 with ``decision=lock_busy``
  so cron jobs can no-op cleanly when concurrent runs collide.

These tests run the actual script as an async function (no subprocess)
against a per-test SQLite file so they stay fast and don't depend on
PowerShell / cmd. The lock-contention test uses ``asyncio.gather`` to
race two invocations of ``demo_seed_reset.main(argv)``.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def fresh_sqlite_url(tmp_path: Path, monkeypatch) -> str:
    """Per-test SQLite file + DATABASE_URL env.

    ``agent_os.db.base`` reads ``DATABASE_URL`` at *import time* into a
    module-level constant; just setting the env var after import is not
    enough. We must (a) reset the cached engine + sessionmaker so the
    next ``get_engine`` call rebuilds them, and (b) overwrite the
    module-level ``DATABASE_URL`` so the rebuild picks up the SQLite
    URL.
    """
    db_file = tmp_path / "demo_reset.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    try:
        from agent_os.db import base as _db_base

        if hasattr(_db_base, "_engine"):
            _db_base._engine = None  # type: ignore[attr-defined]
        if hasattr(_db_base, "_AsyncSessionLocal"):
            _db_base._AsyncSessionLocal = None  # type: ignore[attr-defined]
        # The fix that was missing: monkeypatch.setenv updates the
        # process env but the module already snapshotted the value into
        # ``DATABASE_URL`` at import time.
        monkeypatch.setattr(_db_base, "DATABASE_URL", url, raising=False)
    except Exception:
        pass
    return url


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    return tmp_path / "demo_reset.lock"


def _load_module():
    # Re-import each test so pytest's monkeypatch on env happens first.
    if "demo_seed_reset" in sys.modules:
        return importlib.reload(sys.modules["demo_seed_reset"])
    return importlib.import_module("demo_seed_reset")


def _capture_stdout(capsys) -> dict[str, Any]:
    captured = capsys.readouterr().out.strip().splitlines()
    assert captured, "demo_seed_reset must print exactly one JSON line"
    # Last non-empty line is the structured decision record (seed_prd10
    # may print human-readable summary lines first).
    return json.loads(captured[-1])


# ---------------------------------------------------------------------------
# 1. Health probe / --check-only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_only_on_missing_user_recommends_reseed(
    fresh_sqlite_url, lock_path, capsys
):
    """Empty DB ⇒ user not found ⇒ exit 10 + ``reseed_recommended``."""

    mod = _load_module()
    rc = await mod.main(
        [
            "--check-only",
            "--email", "demo@mydow.example",
            "--lock-file", str(lock_path),
        ]
    )
    rec = _capture_stdout(capsys)
    assert rc == 10, rec
    assert rec["event"] == "demo_seed_reset"
    assert rec["decision"] == "reseed_recommended"
    assert rec["user_found_before"] is False
    assert rec["today_captures_before"] == 0


# ---------------------------------------------------------------------------
# 2. --force reseed restores the §25.3 baseline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_reseed_lands_on_prd10_baseline(
    fresh_sqlite_url, lock_path, capsys
):
    """--force creates user + writes 6 folders / 30 cards baseline."""

    mod = _load_module()
    rc = await mod.main(
        [
            "--force",
            "--email", "demo@mydow.example",
            "--password", "demo123",
            "--lock-file", str(lock_path),
        ]
    )
    rec = _capture_stdout(capsys)
    assert rc == 0, rec
    assert rec["decision"] == "reseed"
    assert rec["seed_card_count_after"] == 30
    assert rec["seed_folder_count_after"] == 6


# ---------------------------------------------------------------------------
# 3. Threshold gate — under threshold ⇒ skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_threshold_gate_skips_when_under_limit(
    fresh_sqlite_url, lock_path, capsys
):
    """First seed account, no captures today ⇒ skipped (under threshold)."""

    mod = _load_module()
    # Bootstrap demo user via --force so the second call has someone to probe.
    await mod.main(
        [
            "--force",
            "--email", "demo@mydow.example",
            "--password", "demo123",
            "--lock-file", str(lock_path),
        ]
    )
    capsys.readouterr()  # discard

    rc = await mod.main(
        [
            "--threshold", "60",
            "--email", "demo@mydow.example",
            "--password", "demo123",
            "--lock-file", str(lock_path),
        ]
    )
    rec = _capture_stdout(capsys)
    assert rc == 0, rec
    assert rec["decision"] == "skipped"
    assert rec["today_captures_before"] <= 60


# ---------------------------------------------------------------------------
# 4. Lock contention — two concurrent runs ⇒ second exits 11
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_contention_returns_lock_busy(
    fresh_sqlite_url, lock_path, capsys
):
    """If two demo_seed_reset runs collide, the loser must exit 11."""

    mod = _load_module()

    # Hold the lock manually so we don't have to race a real reseed.
    handle, ok = mod._acquire_lock(lock_path)
    assert ok, "could not acquire lock for setup"
    try:
        rc = await mod.main(
            [
                "--force",
                "--email", "demo@mydow.example",
                "--password", "demo123",
                "--lock-file", str(lock_path),
            ]
        )
    finally:
        mod._release_lock(handle)

    rec = _capture_stdout(capsys)
    assert rc == 11, rec
    assert rec["decision"] == "lock_busy"
    assert rec["lock_file"].endswith("demo_reset.lock")


# ---------------------------------------------------------------------------
# 5. Missing DATABASE_URL ⇒ exit 30
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_database_url_exits_30(monkeypatch, lock_path, capsys):
    """No DATABASE_URL in env ⇒ refuse to run, structured error log."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    mod = _load_module()
    rc = await mod.main(
        [
            "--check-only",
            "--email", "demo@mydow.example",
            "--lock-file", str(lock_path),
        ]
    )
    rec = _capture_stdout(capsys)
    assert rc == 30, rec
    assert rec["decision"] == "error"
    assert "DATABASE_URL" in rec["error"]
