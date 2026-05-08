"""Unit tests for ``agent_os.common.sentry_setup``.

Sentry is integrated with the FastAPI app at module-import time, but the
init call must:

1. Be a complete no-op when ``SENTRY_DSN`` is unset (default for dev,
   tests, and demos).
2. Activate exactly once when DSN is present, applying our PRD10-shaped
   defaults (environment, release, sample rates, send_default_pii=False).
3. Scrub Authorization headers, password / token bodies, and other
   well-known secrets via the ``before_send`` hook **before** the event
   leaves the process.
4. Drop ``/health`` / ``/ready`` / ``/metrics`` transactions to avoid
   burning the quota on infra noise.
5. Stay resilient if ``sentry_sdk.init`` itself raises (network DNS
   failure, malformed DSN, etc.) — the app must not crash on startup.

These tests exercise the helpers directly with mocked ``sentry_sdk.init``
so we never touch the real Sentry network.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agent_os.common.sentry_setup import (
    _SECRET_BODY_KEYS,
    _SECRET_HEADER_KEYS,
    _before_send,
    _before_send_transaction,
    _scrub_event,
    _scrub_mapping,
    capture_exception,
    capture_message,
    get_sentry_state,
    init_sentry,
    is_sentry_enabled,
    reset_sentry_state_for_test,
)


@pytest.fixture(autouse=True)
def _isolate_sentry_state(monkeypatch):
    """Each test starts with cleared module state and known env."""

    reset_sentry_state_for_test()
    for key in (
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_RELEASE",
        "SENTRY_TRACES_SAMPLE_RATE",
        "SENTRY_SAMPLE_RATE",
        "SENTRY_SEND_DEFAULT_PII",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    reset_sentry_state_for_test()


# ---------------------------------------------------------------------------
# init_sentry
# ---------------------------------------------------------------------------


def test_init_sentry_is_noop_without_dsn():
    """Default deploy / dev / CI must not initialize Sentry."""

    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        result = init_sentry()
        assert result is False
        assert is_sentry_enabled() is False
        mock_sdk.init.assert_not_called()

    state = get_sentry_state()
    assert state["initialized"] is True
    assert state["enabled"] is False
    assert state["dsn_present"] is False


def test_init_sentry_initializes_once_when_dsn_set(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_RELEASE", "v1.2.3")

    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        result = init_sentry()
        assert result is True
        assert is_sentry_enabled() is True

        mock_sdk.init.assert_called_once()
        kwargs = mock_sdk.init.call_args.kwargs
        assert kwargs["dsn"] == "https://abc@example.com/1"
        assert kwargs["environment"] == "staging"
        assert kwargs["release"] == "v1.2.3"
        assert kwargs["send_default_pii"] is False
        # Default sample rates from PRD10
        assert 0.0 <= kwargs["traces_sample_rate"] <= 1.0
        assert 0.0 <= kwargs["sample_rate"] <= 1.0


def test_init_sentry_is_idempotent(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        assert init_sentry() is True
        assert init_sentry() is True  # Second call should not re-init.
        mock_sdk.init.assert_called_once()


def test_init_sentry_force_reinitializes(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        init_sentry(force=True)
        assert mock_sdk.init.call_count == 2


def test_init_sentry_falls_back_to_environment_var(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        kwargs = mock_sdk.init.call_args.kwargs
        assert kwargs["environment"] == "production"


def test_init_sentry_uses_default_environment_when_unset(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        kwargs = mock_sdk.init.call_args.kwargs
        assert kwargs["environment"] == "development"


def test_init_sentry_clamps_invalid_sample_rate(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "5.0")  # > 1
    monkeypatch.setenv("SENTRY_SAMPLE_RATE", "-0.5")  # < 0
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        kwargs = mock_sdk.init.call_args.kwargs
        assert kwargs["traces_sample_rate"] == 1.0
        assert kwargs["sample_rate"] == 0.0


def test_init_sentry_handles_invalid_sample_rate_gracefully(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "not-a-number")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        kwargs = mock_sdk.init.call_args.kwargs
        # Falls back to PRD10 default 0.1
        assert kwargs["traces_sample_rate"] == 0.1


def test_init_sentry_send_default_pii_opt_in(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "on")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        kwargs = mock_sdk.init.call_args.kwargs
        assert kwargs["send_default_pii"] is True


def test_init_sentry_resilient_against_init_failure(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        mock_sdk.init.side_effect = RuntimeError("network down")
        result = init_sentry()
        assert result is False
        assert is_sentry_enabled() is False
        # State is still marked initialized so we don't retry per-request.
        assert get_sentry_state()["initialized"] is True


# ---------------------------------------------------------------------------
# Scrubbing logic
# ---------------------------------------------------------------------------


def test_scrub_mapping_redacts_secret_keys():
    payload = {
        "username": "alice",
        "password": "topsecret",
        "settings": {
            "api_key": "abc",
            "favorite_color": "blue",
        },
    }
    cleaned = _scrub_mapping(payload, _SECRET_BODY_KEYS)
    assert cleaned["username"] == "alice"
    assert cleaned["password"] == "[Filtered]"
    assert cleaned["settings"]["api_key"] == "[Filtered]"
    assert cleaned["settings"]["favorite_color"] == "blue"


def test_scrub_mapping_handles_lists():
    payload = [{"token": "x"}, {"name": "y"}]
    cleaned = _scrub_mapping(payload, _SECRET_BODY_KEYS)
    assert cleaned[0]["token"] == "[Filtered]"
    assert cleaned[1]["name"] == "y"


def test_scrub_mapping_is_case_insensitive():
    payload = {"AUTHORIZATION": "Bearer xxx"}
    cleaned = _scrub_mapping(payload, _SECRET_HEADER_KEYS)
    assert cleaned["AUTHORIZATION"] == "[Filtered]"


def test_scrub_event_redacts_authorization_header():
    event = {
        "request": {
            "headers": {
                "authorization": "Bearer abcdef",
                "user-agent": "pytest",
            },
            "data": {"password": "secret", "username": "alice"},
        }
    }
    cleaned = _scrub_event(event)
    assert cleaned["request"]["headers"]["authorization"] == "[Filtered]"
    assert cleaned["request"]["headers"]["user-agent"] == "pytest"
    assert cleaned["request"]["data"]["password"] == "[Filtered]"
    assert cleaned["request"]["data"]["username"] == "alice"


def test_scrub_event_redacts_extra_and_breadcrumbs():
    event = {
        "extra": {"refresh_token": "x", "request_id": "req_abc"},
        "breadcrumbs": {
            "values": [
                {"data": {"token": "x", "endpoint": "/foo"}},
                {"data": {"endpoint": "/bar"}},
            ]
        },
    }
    cleaned = _scrub_event(event)
    assert cleaned["extra"]["refresh_token"] == "[Filtered]"
    assert cleaned["extra"]["request_id"] == "req_abc"
    assert (
        cleaned["breadcrumbs"]["values"][0]["data"]["token"]
        == "[Filtered]"
    )
    assert (
        cleaned["breadcrumbs"]["values"][0]["data"]["endpoint"]
        == "/foo"
    )


def test_before_send_returns_event_when_clean():
    event = {"request": {"headers": {}, "data": {}}}
    result = _before_send(event, {})
    assert result is event  # mutated in place


def test_before_send_drops_event_on_scrub_failure():
    """If ``_scrub_event`` itself raises, prefer dropping over leaking."""

    with patch(
        "agent_os.common.sentry_setup._scrub_event",
        side_effect=RuntimeError("boom"),
    ):
        result = _before_send({"request": {"data": {"password": "x"}}}, {})
    assert result is None


# ---------------------------------------------------------------------------
# Transaction filtering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "transaction,kept",
    [
        ("/health", False),
        ("/ready", False),
        ("/metrics", False),
        ("/favicon.ico", False),
        ("/api/v1/feed", True),
        ("/api/v1/auth/login", True),
        ("/", True),
    ],
)
def test_before_send_transaction_drops_health_and_metrics(transaction, kept):
    event = {"transaction": transaction}
    result = _before_send_transaction(event, {})
    if kept:
        assert result is event
    else:
        assert result is None


def test_before_send_transaction_keeps_event_with_no_transaction_field():
    event = {"contexts": {}}
    assert _before_send_transaction(event, {}) is event


# ---------------------------------------------------------------------------
# capture_message / capture_exception
# ---------------------------------------------------------------------------


def test_capture_message_noop_when_disabled():
    """When Sentry is off, calls must not touch the SDK."""

    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        capture_message("hello", level="info", request_id="req_x")
        mock_sdk.capture_message.assert_not_called()


def test_capture_message_active_when_enabled(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        capture_message("event", level="warning", request_id="req_y")
        mock_sdk.capture_message.assert_called_once()


def test_capture_exception_noop_when_disabled():
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        try:
            raise ValueError("boom")
        except ValueError as exc:
            capture_exception(exc)
        mock_sdk.capture_exception.assert_not_called()


def test_capture_exception_active_when_enabled(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        try:
            raise ValueError("boom")
        except ValueError as exc:
            capture_exception(exc, request_id="req_z")
        mock_sdk.capture_exception.assert_called_once()


def test_capture_helpers_swallow_internal_errors(monkeypatch):
    """Monitoring failures must never propagate into request handlers."""

    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    with patch("agent_os.common.sentry_setup.sentry_sdk") as mock_sdk:
        init_sentry()
        # sentry-sdk 2.x: capture_* uses ``new_scope`` context manager.
        mock_sdk.new_scope.side_effect = RuntimeError("scope crashed")
        capture_message("noop")
        capture_exception(ValueError("noop"))


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


def test_state_exposes_useful_fields(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@example.com/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "production")
    monkeypatch.setenv("SENTRY_RELEASE", "abcd1234")
    with patch("agent_os.common.sentry_setup.sentry_sdk"):
        init_sentry()
    state = get_sentry_state()
    assert state["enabled"] is True
    assert state["dsn_present"] is True
    assert state["environment"] == "production"
    assert state["release"] == "abcd1234"
