"""JWT token creation and validation."""

from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

# JWT Configuration
SECRET_KEY = "your-secret-key-change-in-production"  # TODO: Move to config
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID (as string for JWT)
    exp: Optional[datetime] = None
    type: str = "access"  # access or refresh


class TokenData(BaseModel):
    """Data extracted from token."""
    user_id: int
    token_type: str


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Create an access token for a user.

    Args:
        user_id: User ID
        expires_delta: Optional custom expiration time

    Returns:
        JWT access token
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),  # Convert to string for JWT
        "exp": expire,
        "type": "access"
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int) -> str:
    """Create a refresh token for a user.

    Args:
        user_id: User ID

    Returns:
        JWT refresh token
    """
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),  # Convert to string for JWT
        "exp": expire,
        "type": "refresh"
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenData if valid, None if invalid

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Validate payload structure
        token_payload = TokenPayload(**payload)

        # Check token type
        if token_payload.type != token_type:
            return None

        # Extract user ID (convert from string to int)
        user_id: int = int(token_payload.sub)

        return TokenData(user_id=user_id, token_type=token_payload.type)

    except (JWTError, ValidationError):
        return None


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a token without verification (for debugging).

    Args:
        token: JWT token string

    Returns:
        Decoded payload or None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
