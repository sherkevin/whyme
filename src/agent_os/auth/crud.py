"""CRUD operations for authentication and user management."""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash, password_needs_rehash, verify_password


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
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


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Get user by username.

    Args:
        db: Database session
        username: Username

    Returns:
        User object or None
    """
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
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
) -> User | None:
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

    if password_needs_rehash(user.password_hash):
        user.password_hash = get_password_hash(password)
        await db.commit()
        await db.refresh(user)

    return user


async def update_user_settings(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: dict[str, Any]
) -> User | None:
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


async def update_user_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    current_password: str,
    new_password: str,
) -> User | None:
    """Rotate a user's password after verifying the current one.

    Returns the refreshed user on success, ``None`` if the user is missing.
    Raises ``ValueError`` with a stable code (``current_password_invalid`` /
    ``same_password``) so the router can map it to a PRD10 envelope.
    """

    user = await get_user_by_id(db, user_id)
    if user is None:
        return None

    if not verify_password(current_password, user.password_hash):
        raise ValueError("current_password_invalid")

    if verify_password(new_password, user.password_hash):
        raise ValueError("same_password")

    user.password_hash = get_password_hash(new_password)

    await db.commit()
    await db.refresh(user)
    return user


async def update_prd10_me(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    name: str | None = None,
    avatar_url: str | None = None,
    settings_patch: dict[str, Any] | None = None,
) -> User | None:
    """PRD10 §5.1 / §5.2 ``PATCH /api/v1/me`` mutation helper.

    Performs:

    * ``User.full_name`` ← ``name`` if provided.
    * ``User.avatar_url`` ← ``avatar_url`` if provided.
    * **Deep merge** ``settings_patch`` into ``User.settings``, where
      ``notification_channels`` is itself merged so flipping a single channel
      doesn't wipe sibling flags.

    The router is responsible for whitelist filtering; this helper only does
    the persistence. Returns the refreshed ``User`` row, or ``None`` if the
    user no longer exists.
    """
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None

    if name is not None:
        user.full_name = name
    if avatar_url is not None:
        user.avatar_url = avatar_url

    if settings_patch:
        existing = dict(user.settings or {})
        # Special-case nested ``notification_channels`` for deep merge so the
        # frontend can flip a single channel without resending every key.
        if "notification_channels" in settings_patch:
            existing_channels = dict(existing.get("notification_channels") or {})
            patch_channels = dict(settings_patch["notification_channels"] or {})
            existing_channels.update(patch_channels)
            settings_patch = {
                **settings_patch,
                "notification_channels": existing_channels,
            }
        existing.update(settings_patch)
        user.settings = existing

    await db.commit()
    await db.refresh(user)
    return user
