"""Authentication API router."""

import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.base import get_db
from agent_os.auth import crud
from agent_os.auth.schema import (
    UserRegister,
    Token,
    UserInfo,
    UserInfoWithStats,
    UserGardenStats,
    UserSettingsUpdate,
    ErrorResponse,
    RefreshTokenRequest,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
    RateLimitResponse,
    EmailRegisterRequest,
    EmailLoginRequest,
)
from agent_os.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.auth.verification import (
    get_verification_service,
    RateLimitError,
    InvalidCodeError,
    ExpiredCodeError,
    TooManyAttemptsError,
    LockedError
)
from agent_os.auth.mailer import get_mailer

logger = logging.getLogger(__name__)

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
    token_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token.

    Validates the refresh token and issues a new access token.
    """
    # Verify refresh token
    token_info = verify_token(token_request.refresh_token, token_type="refresh")
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
    "/me",
    response_model=UserInfoWithStats,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"}
    }
)
async def get_current_user_info(
    workspace_id: Optional[uuid.UUID] = Query(None, description="Workspace ID for stats calculation"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user information.

    Returns user details including settings and optional garden statistics.
    If workspace_id is provided, also returns garden stats (total_notes, neural_connections, generated_insights).
    """
    from agent_os.garden.stats_service import GardenStatsService

    # Build base response
    response_data = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "settings": current_user.settings,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
    }

    # Add garden stats if workspace_id is provided
    if workspace_id:
        try:
            stats_service = GardenStatsService(db)
            stats = await stats_service.get_user_garden_stats(
                user_id=str(current_user.id),
                workspace_id=str(workspace_id)
            )
            response_data["stats"] = UserGardenStats(
                total_notes=stats["total_notes"],
                neural_connections=stats["neural_connections"],
                generated_insights=stats["generated_insights"]
            )
        except Exception as e:
            logger.warning(f"Failed to get garden stats: {e}")
            response_data["stats"] = None
    else:
        response_data["stats"] = None

    return UserInfoWithStats(**response_data)


@router.put(
    "/settings",
    response_model=UserInfo,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"}
    }
)
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    current_user = Depends(get_current_user),  # type: User
    db: AsyncSession = Depends(get_db)
):
    """Update current user settings.

    Updates user settings (daily_goal, theme, language, etc.).
    """
    # Update settings
    user = await crud.update_user_settings(
        db=db,
        user_id=current_user.id,
        settings=settings_update.settings
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Return updated user info
    return UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        settings=user.settings,
        is_active=user.is_active,
        created_at=user.created_at
    )


@router.post(
    "/send-code",
    response_model=SendCodeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid email"},
        429: {"model": RateLimitResponse, "description": "Rate limited"}
    }
)
async def send_verification_code(
    request: Request,
    code_data: SendCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send verification code to email.

    Generates a 6-digit code and sends it via email.
    Implements rate limiting to prevent abuse.
    """
    # Get verification service
    verification = get_verification_service()
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service unavailable"
        )

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    try:
        # Check if user exists (for login type)
        if code_data.code_type == "login":
            user = await crud.get_user_by_email(db, code_data.email)
            if not user:
                # Don't reveal if email exists
                return SendCodeResponse(
                    code="SUCCESS",
                    message="If the email exists, a verification code has been sent"
                )

        # Generate and store code
        code = verification.create_code(
            email=str(code_data.email),
            code_type=code_data.code_type,
            ip=client_ip
        )

        # Send email
        mailer = get_mailer()

        # Prepare template context
        from datetime import datetime
        context = {
            "code": code,
            "email": str(code_data.email),
            "year": datetime.now().year,
            "app_name": "AgentOS"
        }

        # Send using template
        result = mailer.send_template(
            to=str(code_data.email),
            subject=f"【AgentOS】您的验证码是：{code}",
            template_name="verification_code.html",
            context=context
        )

        if not result.success:
            logger.error(f"Failed to send verification email: {result.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email"
            )

        return SendCodeResponse(
            code="SUCCESS",
            message="Verification code sent",
            data={
                "expires_in": 300  # 5 minutes in seconds
            }
        )

    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded for {code_data.email}: {e.retry_after}s")
        return RateLimitResponse(
            code="RATE_LIMITED",
            message=f"发送过于频繁，请 {e.retry_after} 秒后重试",
            retry_after=e.retry_after
        )
    except LockedError as e:
        logger.warning(f"Account locked for {code_data.email}")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed attempts"
        )
    except Exception as e:
        logger.error(f"Error sending verification code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification code"
        )


@router.post(
    "/verify-code",
    response_model=VerifyCodeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or expired code"},
        403: {"model": ErrorResponse, "description": "Account locked"},
        429: {"model": RateLimitResponse, "description": "Too many attempts"}
    }
)
async def verify_code(
    verify_data: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify email verification code.

    Validates the provided code and consumes it (one-time use).
    Returns a temporary token for completing login flow.
    """
    # Get verification service
    verification = get_verification_service()
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service unavailable"
        )

    try:
        # Verify code
        is_valid = verification.verify_code(
            email=str(verify_data.email),
            code=verify_data.code,
            code_type=verify_data.code_type
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )

        # For login type, check if user exists and create token
        if verify_data.code_type == "login":
            user = await crud.get_user_by_email(db, verify_data.email)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Create temporary token for login completion
            temp_token = create_access_token(user_id=str(user.id))

            return VerifyCodeResponse(
                code="SUCCESS",
                message="Verification successful",
                data={
                    "token": temp_token,
                    "user_id": str(user.id)
                }
            )

        return VerifyCodeResponse(
            code="SUCCESS",
            message="Verification successful"
        )

    except ExpiredCodeError as e:
        logger.info(f"Expired code for {verify_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired"
        )

    except InvalidCodeError as e:
        logger.info(f"Invalid code for {verify_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except TooManyAttemptsError as e:
        logger.warning(f"Too many attempts for {verify_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )

    except LockedError as e:
        logger.warning(f"Account locked for {verify_data.email}")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked. Please try again later"
        )

    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify code"
        )


