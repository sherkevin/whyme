"""Authentication API router."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.base import get_db
from agent_os.auth import crud
from agent_os.auth.schema import (
    UserRegister,
    Token,
    UserInfo,
    UserSettingsUpdate,
    ErrorResponse,
)
from agent_os.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from agent_os.auth.dependencies import get_current_user, get_current_user_id
from agent_os.auth.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "User already exists"}
    }
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user.

    Creates a new user account with default settings and returns authentication tokens.
    """
    # Check if username exists
    existing_user = await crud.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email exists
    existing_email = await crud.get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = await crud.create_user(
        db=db,
        username=user_data.username,
        email=user_data.email,
        password=user_data.password
    )

    # Generate tokens
    access_token = create_access_token(user_id=user.id)
    refresh_token = create_refresh_token(user_id=user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=30 * 60  # 30 minutes
    )


@router.post(
    "/login",
    response_model=Token,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"}
    }
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login with username/email and password.

    Uses OAuth2 password flow for token-based authentication.
    """
    # Authenticate user
    user = await crud.authenticate_user(
        db=db,
        username=form_data.username,
        password=form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate tokens
    access_token = create_access_token(user_id=user.id)
    refresh_token = create_refresh_token(user_id=user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=30 * 60
    )


@router.post(
    "/refresh",
    response_model=Token,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"}
    }
)
async def refresh_token(
    token_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token.

    Validates the refresh token and issues a new access token.
    """
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required"
        )

    # Verify refresh token
    token_info = verify_token(refresh_token, token_type="refresh")
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Check if user exists
    user = await crud.get_user_by_id(db, token_info.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Generate new tokens
    access_token = create_access_token(user_id=user.id)
    new_refresh_token = create_refresh_token(user_id=user.id)

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=30 * 60
    )


@router.get(
    "/users/me",
    response_model=UserInfo,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"}
    }
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information.

    Returns user details including settings.
    """
    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        daily_goal=current_user.settings.daily_goal if current_user.settings else 10,
        theme=current_user.settings.theme if current_user.settings else "light",
        language=current_user.settings.language if current_user.settings else "zh",
        created_at=current_user.created_at
    )


@router.put(
    "/users/settings",
    response_model=UserInfo,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"}
    }
)
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user settings.

    Updates daily goal, theme, and/or language preferences.
    """
    # Update settings
    settings = await crud.update_user_settings(
        db=db,
        user_id=current_user.id,
        daily_goal=settings_update.daily_goal,
        theme=settings_update.theme,
        language=settings_update.language
    )

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settings not found"
        )

    # Return updated user info
    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        daily_goal=settings.daily_goal,
        theme=settings.theme,
        language=settings.language,
        created_at=current_user.created_at
    )
