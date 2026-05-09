"""Authentication API router."""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth import crud
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from agent_os.auth.mailer import get_mailer
from agent_os.auth.models import User
from agent_os.auth.schema import (
    PRD10_NOTIFICATION_CHANNEL_KEYS,
    PRD10_SETTINGS_WHITELIST,
    EmailLoginRequest,
    EmailRegisterRequest,
    ErrorResponse,
    Prd10MeResponse,
    Prd10MeUpdateRequest,
    Prd10PasswordUpdate,
    Prd10PasswordUpdateResponse,
    Prd10PreferencesView,
    RateLimitResponse,
    RefreshTokenRequest,
    SendCodeRequest,
    SendCodeResponse,
    Token,
    UserGardenStats,
    UserInfo,
    UserInfoWithStats,
    UserLogin,
    UserRegister,
    UserSettingsUpdate,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from agent_os.auth.verification import (
    ExpiredCodeError,
    InvalidCodeError,
    LockedError,
    RateLimitError,
    TooManyAttemptsError,
    get_verification_service,
)
from agent_os.db.base import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
me_router = APIRouter(prefix="/api/v1", tags=["User"])
demo_router = APIRouter(prefix="/api/v1/demo", tags=["Demo"])


_DEMO_EMAIL_DEFAULT = "demo@mydow.example"
_DEMO_USERNAME_DEFAULT = "demo"
_DEMO_PASSWORD_DEFAULT = "demo123"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _request_device_payload(request: Request) -> dict:
    """Return a durable current-session device summary for account security."""

    user_agent = (request.headers.get("user-agent") or "Unknown browser").strip()
    platform = "Windows" if "Windows" in user_agent else "macOS" if "Mac" in user_agent else "Linux" if "Linux" in user_agent else "Device"
    browser = "Chrome" if "Chrome" in user_agent else "Edge" if "Edg" in user_agent else "Safari" if "Safari" in user_agent else "Browser"
    host = request.client.host if request.client else "unknown"
    return {
        "id": hashlib.sha256(f"{host}|{user_agent}".encode("utf-8")).hexdigest()[:16],
        "label": f"{platform} · {browser}",
        "ip": host,
        "user_agent": user_agent[:240],
        "last_seen_at": _iso_now(),
        "current": True,
    }


def _project_account_security(user: User, request: Request | None = None) -> dict:
    settings = dict(user.settings or {})
    devices = list(settings.get("login_devices") or [])
    if request is not None:
        current = _request_device_payload(request)
        devices = [d for d in devices if d.get("id") != current["id"]]
        devices.insert(0, current)
    return {
        "email": user.email,
        "email_verified": bool(settings.get("email_verified", False)),
        "email_verification_requested_at": settings.get("email_verification_requested_at"),
        "email_verification_delivery": settings.get("email_verification_delivery"),
        "two_factor_enabled": bool(settings.get("two_factor_enabled", False)),
        "password_rotated_at": settings.get("password_rotated_at"),
        "last_security_refresh_at": settings.get("last_security_refresh_at"),
        "login_devices": devices[:8],
    }


def _is_demo_mode_enabled() -> bool:
    """Demo mode requires opt-in via ``AGENTOS_DEMO_MODE``.

    Default off so production deployments cannot accidentally hand out a
    demo session.
    """

    import os

    raw = (os.getenv("AGENTOS_DEMO_MODE") or "").strip().lower()
    return raw in {"1", "on", "true", "enabled", "yes"}


@demo_router.post(
    "/login",
    responses={
        403: {"model": ErrorResponse, "description": "Demo mode disabled"}
    },
)
async def demo_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Single-click login for the static demo bundle.

    When ``AGENTOS_DEMO_MODE=on`` the endpoint guarantees a working
    ``demo@mydow.example`` user (creating it lazily) and returns a fresh
    access/refresh token pair so ``/mydow/biz/`` can boot without a manual
    register/login flow.

    PRD10 §15.28 — response is wrapped in the standard envelope
    ``{success: true, data: {access_token, refresh_token, token_type,
    expires_in}, request_id}`` to match every other PRD10 endpoint. The
    bridge accepts both the envelope and the historical top-level shape so
    legacy embed clients keep booting during the rollout window.
    """
    from agent_os.common.errors import ApiErrorCode
    from agent_os.common.response import error_json_response, success_response

    if not _is_demo_mode_enabled():
        return error_json_response(
            ApiErrorCode.FORBIDDEN,
            "Demo mode is disabled (set AGENTOS_DEMO_MODE=on to enable)",
            request=request,
        )

    user = await crud.authenticate_user(
        db=db,
        username=_DEMO_EMAIL_DEFAULT,
        password=_DEMO_PASSWORD_DEFAULT,
    )

    if user is None:
        # Lazy create on first hit so a fresh dev DB still works without
        # running the seed script up front.
        user = await crud.create_user(
            db=db,
            username=_DEMO_USERNAME_DEFAULT,
            email=_DEMO_EMAIL_DEFAULT,
            password=_DEMO_PASSWORD_DEFAULT,
        )

    access_token = create_access_token(user_id=user.id)
    refresh_token = create_refresh_token(user_id=user.id)

    token_payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 30 * 60,
    }
    return success_response(token_payload, request=request)


@demo_router.get("/status")
async def demo_status(request: Request):
    """Lightweight probe used by the frontend to decide whether to
    auto-call ``/api/v1/demo/login``.

    PRD10 §15.28 — wrapped in the standard envelope to align with every
    other PRD10 endpoint. The bridge accepts both shapes during rollout.
    """
    from agent_os.common.response import success_response

    enabled = _is_demo_mode_enabled()
    return success_response(
        {
            "enabled": enabled,
            "email": _DEMO_EMAIL_DEFAULT if enabled else None,
        },
        request=request,
    )


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
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login with username/email and password using JSON body."""
    # Authenticate user
    user = await crud.authenticate_user(
        db=db,
        username=user_data.username,
        password=user_data.password
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
    workspace_id: uuid.UUID | None = Query(None, description="Workspace ID for stats calculation"),
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


@me_router.get(
    "/me",
    response_model=Prd10MeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"}
    },
)
async def get_prd10_me(
    workspace_id: uuid.UUID | None = Query(None, description="Workspace ID for stats calculation"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD10 §4.1 / §5.1 canonical current-user endpoint.

    Returns the exact PRD10 §5.1 shape:
    ``{id, name, avatar_url, email, role, locale, timezone, plan,
    created_at, updated_at}``. ``role/locale/timezone/plan`` are read from
    ``User.settings`` JSON with safe defaults so we don't have to migrate the
    User table schema. Garden stats remain optional and only populated when
    ``workspace_id`` is provided.

    The older ``/api/v1/auth/me`` keeps the legacy ``UserInfoWithStats`` shape
    untouched.
    """

    settings = current_user.settings or {}
    role = settings.get("role")
    if role not in ("owner", "guest", "system"):
        role = "owner"

    locale = settings.get("locale") or "zh-CN"
    timezone = settings.get("timezone") or "Asia/Shanghai"
    plan = settings.get("plan") or "free"

    stats: UserGardenStats | None = None
    if workspace_id:
        try:
            from agent_os.garden.stats_service import GardenStatsService

            stats_service = GardenStatsService(db)
            raw = await stats_service.get_user_garden_stats(
                user_id=str(current_user.id),
                workspace_id=str(workspace_id),
            )
            stats = UserGardenStats(
                total_notes=raw["total_notes"],
                neural_connections=raw["neural_connections"],
                generated_insights=raw["generated_insights"],
            )
        except Exception as exc:
            logger.warning(f"PRD10 /me garden stats failed: {exc}")
            stats = None

    return Prd10MeResponse(
        id=current_user.id,
        name=current_user.full_name or current_user.username,
        username=current_user.username,
        avatar_url=current_user.avatar_url,
        email=current_user.email,
        role=role,
        locale=locale,
        timezone=timezone,
        plan=plan,
        is_active=current_user.is_active,
        settings=dict(settings),
        stats=stats,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


def _filter_prd10_settings_patch(raw: dict) -> dict:
    """Drop any key not in PRD10_SETTINGS_WHITELIST and sub-filter
    ``notification_channels`` to PRD10_NOTIFICATION_CHANNEL_KEYS only.

    Silently ignored keys (most importantly ``role``, ``plan``, ``is_active``)
    cannot be elevated through the public ``PATCH /api/v1/me`` endpoint.
    """
    if not raw:
        return {}
    cleaned: dict = {}
    for key, value in raw.items():
        if key not in PRD10_SETTINGS_WHITELIST:
            continue
        if key == "notification_channels" and isinstance(value, dict):
            cleaned[key] = {
                k: bool(v)
                for k, v in value.items()
                if k in PRD10_NOTIFICATION_CHANNEL_KEYS
            }
            continue
        cleaned[key] = value
    return cleaned


@me_router.patch(
    "/me",
    response_model=Prd10MeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def patch_prd10_me(
    payload: Prd10MeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD10 §5.1 + §5.2 partial profile update.

    Allows the authenticated user to update their **own** profile and
    UserPreference fields. The request body is parsed by
    :class:`Prd10MeUpdateRequest`; ``settings`` is filtered through
    :data:`PRD10_SETTINGS_WHITELIST` so keys like ``role`` / ``plan`` cannot
    be elevated through this endpoint. Any unknown top-level field is rejected
    by Pydantic (``extra="forbid"``).

    The response is the same :class:`Prd10MeResponse` shape returned by
    ``GET /api/v1/me`` so the frontend can replace its cached profile state
    in one round-trip.
    """

    # Build deep-mergeable settings patch with mirrored top-level locale/timezone.
    settings_patch: dict = {}
    if payload.settings is not None:
        settings_patch.update(_filter_prd10_settings_patch(payload.settings))
    if payload.locale is not None:
        settings_patch["locale"] = payload.locale
    if payload.timezone is not None:
        settings_patch["timezone"] = payload.timezone

    user = await crud.update_prd10_me(
        db=db,
        user_id=current_user.id,
        name=payload.name,
        avatar_url=payload.avatar_url,
        settings_patch=settings_patch or None,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    settings = user.settings or {}
    role = settings.get("role")
    if role not in ("owner", "guest", "system"):
        role = "owner"
    locale = settings.get("locale") or "zh-CN"
    timezone = settings.get("timezone") or "Asia/Shanghai"
    plan = settings.get("plan") or "free"

    return Prd10MeResponse(
        id=user.id,
        name=user.full_name or user.username,
        username=user.username,
        avatar_url=user.avatar_url,
        email=user.email,
        role=role,
        locale=locale,
        timezone=timezone,
        plan=plan,
        is_active=user.is_active,
        settings=dict(settings),
        stats=None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@me_router.patch(
    "/me/preferences",
    response_model=Prd10MeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def patch_prd10_me_preferences(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PRD10 §5.2 / §15.22 — convenience alias for ``PATCH /api/v1/me``.

    Accepts a flat JSON body of preference flags (``theme``, ``auto_save``,
    ``language``, ``timezone``, ``default_input_mode``, ``default_ai_model``,
    ``two_factor_enabled``, ``notification_enabled``, ``notification_channels``)
    and shallow-merges them into ``User.settings`` after running the same
    PRD10 whitelist filter as ``PATCH /me``.

    This lets the biz prototype settings page send only what changed (e.g.
    ``{theme: "dark"}``) without having to wrap the body in
    ``{settings: {...}}``. Privileged keys (``role`` / ``plan`` / ``is_active``)
    are still silently dropped by the whitelist.

    Returns the same :class:`Prd10MeResponse` shape as ``GET /api/v1/me`` so
    the frontend can replace its cached profile state in one round-trip.
    """

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload must be a JSON object",
        )

    settings_patch = _filter_prd10_settings_patch(payload)

    user = await crud.update_prd10_me(
        db=db,
        user_id=current_user.id,
        settings_patch=settings_patch or None,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    settings = user.settings or {}
    role = settings.get("role")
    if role not in ("owner", "guest", "system"):
        role = "owner"
    locale = settings.get("locale") or "zh-CN"
    timezone = settings.get("timezone") or "Asia/Shanghai"
    plan = settings.get("plan") or "free"

    return Prd10MeResponse(
        id=user.id,
        name=user.full_name or user.username,
        username=user.username,
        avatar_url=user.avatar_url,
        email=user.email,
        role=role,
        locale=locale,
        timezone=timezone,
        plan=plan,
        is_active=user.is_active,
        settings=dict(settings),
        stats=None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


_DEFAULT_NOTIFICATION_CHANNELS: dict[str, bool] = {
    "ai_done": True,
    "system_alert": True,
    "knowledge_link": True,
    "job_completed": True,
    "job_failed": True,
    "daily_insight": True,
    "weekly_insight": False,
}


def _project_prd10_preferences(settings: dict | None) -> Prd10PreferencesView:
    """Project ``User.settings`` JSON into PRD10 §5.2 ``UserPreference`` shape.

    Applies safe defaults for keys that have never been written so the SPA
    can hydrate the settings panel even on a brand-new account. Unknown
    keys persist on ``Prd10PreferencesView`` (``extra='allow'``) so the
    forward-compat contract holds.
    """

    raw = dict(settings or {})
    channels_raw = raw.get("notification_channels") or {}
    if not isinstance(channels_raw, dict):
        channels_raw = {}
    merged_channels = {**_DEFAULT_NOTIFICATION_CHANNELS, **{
        k: bool(v) for k, v in channels_raw.items()
        if k in PRD10_NOTIFICATION_CHANNEL_KEYS
    }}

    payload: dict = {
        "default_view": raw.get("default_view") or "card",
        "default_input_mode": raw.get("default_input_mode") or "text",
        "theme": raw.get("theme") or "light",
        "language": raw.get("language") or "zh-CN",
        "locale": raw.get("locale") or "zh-CN",
        "timezone": raw.get("timezone") or "Asia/Shanghai",
        "ai_response_style": raw.get("ai_response_style") or "concise_structured",
        "ai_detail_level": raw.get("ai_detail_level") or "balanced",
        "cite_knowledge_by_default": bool(
            raw.get("cite_knowledge_by_default", True)
        ),
        "ai_auto_suggest": bool(raw.get("ai_auto_suggest", True)),
        "ai_streaming": bool(raw.get("ai_streaming", True)),
        "default_ai_model": raw.get("default_ai_model") or "auto",
        "daily_report_time": raw.get("daily_report_time") or "21:30",
        "notification_enabled": bool(raw.get("notification_enabled", True)),
        "auto_save": bool(raw.get("auto_save", True)),
        "two_factor_enabled": bool(raw.get("two_factor_enabled", False)),
        "notification_channels": merged_channels,
    }
    return Prd10PreferencesView(**payload)


@me_router.get(
    "/me/preferences",
    response_model=Prd10PreferencesView,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_prd10_me_preferences(
    current_user: User = Depends(get_current_user),
):
    """PRD10 §5.2 — read-only projection of the current user's preferences.

    Returns the canonical ``UserPreference`` shape with safe defaults applied
    for keys that have never been written to ``User.settings``. The SPA
    settings page reads from this endpoint to hydrate toggles / segmented
    controls without parsing free-form JSON. Use ``PATCH /api/v1/me`` or
    ``PATCH /api/v1/me/preferences`` to mutate.
    """

    return _project_prd10_preferences(current_user.settings)


@me_router.get(
    "/me/security",
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)
async def get_prd10_me_security(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the real persisted account-security state for the user."""

    current_device = _request_device_payload(request)
    existing = list((current_user.settings or {}).get("login_devices") or [])
    if not any(d.get("id") == current_device["id"] for d in existing):
        await crud.update_prd10_me(
            db=db,
            user_id=current_user.id,
            settings_patch={
                "login_devices": [current_device, *existing][:8],
                "last_security_refresh_at": current_device["last_seen_at"],
            },
        )
        current_user = await crud.get_user_by_id(db, current_user.id) or current_user

    return _project_account_security(current_user, request)


@me_router.post(
    "/me/security/email-verification",
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)
async def request_prd10_email_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a real verification request and delivery record for this email.

    If SMTP/Redis are configured, the endpoint sends through the production
    verification-code pipeline. In local/demo deployments without SMTP, it
    still persists a one-time local-outbox request instead of pretending a
    message was sent.
    """

    now = _iso_now()
    delivery = "local_outbox"
    request_id = str(uuid.uuid4())
    token_hash = hashlib.sha256(secrets.token_urlsafe(32).encode("utf-8")).hexdigest()
    error: str | None = None

    verification = get_verification_service()
    if verification is not None:
        try:
            code = verification.create_code(
                email=str(current_user.email),
                code_type="bind",
                ip=request.client.host if request.client else "unknown",
            )
            mailer = get_mailer()
            result = mailer.send_template(
                to=str(current_user.email),
                subject=f"[Mydow] 邮箱验证码：{code}",
                template_name="verification_code.html",
                context={
                    "code": code,
                    "email": str(current_user.email),
                    "year": datetime.now().year,
                    "app_name": "Mydow",
                },
            )
            if result.success:
                delivery = "smtp"
            else:
                error = result.error
        except Exception as exc:  # pragma: no cover - depends on local SMTP/Redis
            error = str(exc)

    user = await crud.update_prd10_me(
        db=db,
        user_id=current_user.id,
        settings_patch={
            "email_verified": False,
            "email_verification_requested_at": now,
            "email_verification_delivery": delivery,
            "email_verification_request_id": request_id,
            "email_verification_token_hash": token_hash,
            "email_verification_error": error,
        },
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    payload = _project_account_security(user, request)
    payload["request_id"] = request_id
    payload["delivery_error"] = error
    return payload


@me_router.post(
    "/me/security/devices/refresh",
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)
async def refresh_prd10_login_devices(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist and return the current-login device list."""

    current_device = _request_device_payload(request)
    existing = list((current_user.settings or {}).get("login_devices") or [])
    devices = [d for d in existing if d.get("id") != current_device["id"]]
    devices.insert(0, current_device)
    user = await crud.update_prd10_me(
        db=db,
        user_id=current_user.id,
        settings_patch={
            "login_devices": devices[:8],
            "last_security_refresh_at": current_device["last_seen_at"],
        },
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _project_account_security(user, request)


@me_router.post(
    "/me/password",
    response_model=Prd10PasswordUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid current password or same as new"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def change_prd10_me_password(
    payload: Prd10PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the authenticated user's password (PRD10 §15.18 security tab).

    Requires the current password to be provided so a stolen access token
    cannot silently lock the legitimate owner out. The new password must
    differ from the current one. On success the password hash is rotated in
    place; existing JWTs remain valid until they expire (rotation of all
    refresh tokens is tracked separately in §12.2 rate-limit / session work).
    """

    try:
        user = await crud.update_user_password(
            db=db,
            user_id=current_user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "current_password_invalid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        if code == "same_password":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must differ from the current password",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user = await crud.update_prd10_me(
        db=db,
        user_id=current_user.id,
        settings_patch={"password_rotated_at": _iso_now()},
    ) or user

    return Prd10PasswordUpdateResponse(
        id=user.id,
        updated_at=user.updated_at,
        rotated=True,
    )


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
    except LockedError:
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

    except ExpiredCodeError:
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

    except LockedError:
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
            "User registered successfully with email",
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

    except ExpiredCodeError:
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
            "User logged in successfully with email",
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

    except ExpiredCodeError:
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


# ---------------------------------------------------------------------------
# v1.4 §3.1 — POST /api/v1/auth/logout
#
# JWT-based stateless logout. The token is signed and unforgeable, so V1
# returns success and lets the client drop the token. Future V2 can add
# a server-side denylist for instant revocation; the contract stays the
# same. Wired for v1.4 sidebar / settings 退出登录 button.
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_200_OK, tags=["Authentication"])
async def auth_logout(request: Request):
    """v1.4 §3.1 — confirm logout.

    Auth optional: we accept the call whether or not the caller passes a
    Bearer token (so a stale tab can call logout while the access token is
    expired). The browser is responsible for dropping ``mydow_v14_token`` /
    ``mydow_token`` from ``localStorage``; subsequent ``/me`` calls return
    401 and the SPA / biz prototype shows the auth overlay or demo CTA.
    """

    return {"success": True, "message": "logged out", "request_id": getattr(request.state, "request_id", None)}
