"""Authentication module."""

from agent_os.auth.models import User, UserSettings
from agent_os.auth.security import verify_password, get_password_hash
from agent_os.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
    TokenData
)
from agent_os.auth.dependencies import get_current_user, get_current_user_id

__all__ = [
    # Models
    "User",
    "UserSettings",
    # Security
    "verify_password",
    "get_password_hash",
    # JWT
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "TokenData",
    # Dependencies
    "get_current_user",
    "get_current_user_id",
]
