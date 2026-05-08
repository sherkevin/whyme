"""Production-safe wrapper around scripts/seed_prd10.py.

PRD10 §11.9 / todo-tasks.md §11.9 (Owner: my-mcp-20 @ 2026-05-06).

Designed to run as a one-shot service on container start (or in a CI/CD
deploy hook) so that the demo account + default Skills always exist on
every freshly provisioned environment **without** clobbering real user
data on subsequent runs.

Safety fences (in order):

1. **Env opt-in** — exits 0 (no-op) unless ``AGENTOS_PROD_SEED_ON_BOOT``
   is one of ``on/1/true/yes/enabled``. Default off so production deploys
   stay deterministic.

2. **DATABASE_URL sanity** — refuses to run when ``DATABASE_URL`` looks
   like a "real" production DSN (host contains ``prod``/``production``)
   unless ``AGENTOS_PROD_SEED_FORCE=1`` is also set. Belt-and-braces
   against a stray cron firing into the wrong cluster.

3. **Real-user fence** — connects to the DB, counts ``users`` rows that
   are *not* the demo seed account. If any are present, the script logs
   a warning + exits 0 unless ``AGENTOS_PROD_SEED_FORCE=1``. Protects
   pilot deployments where the team already onboarded customers but the
   deploy pipeline still has the seed step enabled.

4. **Demo-only re-seed** — when allowed to run, calls
   ``scripts.seed_prd10.main(['--reset', '--email', SEED_EMAIL, ...])``
   which only wipes rows tagged ``[seed]`` for the demo user. Other
   users are untouched.

CLI usage::

    # No-op (default)
    python scripts/production_seed.py

    # Force a re-seed locally
    AGENTOS_PROD_SEED_ON_BOOT=on python scripts/production_seed.py

    # CI/CD: force even with real users (stages/canary)
    AGENTOS_PROD_SEED_ON_BOOT=on AGENTOS_PROD_SEED_FORCE=1 \
        python scripts/production_seed.py

    # Health check only — print decisions, don't write
    python scripts/production_seed.py --dry-run

Exit codes:

    0  Successfully ran (or correctly skipped per the fences above)
    1  Generic error (DB unreachable, seed script failed, etc.)
    2  Refused: tried to run on real data without --force / env override
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ─────────────────────────────────────────────  Defaults / env reader  ──

# Keep aligned with seed_prd10._parse_args defaults; override via env in
# production deploys (e.g. AGENTOS_PROD_SEED_EMAIL=demo@mydow.example).
SEED_EMAIL_DEFAULT = "demo@whyme.local"
SEED_PASSWORD_DEFAULT = "demo-password-123"
SEED_FULLNAME_DEFAULT = "Demo User"

_ENV_FLAG_TRUE = {"1", "on", "true", "yes", "enabled"}


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in _ENV_FLAG_TRUE


def _str_env(name: str, default: str) -> str:
    raw = os.getenv(name, "").strip()
    return raw or default


# ─────────────────────────────────────────────  Logging  ───────────────

_LOG = logging.getLogger("agent_os.prd10.production_seed")


def _configure_logging(*, verbose: bool) -> None:
    """Configure logging without flooding the console with SQLAlchemy noise.

    Sets WARNING as the root level so transitive libraries (sqlalchemy /
    aiosqlite / asyncio) stay quiet; only ``agent_os.prd10.production_seed``
    drops to INFO (or DEBUG with ``--verbose``). This keeps the ops log
    actionable when CI / docker logs are being reviewed.
    """

    level = logging.DEBUG if verbose else logging.INFO

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s production_seed: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    _LOG.setLevel(level)


# ─────────────────────────────────────────────  Safety fences  ─────────


def _looks_like_production(database_url: str | None) -> bool:
    """Return True when the DSN hostname or database name looks production-ish.

    Conservative URL-token scans alone miss common hosts like
    ``prod.example.com`` (there is no ``://prod`` substring). We therefore
    parse hostname + optional DB path and apply:

    * Host labels equal to / containing ``production``, or starting / ending
      with ``prod`` (but not ``product…`` — handled via stem checks).
    * Database segments ending in ``_prod`` / ``_production`` etc.

    SQLite URLs return False — production deployments should use networked DBs;
    local SQLite is never gated by this fence.
    """

    if not database_url:
        return False

    lowered = database_url.strip().lower()
    if lowered.startswith("sqlite"):
        return False

    # ``dialect+driver://…`` → keep everything after the first ``://``
    if "://" not in lowered:
        blob = lowered
    else:
        blob = lowered.split("://", 1)[1]

    auth_tail = blob.split("@", 1)[-1] if "@" in blob else blob

    if "/" in auth_tail:
        host_port, db_part = auth_tail.split("/", 1)
        db_part = db_part.split("?", 1)[0]
    else:
        host_port, db_part = auth_tail, ""

    hostname = host_port.split(":")[0].strip()

    if hostname:
        labels = [p for p in hostname.split(".") if p]
        risky_exact = {"prod", "production", "prd"}
        for lbl in labels:
            if lbl in risky_exact:
                return True
            if "production" in lbl:
                return True
            if lbl.startswith("prod-") or lbl.endswith("-prod"):
                return True
            # Tier markers like ``mydow-prod-1``, ``api-prod-east`` (not ``-product-``).
            if "-prod-" in lbl or "-production-" in lbl:
                return True
            # ``product``, ``production-line``, etc. — avoid substring-only FP
            stem = lbl.split("-")[0]
            if stem == "prod" and lbl != "product":
                return True

    if db_part:
        d = db_part.lower()
        if d in {"prod", "production"}:
            return True
        prod_suffixes = ("_prod", "_production", "-prod", "-production")
        prod_prefixes = ("prod_", "production_")
        if any(d.endswith(s) for s in prod_suffixes):
            return True
        if any(d.startswith(p) for p in prod_prefixes):
            return True

    return False


async def _count_real_users(seed_email: str) -> int:
    """Return the number of users that are NOT the demo seed account.

    Connects via the same engine the app uses so DATABASE_URL and pool
    settings are honoured. Errors propagate up so callers can decide.
    """

    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from agent_os.auth.models import User
    from agent_os.db.base import get_engine, init_db

    engine = get_engine()
    await init_db()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        # Total users
        total = (await session.execute(select(func.count(User.id)))).scalar_one()
        # Demo account (may not exist yet on first run)
        demo = (
            await session.execute(
                select(func.count(User.id)).where(User.email == seed_email)
            )
        ).scalar_one()
    real = max(0, int(total) - int(demo))
    return real


# ─────────────────────────────────────────────  Main flow  ─────────────


async def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _configure_logging(verbose=args.verbose)

    on_boot = _bool_env("AGENTOS_PROD_SEED_ON_BOOT", default=False) or args.force_run
    force = _bool_env("AGENTOS_PROD_SEED_FORCE", default=False) or args.force

    seed_email = _str_env("AGENTOS_PROD_SEED_EMAIL", SEED_EMAIL_DEFAULT)
    seed_password = _str_env("AGENTOS_PROD_SEED_PASSWORD", SEED_PASSWORD_DEFAULT)
    seed_fullname = _str_env("AGENTOS_PROD_SEED_FULLNAME", SEED_FULLNAME_DEFAULT)
    database_url = os.getenv("DATABASE_URL")

    _LOG.info(
        "starting (on_boot=%s force=%s dry_run=%s seed_email=%s db=%s)",
        on_boot,
        force,
        args.dry_run,
        seed_email,
        _redact_dsn(database_url),
    )

    # ── Fence 1: opt-in ────────────────────────────────────────────────
    if not on_boot:
        _LOG.info(
            "AGENTOS_PROD_SEED_ON_BOOT not set — skipping (no-op). "
            "Pass --force-run or set AGENTOS_PROD_SEED_ON_BOOT=on to enable."
        )
        return 0

    # ── Fence 2: production DSN ────────────────────────────────────────
    if _looks_like_production(database_url) and not force:
        _LOG.error(
            "DATABASE_URL looks like production (%s). Refusing to seed "
            "without AGENTOS_PROD_SEED_FORCE=1 / --force.",
            _redact_dsn(database_url),
        )
        return 2

    # ── Fence 3: real-user count ───────────────────────────────────────
    try:
        real_users = await _count_real_users(seed_email)
    except Exception as exc:  # noqa: BLE001 - any DB failure is fatal here
        _LOG.error("could not count users — DB unreachable? error=%s", exc)
        return 1

    if real_users > 0 and not force:
        _LOG.warning(
            "found %d real (non-demo) users in DB — skipping seed to "
            "preserve existing data. Set AGENTOS_PROD_SEED_FORCE=1 / "
            "--force to override.",
            real_users,
        )
        return 0

    if args.dry_run:
        _LOG.info(
            "DRY RUN — would call seed_prd10.main with email=%s, full_name=%s, "
            "reset=True (real_users=%d)",
            seed_email,
            seed_fullname,
            real_users,
        )
        return 0

    # ── Fence 4: demo-only re-seed ─────────────────────────────────────
    _LOG.info(
        "calling seed_prd10.main (real_users=%d, will --reset demo rows tagged [seed])",
        real_users,
    )
    try:
        # ``scripts/`` is not a Python package (no __init__.py) so we load
        # ``seed_prd10`` by file path. This also lets the script run from
        # any CWD as long as the sibling file is on disk.
        import importlib.util

        seed_path = Path(__file__).resolve().parent / "seed_prd10.py"
        spec = importlib.util.spec_from_file_location(
            "_mydow_seed_prd10", seed_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load seed_prd10 from {seed_path}")
        seed_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_module)

        rc = await seed_module.main(
            [
                "--email",
                seed_email,
                "--password",
                seed_password,
                "--full-name",
                seed_fullname,
                "--reset",
            ]
        )
        if rc != 0:
            _LOG.error("seed_prd10 returned non-zero exit code: %s", rc)
            return rc or 1
    except SystemExit as exc:
        _LOG.error("seed_prd10 exited unexpectedly: %s", exc)
        return int(exc.code or 1)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("seed_prd10 crashed: %s", exc)
        return 1

    _LOG.info("production seed complete — demo account %s ready", seed_email)
    return 0


def _redact_dsn(dsn: str | None) -> str:
    """Redact passwords from a DSN for logging."""

    if not dsn:
        return "<unset>"
    # postgresql+asyncpg://user:pass@host:port/db
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(dsn)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}", ":****", 1)
            parsed = parsed._replace(netloc=netloc)
        return urlunparse(parsed)
    except Exception:
        return "<dsn>"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force-run",
        action="store_true",
        help="Bypass AGENTOS_PROD_SEED_ON_BOOT env check (alias for --opt-in)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Override production-DSN and real-user fences. "
            "Equivalent to AGENTOS_PROD_SEED_FORCE=1."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute decisions but do not call the seeder.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose DEBUG logging.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
