"""PRD10 §11.5 / §29 — error monitoring via Sentry.

Wires the official ``sentry-sdk`` to the FastAPI app so production errors
land in a real dashboard. Design highlights:

* **Default OFF** — when ``SENTRY_DSN`` is unset/empty, :func:`init_sentry`
  is a no-op. Local dev, CI, the test client, and demos all see zero
  network calls and zero behavior change.
* **DSN-driven init** — the only required setting is ``SENTRY_DSN``. The
  rest (``SENTRY_ENVIRONMENT``, ``SENTRY_RELEASE``, sample rates) have
  sensible production defaults but are configurable.
* **PII scrubbing** — the ``before_send`` hook strips obvious secrets
  (Authorization / Cookie headers, password / token fields) before
  events leave the process. PRD10 user-content (cards, messages) is
  considered low risk to forward but the scrub list is conservative.
* **Quiet integrations** — drops noisy `/health` and `/ready` transactions
  so the `transactions/min` quota isn't burned on health checks.
* **Idempotent** — guards against double-init when called twice (e.g.
  module-level + ``startup_event`` belt-and-suspenders).

Public surface:

* :func:`init_sentry` — call once at app startup
* :func:`is_sentry_enabled` — module-level check
* :func:`capture_message` / :func:`capture_exception` — convenience
  wrappers that no-op when Sentry is off
"""

from __future__ import annotations

import logging
import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

_logger = logging.getLogger("agent_os.prd10.sentry")


# Module-level state, set by :func:`init_sentry`. Read via
# :func:`is_sentry_enabled` so callers don't reach into the SDK directly.
_state: dict[str, Any] = {
    "initialized": False,
    "enabled": False,
    "dsn_present": False,
    "environment": None,
    "release": None,
}


# ---------------------------------------------------------------------------
# Helpers — env parsing
# ---------------------------------------------------------------------------


def _read_dsn() -> str | None:
    raw = os.getenv("SENTRY_DSN", "").strip()
    return raw or None


def _read_environment() -> str:
    return os.getenv("SENTRY_ENVIRONMENT", "").strip() or os.getenv(
        "ENVIRONMENT", "development"
    ).strip() or "development"


def _read_release() -> str | None:
    raw = os.getenv("SENTRY_RELEASE", "").strip()
    return raw or None


def _read_sample_rate(env_name: str, default: float) -> float:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        _logger.warning(
            "sentry_invalid_float_env",
            extra={"prd10_env": env_name, "prd10_value": raw, "prd10_default": default},
        )
        return default
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# PII / secrets scrubbing
# ---------------------------------------------------------------------------


_SECRET_HEADER_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-mydow-token",
        "x-auth-token",
        "x-csrf-token",
    }
)

_SECRET_BODY_KEYS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
        "private_key",
        "client_secret",
    }
)

_REDACTED = "[Filtered]"


def _scrub_mapping(payload: Any, secret_keys: frozenset[str]) -> Any:
    """Recursively replace values for keys in ``secret_keys``.

    The scrub keeps the original key + value type (string vs list) so the
    sanitized event still reflects the real shape; only the value is
    replaced with a constant placeholder.
    """

    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(key, str) and key.lower() in secret_keys:
                cleaned[key] = _REDACTED
            else:
                cleaned[key] = _scrub_mapping(value, secret_keys)
        return cleaned

    if isinstance(payload, list):
        return [_scrub_mapping(item, secret_keys) for item in payload]

    return payload


def _scrub_event(event: dict[str, Any]) -> dict[str, Any]:
    """Apply the secret-key filter across the parts of the event most
    likely to carry credentials (request headers, request data, breadcrumbs,
    extra payloads)."""

    request = event.get("request") if isinstance(event, dict) else None
    if isinstance(request, dict):
        if "headers" in request and isinstance(request["headers"], dict):
            request["headers"] = _scrub_mapping(request["headers"], _SECRET_HEADER_KEYS)
        for key in ("cookies", "data", "query_string"):
            if key in request:
                request[key] = _scrub_mapping(request[key], _SECRET_BODY_KEYS)

    extras = event.get("extra")
    if isinstance(extras, dict):
        event["extra"] = _scrub_mapping(extras, _SECRET_BODY_KEYS)

    contexts = event.get("contexts")
    if isinstance(contexts, dict):
        event["contexts"] = _scrub_mapping(contexts, _SECRET_BODY_KEYS)

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict) and isinstance(breadcrumbs.get("values"), list):
        breadcrumbs["values"] = _scrub_mapping(
            breadcrumbs["values"], _SECRET_BODY_KEYS
        )

    return event


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """Sentry ``before_send`` hook — runs synchronously before HTTPS POST."""

    try:
        return _scrub_event(event)
    except Exception:  # noqa: BLE001 - never let scrub break delivery
        # If scrubbing crashed, prefer not sending the event over leaking PII.
        return None


_DROPPED_TRANSACTION_PATHS = (
    "/health",
    "/ready",
    "/metrics",
    "/favicon.ico",
)


