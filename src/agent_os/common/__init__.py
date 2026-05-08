"""Shared helpers for PRD10-aligned backend APIs."""

from agent_os.common.errors import DEFAULT_STATUS_BY_CODE, ApiError, ApiErrorCode
from agent_os.common.logging import JsonLogFormatter, configure_logging
from agent_os.common.metrics import (
    PRD10_LATENCY_TARGETS_MS,
    MetricsRegistry,
    get_default_metrics,
    is_metrics_enabled,
    normalize_path,
    reset_default_metrics_for_test,
)
from agent_os.common.middleware import (
    Prd10AccessLogMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
)
from agent_os.common.pagination import Pagination, build_pagination
from agent_os.common.rate_limit import (
    DEFAULT_POLICIES,
    InMemoryRateLimitStore,
    RateLimitPolicy,
    derive_key,
    get_default_store,
    is_rate_limit_enabled,
    reset_default_store_for_test,
    select_policy,
)
from agent_os.common.response import (
    REQUEST_ID_HEADER,
    REQUEST_ID_STATE_KEY,
    error_json_response,
    error_response,
    error_response_from,
    get_request_id,
    http_exception_to_envelope,
    paginated_json_response,
    paginated_response,
    success_json_response,
    success_response,
)
from agent_os.common.sentry_setup import (
    capture_exception,
    capture_message,
    get_sentry_state,
    init_sentry,
    is_sentry_enabled,
    reset_sentry_state_for_test,
)

__all__ = [
    "ApiError",
    "ApiErrorCode",
    "DEFAULT_STATUS_BY_CODE",
    "Pagination",
    "build_pagination",
    "success_response",
    "paginated_response",
    "error_response",
    "error_response_from",
    "success_json_response",
    "paginated_json_response",
    "error_json_response",
    "http_exception_to_envelope",
    "get_request_id",
    "Prd10AccessLogMiddleware",
    "RateLimitMiddleware",
    "RequestIdMiddleware",
    "REQUEST_ID_HEADER",
    "REQUEST_ID_STATE_KEY",
    "JsonLogFormatter",
    "configure_logging",
    # Rate limiting (PRD10 §29)
    "DEFAULT_POLICIES",
    "InMemoryRateLimitStore",
    "RateLimitPolicy",
    "derive_key",
    "get_default_store",
    "is_rate_limit_enabled",
    "reset_default_store_for_test",
    "select_policy",
    # Sentry error monitoring (PRD10 §11.5)
    "capture_exception",
    "capture_message",
    "get_sentry_state",
    "init_sentry",
    "is_sentry_enabled",
    "reset_sentry_state_for_test",
    # Metrics & P95 monitoring (PRD10 §12.1 / §25.2)
    "MetricsRegistry",
    "PRD10_LATENCY_TARGETS_MS",
    "get_default_metrics",
    "is_metrics_enabled",
    "normalize_path",
    "reset_default_metrics_for_test",
]