@router.post(
    "/register/email",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        409: {"model": ErrorResponse, "description": "Email already registered"},
        422: {"model": ErrorResponse, "description": "Invalid verification code"}
    }
)
async def register_with_email(
    request_data: EmailRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user using email verification code.

    This endpoint allows users to register using only their email and a verification code,
    without requiring a username. A username will be automatically generated from the email.
    """
    # Get verification service
    verification = get_verification_service()
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service unavailable"
        )

    try:
        # Verify the code first
        is_valid = verification.verify_code(
            email=str(request_data.email),
            code=request_data.code,
            code_type="login"
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid or expired verification code"
            )

        # Check if email already exists
        existing_email = await crud.get_user_by_email(db, request_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )

        # Generate username from email (use email prefix)
        # For example: user@example.com -> user_example_com
        email_prefix = request_data.email.split('@')[0]
        import re
        # Clean the username - only allow alphanumeric and underscore
        clean_username = re.sub(r'[^a-zA-Z0-9]', '_', email_prefix)
        base_username = clean_username

        # Ensure username is unique
        username = base_username
        counter = 1
        while await crud.get_user_by_username(db, username):
            username = f"{base_username}_{counter}"
            counter += 1

        # Create user
        user = await crud.create_user(
            db=db,
            username=username,
            email=str(request_data.email),
            password=request_data.password
        )

        logger.info(
            f"User registered successfully with email",
            extra={
                "user_id": str(user.id),
                "email": str(request_data.email),
                "username": username
            }
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

    except ExpiredCodeError as e:
        logger.info(f"Expired code for {request_data.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verification code has expired. Please request a new one."
        )

    except InvalidCodeError as e:
        logger.info(f"Invalid code for {request_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Error during email registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.post(
    "/login/email",
    response_model=Token,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Invalid code or user not found"},
        422: {"model": ErrorResponse, "description": "Invalid verification code"}
    }
)
async def login_with_email(
    request_data: EmailLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login using email verification code.

    This endpoint allows users to login using only their email and a verification code,
    without requiring a password. This is a passwordless authentication method.
    """
    # Get verification service
    verification = get_verification_service()
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service unavailable"
        )

    try:
        # Verify the code
        is_valid = verification.verify_code(
            email=str(request_data.email),
            code=request_data.code,
            code_type="login"
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired verification code"
            )

        # Check if user exists
        user = await crud.get_user_by_email(db, request_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found. Please register first."
            )

        # Update last login
        from datetime import datetime
        user.last_login_at = datetime.utcnow()
        await db.commit()

        logger.info(
            f"User logged in successfully with email",
            extra={
                "user_id": str(user.id),
                "email": str(request_data.email)
            }
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

    except ExpiredCodeError as e:
        logger.info(f"Expired code for {request_data.email}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verification code has expired. Please request a new one."
        )

    except InvalidCodeError as e:
        logger.info(f"Invalid code for {request_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Error during email login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to login"
        )