def _before_send_transaction(
    event: dict[str, Any], _hint: dict[str, Any]
) -> dict[str, Any] | None:
    """Drop noisy infrastructure transactions to keep the quota for real traffic."""

    transaction = event.get("transaction") if isinstance(event, dict) else None
    if isinstance(transaction, str):
        for prefix in _DROPPED_TRANSACTION_PATHS:
            if transaction.startswith(prefix):
                return None
    return event


# ---------------------------------------------------------------------------
# Public init
# ---------------------------------------------------------------------------


def init_sentry(*, force: bool = False) -> bool:
    """Initialize Sentry from environment variables.

    Args:
        force: When ``True``, re-initialize even if a previous call already
            ran. Useful for tests that mutate env between cases.

    Returns:
        ``True`` if Sentry was activated this call, ``False`` if it stayed
        inactive (no DSN or already initialized).

    Environment:
        ``SENTRY_DSN`` — required to enable. Empty/unset = no-op.
        ``SENTRY_ENVIRONMENT`` — falls back to ``ENVIRONMENT`` env var,
            then to ``development``.
        ``SENTRY_RELEASE`` — optional; recommended for Sentry to associate
            errors with deploys (e.g. git SHA or app version).
        ``SENTRY_TRACES_SAMPLE_RATE`` — default ``0.1`` (10% of transactions
            sampled). Set to ``0.0`` to disable tracing.
        ``SENTRY_SAMPLE_RATE`` — default ``1.0`` (every error is captured).
        ``SENTRY_SEND_DEFAULT_PII`` — default ``false``; when ``on/1/true``
            allows Sentry to associate user identity with events.
    """

    if _state["initialized"] and not force:
        return _state["enabled"]

    dsn = _read_dsn()
    _state["dsn_present"] = bool(dsn)

    if not dsn:
        _state["initialized"] = True
        _state["enabled"] = False
        _state["environment"] = _read_environment()
        _state["release"] = _read_release()
        _logger.debug("sentry_skipped_no_dsn")
        return False

    environment = _read_environment()
    release = _read_release()
    traces_sample_rate = _read_sample_rate("SENTRY_TRACES_SAMPLE_RATE", 0.1)
    sample_rate = _read_sample_rate("SENTRY_SAMPLE_RATE", 1.0)
    send_pii = os.getenv("SENTRY_SEND_DEFAULT_PII", "").strip().lower() in (
        "1",
        "on",
        "true",
        "yes",
        "enabled",
    )

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            sample_rate=sample_rate,
            traces_sample_rate=traces_sample_rate,
            send_default_pii=send_pii,
            attach_stacktrace=True,
            max_breadcrumbs=50,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,        # capture INFO+ as breadcrumbs
                    event_level=logging.ERROR, # capture ERROR+ as events
                ),
            ],
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
        )
    except Exception as exc:  # noqa: BLE001 - keep startup resilient
        _logger.warning(
            "sentry_init_failed",
            extra={"prd10_error": exc.__class__.__name__, "prd10_message": str(exc)},
        )
        _state["initialized"] = True
        _state["enabled"] = False
        _state["environment"] = environment
        _state["release"] = release
        return False

    _state["initialized"] = True
    _state["enabled"] = True
    _state["environment"] = environment
    _state["release"] = release
    _logger.info(
        "sentry_initialized",
        extra={
            "prd10_environment": environment,
            "prd10_release": release or "-",
            "prd10_traces_sample_rate": traces_sample_rate,
            "prd10_sample_rate": sample_rate,
        },
    )
    return True


def is_sentry_enabled() -> bool:
    """Return whether Sentry is actively shipping events."""

    return bool(_state.get("enabled"))


def get_sentry_state() -> dict[str, Any]:
    """Return a copy of the module state. Useful for tests / `/ready` payload."""

    return dict(_state)


def reset_sentry_state_for_test() -> None:
    """Clear module state. Test-only helper, never called from production."""

    _state.update(
        {
            "initialized": False,
            "enabled": False,
            "dsn_present": False,
            "environment": None,
            "release": None,
        }
    )


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


def capture_message(message: str, level: str = "info", **extra: Any) -> None:
    """Send an arbitrary message to Sentry. No-op when disabled.

    Uses sentry-sdk 2.x's ``new_scope`` context manager so per-call
    extras (``request_id`` etc.) don't leak into unrelated subsequent
    captures on the same task.
    """

    if not is_sentry_enabled():
        return
    try:
        with sentry_sdk.new_scope() as scope:
            for key, value in extra.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_message(message, level=level)
    except Exception:  # noqa: BLE001 - never propagate monitoring failures
        _logger.exception("sentry_capture_message_failed")


def capture_exception(exc: BaseException | None = None, **extra: Any) -> None:
    """Send a caught exception to Sentry. No-op when disabled.

    Uses sentry-sdk 2.x's ``new_scope`` context manager so per-call
    extras (``request_id`` etc.) don't leak into unrelated subsequent
    captures on the same task.
    """

    if not is_sentry_enabled():
        return
    try:
        with sentry_sdk.new_scope() as scope:
            for key, value in extra.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001
        _logger.exception("sentry_capture_exception_failed")
