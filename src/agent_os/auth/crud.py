"""CRUD operations for authentication and user management."""

import uuid
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash, verify_password


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Get user by ID.

    Args:
        db: Database session
        user_id: User ID (UUID)

    Returns:
        User object or None
    """
    result = await db.execute(
        select(User).filter(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username.

    Args:
        db: Database session
        username: Username

    Returns:
        User object or None
    """
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email.

    Args:
        db: Database session
        email: Email address

    Returns:
        User object or None
    """
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str
) -> User:
    """Create a new user.

    Args:
        db: Database session
        username: Username
        email: Email address
        password: Plain text password

    Returns:
        Created user object
    """
    # Hash password
    password_hash = get_password_hash(password)

    # Create user with default settings
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        settings={
            "daily_goal": 10,
            "theme": "light",
            "language": "zh"
        }
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str
) -> Optional[User]:
    """Authenticate user with username/email and password.

    Args:
        db: Database session
        username: Username or email
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    # Try username first, then email
    user = await get_user_by_username(db, username)
    if user is None:
        user = await get_user_by_email(db, username)

    if user is None:
        return None

    # Verify password
    if not verify_password(password, user.password_hash):
        return None

    return user


async def update_user_settings(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Dict[str, Any]
) -> Optional[User]:
    """Update user settings.

    Args:
        db: Database session
        user_id: User ID (UUID)
        settings: Settings dict to merge into existing settings

    Returns:
        Updated user object or None
    """
    # Get user
    user = await get_user_by_id(db, user_id)

    if user is None:
        return None

    # Merge settings
    user.settings = {**user.settings, **settings}

    await db.commit()
    await db.refresh(user)

    return user
