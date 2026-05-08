"""ASGI middleware: request-id tagging, structured PRD10 access log,
and PRD10 §29 token-bucket rate limiting.

These three middlewares are designed to be stacked on FastAPI in the
following call order (outermost → innermost):

    RequestIdMiddleware  →  RateLimitMiddleware  →  Prd10AccessLogMiddleware  →  app

Starlette runs ``add_middleware`` in reverse insertion order, so callers
should add them innermost-first (see ``server/app.py``):

    app.add_middleware(Prd10AccessLogMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from agent_os.common.errors import ApiErrorCode
from agent_os.common.metrics import get_default_metrics, is_metrics_enabled
from agent_os.common.rate_limit import (
    DEFAULT_POLICIES,
    InMemoryRateLimitStore,
    RateLimitPolicy,
    derive_key,
    get_default_store,
    is_rate_limit_enabled,
    select_policy,
)
from agent_os.common.response import REQUEST_ID_HEADER, REQUEST_ID_STATE_KEY

logger = logging.getLogger("agent_os.prd10.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a request id reachable via `request.state`.

    - Reads inbound `X-Request-ID` if present, otherwise generates `req_<hex12>`.
    - Stores it as `request.state.request_id`.
    - Echoes it back as the `X-Request-ID` response header.
    - When Sentry is enabled (PRD10 §11.5), tags the active Sentry scope
      with ``request_id`` + request path/method so any error captured for
      this request shows up correlated with our logs.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER)
        if not rid:
            rid = f"req_{uuid.uuid4().hex[:12]}"

        try:
            setattr(request.state, REQUEST_ID_STATE_KEY, rid)
        except Exception:
            pass

        # PRD10 §11.5b: bind request_id to the active Sentry isolation
        # scope so captured exceptions / breadcrumbs carry the same
        # correlation id we already log via ``Prd10AccessLogMiddleware``.
        # The import is local so non-Sentry deployments (or test runs
        # without ``sentry-sdk`` installed) do not pay any per-request
        # cost beyond the conditional check.
        #
        # We use sentry-sdk 2.x's module-level helpers
        # (``set_tag`` / ``set_context``) which write to the current
        # isolation scope and are recommended over the deprecated
        # ``configure_scope`` context manager.
        try:
            from agent_os.common.sentry_setup import is_sentry_enabled

            if is_sentry_enabled():
                import sentry_sdk

                sentry_sdk.set_tag("request_id", rid)
                sentry_sdk.set_tag("http.method", request.method or "GET")
                sentry_sdk.set_context(
                    "request_meta",
                    {
                        "request_id": rid,
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
        except Exception:
            # Monitoring failures must never break the request path.
            pass

        response: Response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


# Path prefixes whose accesses should be emitted to the structured PRD10
# access logger. Kept here (rather than in app.py) so other entrypoints
# that mount the same middleware get the same observability surface.
_PRD10_ACCESS_PREFIXES: tuple[str, ...] = (
    "/api/v1/capture",
    "/api/v1/uploads",
    "/api/v1/kb",
    "/api/v1/jobs",
    "/api/v1/notifications",
    "/api/v1/feed",
    "/api/v1/cards",
    "/api/v1/today",
    "/api/v1/search",
    "/api/v1/ai",
    "/api/v1/skills",
    "/api/v1/garden",
)


class Prd10AccessLogMiddleware(BaseHTTPMiddleware):
    """Lightweight access logger for PRD10 endpoints.

    Emits a single structured log line per matching request with:

    * ``request_id``  — same id stamped by ``RequestIdMiddleware``
    * ``method`` / ``path``
    * ``status_code``
    * ``duration_ms``
    * ``client_host``

    Non-PRD10 paths bypass the logger to keep noise low while the legacy
    surface is still in place. Failures are logged at ``WARNING`` so they
    surface in default operator dashboards without flipping log levels.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if not path.startswith(_PRD10_ACCESS_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms_float = (time.perf_counter() - start) * 1000
            duration_ms = int(duration_ms_float)
            rid = getattr(request.state, REQUEST_ID_STATE_KEY, None) or "-"
            client_host = request.client.host if request.client else "-"
            level = (
                logging.WARNING if status_code >= 500
                else logging.INFO
            )
            logger.log(
                level,
                "prd10_access",
                extra={
                    "prd10_request_id": rid,
                    "prd10_method": request.method,
                    "prd10_path": path,
                    "prd10_status_code": status_code,
                    "prd10_duration_ms": duration_ms,
                    "prd10_client_host": client_host,
                },
            )

            # PRD10 §12.1 — feed the same observation into the metrics
            # registry so /metrics + /api/v1/__metrics__/json can answer
            # P95-style questions without a separate middleware pass.
            if is_metrics_enabled():
                try:
                    await get_default_metrics().record_request(
                        method=request.method or "GET",
                        path=path,
                        status=status_code,
                        duration_ms=duration_ms_float,
                    )
                except Exception:
                    # Metrics must never break the request path.
                    pass


class RateLimitMiddleware(BaseHTTPMiddleware):
    """PRD10 §29 token-bucket rate limiter.

    Default OFF. Enable by setting ``AGENTOS_RATE_LIMIT=on`` in the
    environment (any of `1` / `on` / `true` / `yes` / `enabled` works).
    Production deployments should opt in once Redis is wired; the
    in-memory store provided here is single-process only.

    On 429 the response body is the canonical PRD10 error envelope
    ``{success:false, error:{code:"RATE_LIMITED", ...}}`` with
    ``Retry-After`` plus ``X-RateLimit-*`` headers so SDK consumers can
    back off uniformly.
    """

    def __init__(
        self,
        app,
        *,
        policies: tuple[RateLimitPolicy, ...] | None = None,
        store: InMemoryRateLimitStore | None = None,
        enabled: bool | None = None,
    ) -> None:
        super().__init__(app)
        self._policies: tuple[RateLimitPolicy, ...] = (
            tuple(policies) if policies else DEFAULT_POLICIES
        )
        self._store = store or get_default_store()
        self._enabled = enabled

    def is_active(self) -> bool:
        """Return ``True`` when this middleware should actively enforce."""

        if self._enabled is None:
            return is_rate_limit_enabled()
        return bool(self._enabled)

    async def dispatch(self, request: Request, call_next):
        if not self.is_active():
            return await call_next(request)

        path = request.url.path or ""
        method = request.method or "GET"

        policy = select_policy(path, method, policies=self._policies)
        if policy is None:
            return await call_next(request)

        key = derive_key(request, policy)
        allowed, remaining, retry_after = await self._store.consume(
            key,
            policy.capacity,
            policy.refill_per_second,
        )

        if allowed:
            response = await call_next(request)
            try:
                response.headers["X-RateLimit-Policy"] = policy.name
                response.headers["X-RateLimit-Limit"] = str(policy.capacity)
                response.headers["X-RateLimit-Remaining"] = str(int(remaining))
            except Exception:
                # Header injection should never break a successful response.
                pass
            return response

        retry_seconds = max(1, int(round(retry_after)))
        rid = getattr(request.state, REQUEST_ID_STATE_KEY, None)
        if not isinstance(rid, str) or not rid:
            rid = f"req_{uuid.uuid4().hex[:12]}"

        body = {
            "success": False,
            "error": {
                "code": ApiErrorCode.RATE_LIMITED.value,
                "message": (
                    f"Rate limit exceeded for policy '{policy.name}'."
                    " Please retry later."
                ),
                "details": {
                    "policy": policy.name,
                    "scope": policy.scope,
                    "limit": policy.capacity,
                    "retry_after_seconds": retry_seconds,
                },
            },
            "request_id": rid,
        }
        headers = {
            "Retry-After": str(retry_seconds),
            "X-RateLimit-Policy": policy.name,
            "X-RateLimit-Limit": str(policy.capacity),
            "X-RateLimit-Remaining": "0",
            REQUEST_ID_HEADER: rid,
        }

        logger.warning(
            "prd10_rate_limited",
            extra={
                "prd10_request_id": rid,
                "prd10_method": method,
                "prd10_path": path,
                "prd10_policy": policy.name,
                "prd10_scope": policy.scope,
                "prd10_retry_after_seconds": retry_seconds,
            },
        )

        return JSONResponse(content=body, status_code=429, headers=headers)
