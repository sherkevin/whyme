"""Static + behavioural contract checks for scripts/production_seed.py.

PRD10 §11.9 / todo-tasks.md §11.9 (Owner: my-mcp-20 @ 2026-05-06).

These tests guard the safety-critical behaviour of the production seed
wrapper without touching the network: 4 fences (env opt-in / production
DSN / real-user count / demo-only re-seed) + the docker-compose ``seed``
profile + the docs file.

We avoid spinning up a full DB in unit tests; the real-run path is
already exercised by ``scripts/seed_prd10.py`` integration tests and by
the manual smoke run captured in the §11.9 task evidence.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "production_seed.py"
COMPOSE_PATH = REPO_ROOT / "docker-compose.prd10.yml"
DOCS_PATH = REPO_ROOT / "docs" / "11-deployment" / "production-seed.md"
ENV_VARS_DOC = REPO_ROOT / "docs" / "11-deployment" / "env-vars.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "_test_production_seed", SCRIPT_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# File presence
# ---------------------------------------------------------------------------


def test_production_seed_files_exist() -> None:
    """Script + docs + .env.example block all ship with the repo."""
    assert SCRIPT_PATH.is_file(), "scripts/production_seed.py missing"
    assert DOCS_PATH.is_file(), "docs/11-deployment/production-seed.md missing"
    body = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "AGENTOS_PROD_SEED_ON_BOOT" in body
    assert "AGENTOS_PROD_SEED_FORCE" in body


def test_env_vars_handbook_mentions_prod_seed() -> None:
    """env-vars.md stays in sync with §11.9 (todo-tasks registry)."""
    body = ENV_VARS_DOC.read_text(encoding="utf-8")
    for frag in (
        "AGENTOS_PROD_SEED_ON_BOOT",
        "AGENTOS_PROD_SEED_FORCE",
        "AGENTOS_PROD_SEED_EMAIL",
        "production-seed.md",
        "§11.9",
    ):
        assert frag in body, f"env-vars.md missing {frag!r}"


# ---------------------------------------------------------------------------
# Safety fences (unit-level)
# ---------------------------------------------------------------------------


def test_bool_env_recognises_truthy_strings() -> None:
    mod = _load_module()
    truthy = {"1", "on", "true", "yes", "enabled", "TRUE", "On", "Yes"}
    falsy = {"", "0", "off", "false", "no", "disabled", "maybe", "  "}
    import os as _os

    for v in truthy:
        _os.environ["TEST_FLAG"] = v
        assert mod._bool_env("TEST_FLAG") is True, f"truthy {v!r} not recognised"
    for v in falsy:
        _os.environ["TEST_FLAG"] = v
        assert mod._bool_env("TEST_FLAG") is False, f"falsy {v!r} treated truthy"
    _os.environ.pop("TEST_FLAG", None)


@pytest.mark.parametrize(
    "dsn,expected",
    [
        # Production-looking DSNs → True (refuse without --force)
        ("postgresql+asyncpg://u:p@prod-db.example.com:5432/app", True),
        ("postgresql://u:p@db-production.internal:5432/app", True),
        ("postgresql+asyncpg://u:p@prod.cluster.local/app_prod_main", True),
        # Safe-looking DSNs → False (allowed by default)
        ("postgresql+asyncpg://u:p@localhost:5432/agentos_db", False),
        ("postgresql+asyncpg://u:p@postgres:5432/agentos_db", False),
        ("postgresql://u:p@staging-db.example.com/agentos_staging", False),
        ("sqlite+aiosqlite:///./test.db", False),
        ("", False),
        (None, False),
    ],
)
def test_looks_like_production_classification(dsn: str | None, expected: bool) -> None:
    mod = _load_module()
    assert mod._looks_like_production(dsn) is expected, (
        f"DSN {dsn!r} classified wrong"
    )


def test_redact_dsn_strips_password() -> None:
    mod = _load_module()
    result = mod._redact_dsn(
        "postgresql+asyncpg://agentos:supersecret@postgres:5432/agentos_db"
    )
    assert "supersecret" not in result, "password leaked into log"
    assert "****" in result, "expected redaction marker"
    assert mod._redact_dsn("") == "<unset>"
    assert mod._redact_dsn(None) == "<unset>"


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


def test_parse_args_defaults() -> None:
    mod = _load_module()
    ns = mod._parse_args([])
    assert ns.force_run is False
    assert ns.force is False
    assert ns.dry_run is False
    assert ns.verbose is False


def test_parse_args_all_flags() -> None:
    mod = _load_module()
    ns = mod._parse_args(["--force-run", "--force", "--dry-run", "-v"])
    assert ns.force_run is True
    assert ns.force is True
    assert ns.dry_run is True
    assert ns.verbose is True


# ---------------------------------------------------------------------------
# docker-compose seed profile
# ---------------------------------------------------------------------------


def test_compose_has_seed_profile() -> None:
    """`docker compose --profile seed` must expose a one-shot seed service."""
    spec = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    seed = spec["services"].get("seed")
    assert seed is not None, "compose missing seed service"
    assert "seed" in (seed.get("profiles") or [])
    assert seed.get("restart") == "no", "seed must not auto-restart"
    # depends_on postgres healthy
    deps = seed.get("depends_on") or {}
    assert "postgres" in deps
    pg = deps["postgres"]
    if isinstance(pg, dict):
        assert pg.get("condition") == "service_healthy"
    # env wires AGENTOS_PROD_SEED_*
    env = seed.get("environment") or {}
    env_text = " ".join(f"{k}={v}" for k, v in env.items())
    assert "AGENTOS_PROD_SEED_ON_BOOT" in env_text
    assert "DATABASE_URL" in env_text
    # command runs the wrapper script
    cmd = seed.get("command") or []
    cmd_text = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    assert "production_seed.py" in cmd_text


# ---------------------------------------------------------------------------
# Documentation contract
# ---------------------------------------------------------------------------


def test_docs_cover_4_fences_and_4_scenarios() -> None:
    """The docs page must describe the 4 fences and 4 scenarios so any
    operator reading it can understand the behaviour."""
    body = DOCS_PATH.read_text(encoding="utf-8")
    # 4 fences
    for fragment in (
        "AGENTOS_PROD_SEED_ON_BOOT",
        "AGENTOS_PROD_SEED_FORCE",
        "DSN",
        "real",
        "demo-only",
    ):
        assert fragment in body, f"docs missing fence keyword: {fragment!r}"
    # 4 scenarios
    for fragment in (
        "首次部署",
        "升级",
        "Staging",
        "干跑",
        "dry-run",
    ):
        assert fragment in body, f"docs missing scenario: {fragment!r}"
    # Self-check section
    assert "上线前自检" in body
