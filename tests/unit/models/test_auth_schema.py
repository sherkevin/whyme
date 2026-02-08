"""Test authentication schema validation."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from agent_os.auth.schema import (
    UserRegister,
    UserLogin,
    RefreshTokenRequest,
    UserSettingsUpdate,
    Token,
    UserResponse,
    UserInfo,
    UserSettings,
    ErrorResponse,
)


class TestUserRegisterSchema:
    """Test UserRegister schema validation."""

    def test_valid_user_register(self):
        """Test creating valid user registration."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        }

        user = UserRegister(**data)

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "password123"

    def test_username_too_short(self):
        """Test username too short raises error."""
        data = {
            "username": "ab",  # Less than 3 characters
            "email": "test@example.com",
            "password": "password123"
        }

        with pytest.raises(ValidationError):
            UserRegister(**data)

    def test_username_too_long(self):
        """Test username too long raises error."""
        data = {
            "username": "a" * 51,  # More than 50 characters
            "email": "test@example.com",
            "password": "password123"
        }

        with pytest.raises(ValidationError):
            UserRegister(**data)

    def test_password_too_short(self):
        """Test password too short raises error."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "abcde"  # Less than 6 characters
        }

        with pytest.raises(ValidationError):
            UserRegister(**data)

    def test_invalid_email(self):
        """Test invalid email raises error."""
        data = {
            "username": "testuser",
            "email": "not-an-email",
            "password": "password123"
        }

        with pytest.raises(ValidationError):
            UserRegister(**data)

    def test_missing_required_field(self):
        """Test missing required field raises error."""
        data = {
            "username": "testuser",
            "email": "test@example.com"
            # Missing password
        }

        with pytest.raises(ValidationError):
            UserRegister(**data)


class TestUserLoginSchema:
    """Test UserLogin schema validation."""

    def test_valid_login(self):
        """Test creating valid login."""
        data = {
            "username": "testuser",
            "password": "password123"
        }

        login = UserLogin(**data)

        assert login.username == "testuser"
        assert login.password == "password123"

    def test_login_with_email(self):
        """Test login with email as username."""
        data = {
            "username": "user@example.com",
            "password": "password123"
        }

        login = UserLogin(**data)

        assert login.username == "user@example.com"


class TestRefreshTokenRequestSchema:
    """Test RefreshTokenRequest schema validation."""

    def test_valid_refresh_request(self):
        """Test creating valid refresh token request."""
        data = {
            "refresh_token": "valid.refresh.token"
        }

        request = RefreshTokenRequest(**data)

        assert request.refresh_token == "valid.refresh.token"


class TestUserSettingsUpdateSchema:
    """Test UserSettingsUpdate schema validation."""

    def test_valid_settings_update(self):
        """Test creating valid settings update."""
        data = {
            "daily_goal": 15,
            "theme": "dark",
            "language": "en"
        }

        settings = UserSettingsUpdate(**data)

        assert settings.daily_goal == 15
        assert settings.theme == "dark"
        assert settings.language == "en"

    def test_partial_settings_update(self):
        """Test partial settings update (only some fields)."""
        data = {
            "daily_goal": 20
        }

        settings = UserSettingsUpdate(**data)

        assert settings.daily_goal == 20
        assert settings.theme is None
        assert settings.language is None

    def test_daily_goal_too_low(self):
        """Test daily_goal below minimum raises error."""
        data = {
            "daily_goal": 0  # Less than 1
        }

        with pytest.raises(ValidationError):
            UserSettingsUpdate(**data)

    def test_daily_goal_too_high(self):
        """Test daily_goal above maximum raises error."""
        data = {
            "daily_goal": 101  # More than 100
        }

        with pytest.raises(ValidationError):
            UserSettingsUpdate(**data)

    def test_invalid_theme(self):
        """Test invalid theme raises error."""
        data = {
            "theme": "blue"  # Must be "light" or "dark"
        }

        with pytest.raises(ValidationError):
            UserSettingsUpdate(**data)


class TestTokenSchema:
    """Test Token schema validation."""

    def test_valid_token_response(self):
        """Test creating valid token response."""
        data = {
            "access_token": "access.token.here",
            "refresh_token": "refresh.token.here",
            "token_type": "bearer",
            "expires_in": 1800
        }

        token = Token(**data)

        assert token.access_token == "access.token.here"
        assert token.refresh_token == "refresh.token.here"
        assert token.token_type == "bearer"
        assert token.expires_in == 1800

    def test_token_default_values(self):
        """Test token response with default values."""
        data = {
            "access_token": "access.token",
            "refresh_token": "refresh.token",
            "expires_in": 1800
        }

        token = Token(**data)

        assert token.token_type == "bearer"  # Default


class TestUserInfoSchema:
    """Test UserInfo schema validation."""

    def test_valid_user_info(self):
        """Test creating valid user info."""
        now = datetime.now()

        data = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "daily_goal": 15,
            "theme": "dark",
            "language": "zh",
            "created_at": now
        }

        user_info = UserInfo(**data)

        assert user_info.id == 1
        assert user_info.username == "testuser"
        assert user_info.email == "test@example.com"
        assert user_info.daily_goal == 15
        assert user_info.theme == "dark"
        assert user_info.language == "zh"
        assert user_info.created_at == now


class TestUserSettingsSchema:
    """Test UserSettings schema validation."""

    def test_valid_user_settings(self):
        """Test creating valid user settings."""
        data = {
            "daily_goal": 20,
            "theme": "light",
            "language": "en"
        }

        settings = UserSettings(**data)

        assert settings.daily_goal == 20
        assert settings.theme == "light"
        assert settings.language == "en"

    def test_user_settings_defaults(self):
        """Test user settings with default values."""
        settings = UserSettings()

        assert settings.daily_goal == 10
        assert settings.theme == "light"
        assert settings.language == "zh"


class TestErrorResponseSchema:
    """Test ErrorResponse schema validation."""

    def test_valid_error_response(self):
        """Test creating valid error response."""
        data = {
            "detail": "User not found",
            "error_code": "USER_NOT_FOUND"
        }

        error = ErrorResponse(**data)

        assert error.detail == "User not found"
        assert error.error_code == "USER_NOT_FOUND"

    def test_error_response_without_code(self):
        """Test error response without error code."""
        data = {
            "detail": "Validation error"
        }

        error = ErrorResponse(**data)

        assert error.detail == "Validation error"
        assert error.error_code is None
