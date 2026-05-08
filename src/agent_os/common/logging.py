"""Structured logging utilities for PRD10 §11.6 / §23.2.

This module exposes ``configure_logging()`` to set up the root logger with
either:

* ``text`` (default) — human-friendly format used by local development.
* ``json``           — one JSON object per log line, ready for log
  aggregators (Datadog, ELK, Loki). Custom keys whose names start with
  ``prd10_`` are emitted as top-level fields without that prefix so the
  aggregator sees ``request_id`` / ``status_code`` directly.

Pick the format with ``AGENTOS_LOG_FORMAT=json``. Anything else falls back
to text. ``AGENTOS_LOG_LEVEL`` overrides the root level (default INFO).

Designed to be **idempotent**: calling ``configure_logging()`` multiple
times only attaches one handler so test fixtures and the FastAPI startup
hook can both call it.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime, timezone
from typing import Any

_HANDLER_TAG = "_agentos_prd10_handler"


class JsonLogFormatter(logging.Formatter):
    """Format ``LogRecord``s as one JSON line per record.

    Custom keys passed via ``extra={"prd10_request_id": "..."}`` are
    flattened to top-level fields with the ``prd10_`` prefix removed.
    Standard fields (``ts``, ``level``, ``logger``, ``message``,
    ``module``, ``line``) are always present so downstream log
    aggregators have a stable schema.
    """

    _STANDARD = (
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    )

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        for key, value in record.__dict__.items():
            if key in self._STANDARD or key.startswith("_"):
                continue
            short_key = key[len("prd10_"):] if key.startswith("prd10_") else key
            payload[short_key] = _to_jsonable(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = record.stack_info

        return json.dumps(payload, ensure_ascii=False, default=str)


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    return str(value)


def _build_handler(format_choice: str) -> logging.Handler:
    handler = logging.StreamHandler(stream=sys.stdout)
    if format_choice.lower() == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
    setattr(handler, _HANDLER_TAG, True)
    return handler


def configure_logging(
    *,
    format_choice: str | None = None,
    level: str | None = None,
) -> None:
    """Idempotently install the PRD10 structured logging handler.

    Reads:

    * ``AGENTOS_LOG_FORMAT`` (or the explicit ``format_choice`` arg) →
      ``json`` enables structured output, anything else stays text.
    * ``AGENTOS_LOG_LEVEL``  (or ``level`` arg) → defaults to ``INFO``.

    Subsequent calls do not stack handlers; they only update the format
    and level so test fixtures can switch on JSON output safely.
    """

    fmt = (format_choice or os.getenv("AGENTOS_LOG_FORMAT") or "text").strip().lower()
    lvl_name = (level or os.getenv("AGENTOS_LOG_LEVEL") or "INFO").strip().upper()
    lvl = getattr(logging, lvl_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(lvl)

    existing = [h for h in root.handlers if getattr(h, _HANDLER_TAG, False)]
    if existing:
        for h in existing:
            root.removeHandler(h)

    handler = _build_handler(fmt)
    handler.setLevel(lvl)
    root.addHandler(handler)

    # Tame noisy loggers in production-style runs while keeping our own
    # access logger at INFO so the structured access lines flow through.
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "asyncio"):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if fmt == "json" else logging.INFO
        )
    logging.getLogger("agent_os.prd10.access").setLevel(logging.INFO)


__all__ = ["JsonLogFormatter", "configure_logging"]
