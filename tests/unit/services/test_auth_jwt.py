"""Test JWT token creation and validation."""

import pytest
import uuid
from datetime import timedelta, datetime, timezone

from agent_os.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    TokenData,
)


class TestAccessTokenCreation:
    """Test access token creation."""

    def test_create_access_token_returns_string(self):
        """Test creating access token returns a string."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id)

        assert isinstance(token, str)
        assert len(token) > 0
        # JWT has 3 parts separated by dots
        assert "." in token

    def test_create_access_token_with_custom_expiration(self):
        """Test creating access token with custom expiration."""
        user_id = uuid.uuid4()
        expires = timedelta(minutes=60)
        token = create_access_token(user_id=user_id, expires_delta=expires)

        assert isinstance(token, str)

        # Decode and check expiration
        payload = decode_token(token)
        assert payload is not None
        # Use UTC for comparison
        exp = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Should be about 60 minutes from now (within 1 minute tolerance)
        time_diff = exp - now
        assert 59 * 60 <= time_diff.total_seconds() <= 61 * 60

    def test_create_access_token_default_expiration(self):
        """Test creating access token with default expiration (30 minutes)."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id)

        payload = decode_token(token)
        assert payload is not None
        # Use UTC for comparison
        exp = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Should be about 30 minutes from now
        time_diff = exp - now
        assert 29 * 60 <= time_diff.total_seconds() <= 31 * 60

    def test_access_token_contains_correct_payload(self):
        """Test access token contains correct payload."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id)

        payload = decode_token(token)
        assert payload['sub'] == str(user_id)  # sub is string in JWT
        assert payload['type'] == 'access'
        assert 'exp' in payload


class TestRefreshTokenCreation:
    """Test refresh token creation."""

    def test_create_refresh_token_returns_string(self):
        """Test creating refresh token returns a string."""
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id=user_id)

        assert isinstance(token, str)
        assert "." in token

    def test_refresh_token_expiration(self):
        """Test refresh token expires in 7 days."""
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id=user_id)

        payload = decode_token(token)
        assert payload is not None
        # Use UTC for comparison
        exp = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Should be about 7 days from now (within 1 minute tolerance)
        time_diff = exp - now
        expected_seconds = 7 * 24 * 60 * 60
        assert expected_seconds - 60 <= time_diff.total_seconds() <= expected_seconds + 60

    def test_refresh_token_type(self):
        """Test refresh token has type 'refresh'."""
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id=user_id)

        payload = decode_token(token)
        assert payload['type'] == 'refresh'


class TestTokenVerification:
    """Test token verification."""

    def test_verify_valid_access_token(self):
        """Test verifying valid access token."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id=user_id)

        token_data = verify_token(token, token_type="access")

        assert token_data is not None
        assert isinstance(token_data, TokenData)
        assert token_data.user_id == user_id
        assert token_data.token_type == "access"

    def test_verify_valid_refresh_token(self):
        """Test verifying valid refresh token."""
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id=user_id)

        token_data = verify_token(token, token_type="refresh")

        assert token_data is not None
        assert token_data.user_id == user_id
        assert token_data.token_type == "refresh"

    def test_verify_token_with_wrong_type_fails(self):
        """Test verifying access token as refresh token fails."""
        access_token = create_access_token(user_id=1)

        token_data = verify_token(access_token, token_type="refresh")

        assert token_data is None

    def test_verify_invalid_token_returns_none(self):
        """Test verifying invalid token returns None."""
        invalid_token = "invalid.token.string"

        token_data = verify_token(invalid_token, token_type="access")

        assert token_data is None

    def test_verify_expired_token_returns_none(self):
        """Test verifying expired token returns None."""
        # Create token with very short expiration
        expires = timedelta(seconds=-1)  # Already expired
        token = create_access_token(user_id=1, expires_delta=expires)

        token_data = verify_token(token, token_type="access")

        assert token_data is None

    def test_verify_empty_token_returns_none(self):
        """Test verifying empty token returns None."""
        token_data = verify_token("", token_type="access")

        assert token_data is None


class TestTokenDecoding:
    """Test token decoding (without verification)."""

    def test_decode_valid_token(self):
        """Test decoding valid token."""
        user_id = 789
        token = create_access_token(user_id=user_id)

        payload = decode_token(token)

        assert payload is not None
        assert isinstance(payload, dict)
        assert int(payload['sub']) == user_id  # sub is string in JWT
        assert 'exp' in payload

    def test_decode_invalid_token_returns_none(self):
        """Test decoding invalid token returns None."""
        payload = decode_token("invalid.token")

        assert payload is None
