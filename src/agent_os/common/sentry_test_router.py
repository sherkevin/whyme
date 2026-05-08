"""PRD10 §11.5b — debug-only Sentry test endpoint.

Exposes a single endpoint operators can hit to verify that Sentry is
correctly wired up in a fresh deployment. The endpoint is **opt-in**:

* Mounted only when ``AGENTOS_SENTRY_TEST=on`` (or `1` / `true` / `yes`).
* Mounted only when Sentry is actually enabled (i.e. ``SENTRY_DSN`` is set).

The endpoint deliberately raises so a ``ZeroDivisionError`` event lands
in the configured Sentry project. The response is an envelope error so
clients still get a clean 500 they can check against the Sentry UI.

Why this matters: many deployments configure ``SENTRY_DSN`` correctly
but never see events because the SDK silently fails (firewall / wrong
project key / sample rate=0 / etc.). Hitting ``POST /api/v1/__sentry_test__``
once after a deploy is the fastest way to confirm the round trip.

Operationally:

* Production deploys SHOULD set ``AGENTOS_SENTRY_TEST=on`` once during
  rollout, hit the endpoint, confirm in the Sentry UI, then unset.
* The endpoint is gated behind a guard module (``app.py`` checks the env
  + ``is_sentry_enabled`` before mounting), so simply leaving it on does
  not expose anything sensitive — it only triggers a synthetic error.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Request

from agent_os.common.errors import ApiError, ApiErrorCode
from agent_os.common.response import error_response_from
from agent_os.common.sentry_setup import (
    capture_exception,
    capture_message,
    is_sentry_enabled,
)

router = APIRouter(prefix="/api/v1", tags=["Internal"])


def is_sentry_test_endpoint_enabled() -> bool:
    """Return ``True`` if operators have opted in to the synthetic endpoint.

    Both conditions must hold:

    * ``AGENTOS_SENTRY_TEST`` env truthy (``1`` / ``on`` / ``true`` / ``yes`` / ``enabled``).
    * Sentry itself is enabled (``SENTRY_DSN`` set, init succeeded).

    The OR-of-AND structure prevents a leaked test endpoint from doing
    anything observable when Sentry is off.
    """

    raw = os.getenv("AGENTOS_SENTRY_TEST", "").strip().lower()
    if raw not in ("1", "on", "true", "yes", "enabled"):
        return False
    return is_sentry_enabled()


@router.post(
    "/__sentry_test__",
    summary="Trigger a synthetic Sentry event (operators only)",
    description=(
        "Raises a ZeroDivisionError so operators can confirm Sentry receives"
        " events from this deploy. Mounted only when AGENTOS_SENTRY_TEST=on"
        " AND SENTRY_DSN is set."
    ),
    status_code=500,
    include_in_schema=False,
)
async def trigger_sentry_test_event(request: Request) -> dict:
    """Capture a message + raise a synthetic error.

    The route does both:

    * ``capture_message`` for an info-level breadcrumb-style event.
    * ``capture_exception`` after raising, so the exception event is
      definitely associated with this request.

    The handler returns a PRD10 envelope so the test client never sees
    a 422 / unstructured error.
    """

    capture_message(
        "sentry_smoke_test_message",
        level="info",
        request_id=getattr(request.state, "request_id", "-"),
    )

    err = ApiError(
        ApiErrorCode.INTERNAL_ERROR,
        "Synthetic error triggered by /__sentry_test__ — Sentry should now have an event.",
        details={"synthetic": True, "endpoint": "/api/v1/__sentry_test__"},
    )
    try:
        # Force an actual Python exception so Sentry stack frames are
        # populated; then translate to PRD10 envelope.
        _ = 1 / 0
    except ZeroDivisionError as exc:
        capture_exception(
            exc,
            request_id=getattr(request.state, "request_id", "-"),
            synthetic=True,
        )

    body = error_response_from(err, request=request)
    body.setdefault("error", {}).setdefault("details", {})["synthetic"] = True
    return body
