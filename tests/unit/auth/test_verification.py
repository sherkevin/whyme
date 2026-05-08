"""Unit tests for Auth Verification Service.

Tests B-03B and B-03C: Verification code generation and validation.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_os.auth.verification import (
    ExpiredCodeError,
    InvalidCodeError,
    LockedError,
    RateLimitError,
    TooManyAttemptsError,
    VerificationService,
    get_verification_service,
)


@pytest.fixture
def redis():
    """Create mock Redis client.

    The default ``MagicMock`` returns truthy ``MagicMock`` objects for every
    attribute access, which makes ``redis.exists(lock_key)`` accidentally
    look like a locked account inside ``check_locked``. We seed sensible
    defaults so individual tests only need to override the redis behavior
    they actually care about.
    """
    mock = MagicMock()
    mock.exists.return_value = False
    mock.get.return_value = None
    mock.incr.return_value = 1
    return mock


@pytest.fixture
def verification(redis):
    """Create verification service instance."""
    return VerificationService(redis)


class TestVerificationService:
    """Test verification service core functionality."""

    def test_generate_code(self, verification):
        """Test code generation."""
        code = verification.generate_code()

        assert len(code) == 6
        assert code.isdigit()
        assert 0 <= int(code) <= 999999

    def test_generate_code_unique(self, verification):
        """Test codes are reasonably unique."""
        codes = [verification.generate_code() for _ in range(100)]

        # Should have at least 90 unique codes out of 100
        unique_codes = set(codes)
        assert len(unique_codes) >= 90

    def test_create_code_success(self, verification, redis):
        """Test successful code creation."""
        redis.exists.return_value = False

        code = verification.create_code(
            email="test@example.com",
            code_type="login",
            ip="127.0.0.1"
        )

        assert len(code) == 6

        # Verify Redis calls
        redis.setex.assert_called()
        calls = [str(call) for call in redis.setex.call_args_list]

        # Should set code, email rate limit, and IP rate limit
        assert len(calls) >= 2  # At least code + email rate limit

    def test_create_code_rate_limit_email(self, verification, redis):
        """Test email rate limiting."""
        # Email already rate limited
        redis.exists.return_value = True
        redis.ttl.return_value = 30

        with pytest.raises(RateLimitError) as e:
            verification.create_code(
                email="test@example.com",
                code_type="login",
                ip="127.0.0.1"
            )

        assert e.value.retry_after == 30

    def test_create_code_rate_limit_ip(self, verification, redis):
        """Test IP rate limiting."""
        # IP rate limited but email not
        def exists_side_effect(key):
            return "rate_limit:ip:" in key

        redis.exists.side_effect = exists_side_effect
        redis.ttl.return_value = 45

        with pytest.raises(RateLimitError) as e:
            verification.create_code(
                email="test@example.com",
                code_type="login",
                ip="127.0.0.1"
            )

        assert e.value.retry_after == 45

    def test_create_code_locked(self, verification, redis):
        """Test locked account rejection."""
        redis.exists.side_effect = lambda key: "verify_locked:" in key
        redis.ttl.return_value = 300

        with pytest.raises(LockedError):
            verification.create_code(
                email="locked@example.com",
                code_type="login",
                ip="127.0.0.1"
            )

    def test_verify_code_success(self, verification, redis):
        """Test successful code verification."""
        redis.get.return_value = "123456"

        result = verification.verify_code(
            email="test@example.com",
            code="123456",
            code_type="login"
        )

        assert result is True

        # Code should be deleted
        redis.delete.assert_called()

    def test_verify_code_incorrect(self, verification, redis):
        """Test incorrect code."""
        redis.get.return_value = "654321"  # Different code
        redis.incr.return_value = 1

        with pytest.raises(InvalidCodeError):
            verification.verify_code(
                email="test@example.com",
                code="123456",
                code_type="login"
            )

    def test_verify_code_expired(self, verification, redis):
        """Test expired code."""
        redis.get.return_value = None  # Code doesn't exist

        with pytest.raises(ExpiredCodeError):
            verification.verify_code(
                email="test@example.com",
                code="123456",
                code_type="login"
            )

    def test_verify_code_too_many_attempts(self, verification, redis):
        """Test lockout after too many attempts."""
        redis.get.return_value = "654321"  # Wrong code

        # Simulate 4 previous attempts
        redis.incr.return_value = 5

        with pytest.raises(TooManyAttemptsError):
            verification.verify_code(
                email="test@example.com",
                code="123456",
                code_type="login"
            )

        # Should set lock
        assert redis.setex.called

    def test_verify_code_locked(self, verification, redis):
        """Test verification when account is locked."""
        redis.exists.side_effect = lambda key: "verify_locked:" in key

        with pytest.raises(LockedError):
            verification.verify_code(
                email="locked@example.com",
                code="123456",
                code_type="login"
            )


class TestVerificationServiceTypes:
    """Test different verification code types."""

    def test_login_type(self, verification, redis):
        """Test login verification code."""
        redis.exists.return_value = False

        code = verification.create_code(
            email="test@example.com",
            code_type="login"
        )

        assert len(code) == 6

    def test_bind_type(self, verification, redis):
        """Test email binding verification code."""
        redis.exists.return_value = False

        code = verification.create_code(
            email="test@example.com",
            code_type="bind"
        )

        assert len(code) == 6

    def test_reset_type(self, verification, redis):
        """Test password reset verification code."""
        redis.exists.return_value = False

        code = verification.create_code(
            email="test@example.com",
            code_type="reset"
        )

        assert len(code) == 6

    def test_invalid_type(self, verification, redis):
        """Test invalid code type."""
        with pytest.raises(ValueError, match="Invalid code type"):
            verification.create_code(
                email="test@example.com",
                code_type="invalid"
            )


class TestVerificationServiceRemainingAttempts:
    """Test remaining attempts calculation."""

    def test_no_attempts(self, verification, redis):
        """Test remaining attempts with no failures."""
        redis.exists.return_value = False
        redis.get.return_value = None

        remaining = verification.get_remaining_attempts(
            email="test@example.com",
            code_type="login"
        )

        assert remaining == 5  # MAX_ATTEMPTS

    def test_some_attempts(self, verification, redis):
        """Test remaining attempts after some failures."""
        redis.exists.return_value = False
        redis.get.return_value = "2"  # 2 failed attempts

        remaining = verification.get_remaining_attempts(
            email="test@example.com",
            code_type="login"
        )

        assert remaining == 3  # 5 - 2

    def test_locked_zero_attempts(self, verification, redis):
        """Test zero attempts when locked."""
        redis.exists.side_effect = lambda key: "verify_locked:" in key

        remaining = verification.get_remaining_attempts(
            email="test@example.com",
            code_type="login"
        )

        assert remaining == 0


class TestVerificationServiceOneTimeUse:
    """Test one-time use consumption."""

    def test_code_deleted_after_use(self, verification, redis):
        """Test code is deleted after successful verification."""
        redis.get.return_value = "123456"

        verification.verify_code(
            email="test@example.com",
            code="123456",
            code_type="login"
        )

        # Verify delete was called for code key
        delete_calls = [str(call) for call in redis.delete.call_args_list]
        assert any("verify_code:" in str(call) for call in delete_calls)

    def test_attempts_cleared_after_use(self, verification, redis):
        """Test attempts cleared after successful verification."""
        redis.get.return_value = "123456"

        verification.verify_code(
            email="test@example.com",
            code="123456",
            code_type="login"
        )

        # Verify delete was called for attempts key
        assert redis.delete.called


class TestGetVerificationService:
    """Test verification service factory.

    The factory does ``from agent_os.db.cache import get_redis`` lazily, so
    the patch target must follow that import path rather than the legacy
    ``agent_os.auth.verification.get_redis`` (which never existed as a
    module attribute).
    """

    @patch('agent_os.db.cache.get_redis')
    def test_returns_service(self, mock_get_redis):
        """Test factory returns VerificationService."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        service = get_verification_service()

        assert service is not None
        assert isinstance(service, VerificationService)

    @patch('agent_os.db.cache.get_redis')
    def test_returns_none_on_error(self, mock_get_redis):
        """Test factory returns None on error."""
        mock_get_redis.side_effect = Exception("Redis error")

        service = get_verification_service()

        assert service is None
