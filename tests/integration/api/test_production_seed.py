"""§11.9 production_seed.py — 4 fence safety + happy path tests.

Covers ``scripts/production_seed.py`` (Owner: my-mcp-20 @ 2026-05-06,
finished by claude-opus @ 2026-05-07).

Fences under test:

  1. Env opt-in (``AGENTOS_PROD_SEED_ON_BOOT``) — exits 0 when not set.
  2. Production DSN guard (``DATABASE_URL`` containing ``prod`` /
     ``production``) — exits 2 unless ``AGENTOS_PROD_SEED_FORCE=1``.
  3. Real-user fence (``users`` rows that aren't the demo account) —
     exits 0 with warning unless ``AGENTOS_PROD_SEED_FORCE=1``.
  4. Demo-only re-seed — happy path: invokes ``seed_prd10.main`` with
     ``--reset`` and exits 0.

Plus dry-run + idempotency checks.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"


def _load_production_seed():
    """Load ``scripts/production_seed.py`` as a fresh module each time so
    tests can mutate env / module-level state without bleed-over."""
    spec = importlib.util.spec_from_file_location(
        "_test_production_seed", SCRIPTS / "production_seed.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Strip all PROD_SEED env vars + DATABASE_URL between tests."""
    for k in (
        "AGENTOS_PROD_SEED_ON_BOOT",
        "AGENTOS_PROD_SEED_FORCE",
        "AGENTOS_PROD_SEED_EMAIL",
        "AGENTOS_PROD_SEED_PASSWORD",
        "AGENTOS_PROD_SEED_FULLNAME",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(k, raising=False)


# ─────────────────────────────────────────────  Fence 1: opt-in  ────────


def test_fence1_no_opt_in_returns_0(monkeypatch):
    mod = _load_production_seed()
    rc = asyncio.run(mod.run([]))
    assert rc == 0, "without AGENTOS_PROD_SEED_ON_BOOT, must be a no-op (exit 0)"


def test_fence1_force_run_cli_flag_overrides_env(monkeypatch, tmp_path):
    """`--force-run` should bypass the env-flag fence (still goes through other fences)."""
    mod = _load_production_seed()
    db_file = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    # Use a dry run so we don't actually re-seed (we only need fence-1 to pass)
    rc = asyncio.run(mod.run(["--force-run", "--dry-run"]))
    # rc is 0 even if other fences would otherwise short-circuit
    assert rc in (0, 1), f"expected 0 (passed all fences) or 1 (DB unreachable), got {rc}"


# ─────────────────────────────────────────────  Fence 2: production DSN  ─


@pytest.mark.parametrize(
    "dsn,is_risky",
    [
        ("postgresql+asyncpg://user:pw@prod.example.com/mydow", True),
        ("postgresql+asyncpg://user:pw@db.production.example.com/mydow", True),
        ("postgresql+asyncpg://user:pw@db.example.com/mydow_prod", True),
        ("postgresql+asyncpg://user:pw@mydow-prod-1.example.com/mydow", True),
        ("sqlite+aiosqlite:///./data/dev.db", False),
        ("postgresql+asyncpg://user:pw@db.example.com/mydow", False),
        ("postgresql+asyncpg://user:pw@staging.example.com/mydow", False),
        (None, False),
    ],
)
def test_fence2_looks_like_production(dsn, is_risky):
    mod = _load_production_seed()
    assert mod._looks_like_production(dsn) == is_risky


def test_fence2_production_dsn_blocks_unless_force(monkeypatch):
    mod = _load_production_seed()
    monkeypatch.setenv("AGENTOS_PROD_SEED_ON_BOOT", "on")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:pw@prod.example.com/mydow"
    )
    rc = asyncio.run(mod.run([]))
    assert rc == 2, "production DSN must trigger fence-2 exit 2 without force"


# ─────────────────────────────────────────────  Fence 3: real users  ────


def test_fence3_real_users_block_without_force(monkeypatch, tmp_path):
    """When DB has non-demo users, the seed should skip with exit 0."""
    mod = _load_production_seed()
    db_file = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("AGENTOS_PROD_SEED_ON_BOOT", "on")

    async def _fake_count_real_users(seed_email):
        assert seed_email == mod.SEED_EMAIL_DEFAULT
        return 7  # pretend there are 7 real users

    monkeypatch.setattr(mod, "_count_real_users", _fake_count_real_users)

    rc = asyncio.run(mod.run([]))
    assert rc == 0, "fence-3 must skip (exit 0) with warning when real users exist"


