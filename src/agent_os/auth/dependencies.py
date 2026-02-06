"""FastAPI dependencies for authentication."""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agent_os.db.base import get_db
from agent_os.auth.jwt_handler import verify_token, TokenData
from agent_os.auth.models import User


# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Check if token is provided
    if credentials is None:
        raise credentials_exception

    # Verify token
    token_data: Optional[TokenData] = verify_token(
        credentials.credentials,
        token_type="access"
    )

    if token_data is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(
        select(User).filter(User.id == token_data.user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user.

    Args:
        current_user: Current user from token

    Returns:
        Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_user_id(
    current_user: User = Depends(get_current_user)
) -> uuid.UUID:
    """Get current user ID (lightweight version).

    Use this when you only need the user ID, not the full user object.

    Args:
        current_user: Current user from token

    Returns:
        User ID (UUID)
    """
    return current_user.id


# Optional authentication (doesn't raise error if no token)
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if token provided, otherwise None.

    Args:
        credentials: HTTP Bearer credentials (optional)
        db: Database session

    Returns:
        User if token valid, None otherwise
    """
    if credentials is None:
        return None

    token_data = verify_token(credentials.credentials, token_type="access")
    if token_data is None:
        return None

    result = await db.execute(
        select(User).filter(User.id == token_data.user_id)
    )
    user = result.scalar_one_or_none()

    return user
