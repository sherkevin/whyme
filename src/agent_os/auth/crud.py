"""CRUD operations for authentication and user management."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_os.auth.models import User, UserSettings
from agent_os.auth.security import get_password_hash, verify_password


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        User object or None
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.settings))
        .filter(User.id == user_id)
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
    hashed_password = get_password_hash(password)

    # Create user
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create default settings
    settings = UserSettings(
        user_id=user.id,
        daily_goal=10,
        theme="light",
        language="zh"
    )
    db.add(settings)
    await db.commit()

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
    if not verify_password(password, user.hashed_password):
        return None

    # Load settings
    user_with_settings = await get_user_by_id(db, user.id)
    return user_with_settings


async def update_user_settings(
    db: AsyncSession,
    user_id: int,
    daily_goal: Optional[int] = None,
    theme: Optional[str] = None,
    language: Optional[str] = None
) -> Optional[UserSettings]:
    """Update user settings.

    Args:
        db: Database session
        user_id: User ID
        daily_goal: Daily card goal
        theme: UI theme
        language: Language code

    Returns:
        Updated settings object or None
    """
    # Get settings
    result = await db.execute(
        select(UserSettings).filter(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        return None

    # Update fields
    if daily_goal is not None:
        settings.daily_goal = daily_goal
    if theme is not None:
        settings.theme = theme
    if language is not None:
        settings.language = language

    await db.commit()
    await db.refresh(settings)

    return settings