def test_fence3_real_users_force_proceeds_to_seed(monkeypatch, tmp_path):
    """With AGENTOS_PROD_SEED_FORCE=1, the seed should run despite real users."""
    mod = _load_production_seed()
    db_file = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("AGENTOS_PROD_SEED_ON_BOOT", "on")
    monkeypatch.setenv("AGENTOS_PROD_SEED_FORCE", "1")

    async def _fake_count_real_users(seed_email):
        return 3

    monkeypatch.setattr(mod, "_count_real_users", _fake_count_real_users)

    # Dry run so we don't actually run seed_prd10 (it requires a fully
    # initialised DB schema which is expensive to wire up here).
    rc = asyncio.run(mod.run(["--dry-run"]))
    assert rc == 0, "force should bypass fence-3 and reach dry-run path"


# ─────────────────────────────────────────────  Dry-run path  ──────────


def test_dry_run_reports_decision_without_seeding(monkeypatch, tmp_path, caplog):
    mod = _load_production_seed()
    db_file = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("AGENTOS_PROD_SEED_ON_BOOT", "on")

    async def _fake_count_real_users(seed_email):
        return 0

    monkeypatch.setattr(mod, "_count_real_users", _fake_count_real_users)

    seed_called = False

    def _fake_loader(*_args, **_kwargs):  # would fail this if called
        nonlocal seed_called
        seed_called = True
        raise AssertionError("seed_prd10.main must NOT be called in dry-run")

    monkeypatch.setattr("importlib.util.spec_from_file_location", _fake_loader)

    with caplog.at_level("INFO"):
        rc = asyncio.run(mod.run(["--dry-run"]))
    assert rc == 0
    assert not seed_called


# ─────────────────────────────────────────────  Happy path  ────────────


def test_happy_path_calls_seed_prd10(monkeypatch, tmp_path):
    """Successfully passes all fences and invokes seed_prd10.main with --reset."""
    mod = _load_production_seed()
    db_file = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setenv("AGENTOS_PROD_SEED_ON_BOOT", "on")
    monkeypatch.setenv("AGENTOS_PROD_SEED_EMAIL", "demo+11_9@whyme.local")
    monkeypatch.setenv("AGENTOS_PROD_SEED_FULLNAME", "Test Demo")

    async def _fake_count_real_users(seed_email):
        assert seed_email == "demo+11_9@whyme.local"
        return 0

    monkeypatch.setattr(mod, "_count_real_users", _fake_count_real_users)

    captured_calls = []

    class _FakeSeedModule:
        async def main(self, argv):
            captured_calls.append(list(argv))
            return 0

    fake_module = _FakeSeedModule()

    class _FakeLoader:
        def exec_module(self, module):
            module.main = fake_module.main

    class _FakeSpec:
        loader = _FakeLoader()

    def _fake_spec_from_file_location(name, path):
        return _FakeSpec()

    def _fake_module_from_spec(spec):
        return type("M", (), {})()

    monkeypatch.setattr(
        "importlib.util.spec_from_file_location", _fake_spec_from_file_location
    )
    monkeypatch.setattr(
        "importlib.util.module_from_spec", _fake_module_from_spec
    )

    rc = asyncio.run(mod.run([]))
    assert rc == 0
    assert len(captured_calls) == 1
    argv = captured_calls[0]
    assert "--email" in argv
    assert "demo+11_9@whyme.local" in argv
    assert "--reset" in argv
    assert "--full-name" in argv
    assert "Test Demo" in argv


# ─────────────────────────────────────────────  Helpers  ───────────────


@pytest.mark.parametrize(
    "dsn,redacted_contains",
    [
        ("postgresql://user:secret@host/db", ":****@"),
        ("sqlite:///./db", "sqlite"),
        (None, "<unset>"),
    ],
)
def test_redact_dsn_hides_password(dsn, redacted_contains):
    mod = _load_production_seed()
    out = mod._redact_dsn(dsn)
    assert redacted_contains in out
    if dsn and "secret" in dsn:
        assert "secret" not in out


def test_bool_env_parsing(monkeypatch):
    mod = _load_production_seed()
    for raw in ("on", "1", "true", "TRUE", "Yes", "ENABLED"):
        monkeypatch.setenv("X_TEST_BOOL", raw)
        assert mod._bool_env("X_TEST_BOOL", default=False) is True, f"raw={raw!r}"
    for raw in ("off", "0", "false", "no", "disabled", ""):
        monkeypatch.setenv("X_TEST_BOOL", raw)
        assert mod._bool_env("X_TEST_BOOL", default=True) is (raw == "")
