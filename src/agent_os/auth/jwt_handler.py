"""JWT token creation and validation using security.py functions.

This module provides a compatibility layer for existing code that imports from jwt_handler.
The actual implementation is in security.py.
"""

import uuid
from datetime import timedelta
from typing import Optional

from agent_os.auth.security import create_access_token as _create_access_token
from agent_os.auth.security import create_refresh_token as _create_refresh_token
from agent_os.auth.security import decode_token


class TokenData:
    """Data extracted from token."""
    def __init__(self, user_id: uuid.UUID, token_type: str):
        self.user_id = user_id
        self.token_type = token_type


def create_access_token(
    user_id: uuid.UUID,
    expires_delta: timedelta | None = None
) -> str:
    """Create an access token for a user.

    Args:
        user_id: User ID (UUID)
        expires_delta: Optional custom expiration time

    Returns:
        JWT access token
    """
    # Convert UUID to string for JWT
    data = {"sub": str(user_id)}
    return _create_access_token(data, expires_delta)


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a refresh token for a user.

    Args:
        user_id: User ID (UUID)

    Returns:
        JWT refresh token
    """
    # Convert UUID to string for JWT
    data = {"sub": str(user_id)}
    return _create_refresh_token(data)


def verify_token(token: str, token_type: str = "access") -> TokenData | None:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenData if valid, None if invalid
    """
    payload = decode_token(token)

    if payload is None:
        return None

    # Check token type
    if payload.get("type") != token_type:
        return None

    # Extract user ID (convert from string to UUID)
    try:
        user_id = uuid.UUID(payload.get("sub", ""))
        return TokenData(user_id=user_id, token_type=payload.get("type", "access"))
    except (ValueError, AttributeError):
        return None
