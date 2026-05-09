"""Authentication schemas for API requests and responses."""

import uuid
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ============== Request Schemas ==============

class UserRegister(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=6, max_length=100, description="Password")


class UserLogin(BaseModel):
    """User login request."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str = Field(..., description="Refresh token")


class EmailRegisterRequest(BaseModel):
    """Email-based registration request."""
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=6, max_length=100, description="Password")
    code: str = Field(..., min_length=6, max_length=6, description="Email verification code")


class EmailLoginRequest(BaseModel):
    """Email-based login request."""
    email: EmailStr = Field(..., description="Email address")
    code: str = Field(..., min_length=6, max_length=6, description="Email verification code")


class UserSettingsUpdate(BaseModel):
    """User settings update request.

    User settings are stored as JSONB in the User model.
    This schema allows partial updates to the settings dict.
    """
    settings: dict[str, Any] = Field(..., description="User settings to update")


# ============== PRD10 §15 follow-up: dedicated read endpoints + password change ==============
#
# Engineer 1 (PRD10 §15.22) covers ``PATCH /api/v1/me`` (profile + nested
# settings deep-merge) via ``Prd10MeUpdateRequest`` further down in this
# file. The schemas below are deliberately scoped to the gaps Engineer 1's
# work does not cover:
#
# * a clean read-only ``GET /api/v1/me/preferences`` envelope that maps the
#   UserPreference fields stored under ``User.settings`` to PRD10 §5.2's
#   canonical shape with safe defaults so the SPA can hydrate the settings
#   panel without parsing free-form JSON.
# * ``POST /api/v1/me/password`` so the biz "修改密码" button has a real
#   backend instead of toast-only behaviour.


class Prd10PreferencesView(BaseModel):
    """Canonical read-only projection of PRD10 §5.2 ``UserPreference``.

    The legacy ``User.settings`` JSON column stores arbitrary keys; this
    response model picks the subset PRD10 §5.2 documents and applies safe
    defaults so the SPA can render toggles even on a brand new account.
    Naming aligns with the ``Prd10MeUpdateRequest`` whitelist (notably
    ``notification_channels``) so PATCH/GET are symmetric.
    """

    default_view: Literal["card", "list", "kanban"] = Field(default="card")
    default_input_mode: Literal["text", "voice", "auto"] = Field(default="text")
    theme: Literal["light", "dark", "system"] = Field(default="light")
    language: str = Field(default="zh-CN")
    locale: str = Field(default="zh-CN")
    timezone: str = Field(default="Asia/Shanghai")
    ai_response_style: Literal[
        "concise_structured", "concise", "detailed", "academic"
    ] = Field(default="concise_structured")
    ai_detail_level: Literal["brief", "balanced", "deep"] = Field(default="balanced")
    cite_knowledge_by_default: bool = Field(default=True)
    ai_auto_suggest: bool = Field(default=True)
    ai_streaming: bool = Field(default=True)
    default_ai_model: str = Field(default="auto")
    daily_report_time: str = Field(default="21:30")
    notification_enabled: bool = Field(default=True)
    auto_save: bool = Field(default=True)
    two_factor_enabled: bool = Field(default=False)
    notification_channels: dict[str, bool] = Field(
        default_factory=lambda: {
            "ai_done": True,
            "system_alert": True,
            "knowledge_link": True,
            "job_completed": True,
            "job_failed": True,
            "daily_insight": True,
            "weekly_insight": False,
        }
    )

    model_config = ConfigDict(extra="allow")


class Prd10PasswordUpdate(BaseModel):
    """``POST /api/v1/me/password`` request body."""

    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=6, max_length=200)

    model_config = ConfigDict(extra="forbid")


class Prd10PasswordUpdateResponse(BaseModel):
    """Response payload after a successful password rotation."""

    id: uuid.UUID
    updated_at: datetime
    rotated: bool = Field(default=True)


# ============== Response Schemas ==============

class Token(BaseModel):
    """Token response."""
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class UserBase(BaseModel):
    """Base user information."""
    id: uuid.UUID
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    """Complete user response with settings."""
    settings: dict[str, Any] = Field(default_factory=dict, description="User settings")
    full_name: str | None = None
    avatar_url: str | None = None


class UserInfo(BaseModel):
    """Current user info response."""
    id: uuid.UUID
    username: str
    email: EmailStr
    settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserGardenStats(BaseModel):
    """User's garden statistics for /auth/me endpoint."""
    total_notes: int = Field(..., description="Total number of active notes/cards")
    neural_connections: int = Field(..., description="Unique strong connections (undirected graph)")
    generated_insights: int = Field(..., description="Stable insights with level >= 2")


class UserInfoWithStats(BaseModel):
    """Current user info with garden statistics."""
    id: uuid.UUID
    username: str
    email: EmailStr
    settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    stats: UserGardenStats | None = Field(None, description="Garden statistics")

    model_config = ConfigDict(from_attributes=True)


class Prd10MeResponse(BaseModel):
    """PRD10 §5.1 canonical `/api/v1/me` shape.

    Avoids changing the User table schema by reading `role/locale/timezone/plan`
    from `User.settings` JSON with safe defaults. The legacy `/api/v1/auth/me`
    endpoint keeps `UserInfoWithStats` so existing clients don't break.
    """

    id: uuid.UUID
    name: str | None = Field(None, description="Display name (full_name or username)")
    username: str
    avatar_url: str | None = None
    email: EmailStr
    role: Literal["owner", "guest", "system"] = "owner"
    locale: str = Field(default="zh-CN")
    timezone: str = Field(default="Asia/Shanghai")
    plan: str = Field(default="free", description="free | pro | enterprise")
    is_active: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)
    stats: UserGardenStats | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSettings(BaseModel):
    """User settings schema."""
    theme: str = Field(default="light", description="UI theme preference")
    language: str = Field(default="en", description="Language preference")
    timezone: str = Field(default="UTC", description="Timezone setting")
    email_notifications: bool = Field(default=True, description="Email notification preference")
    desktop_notifications: bool = Field(default=True, description="Desktop notification preference")

    model_config = ConfigDict(from_attributes=True, extra="allow")


# ---- PRD10 §5.1 + §5.2  PATCH /api/v1/me  -----------------------------------

# Whitelist of settings keys that can be written via PATCH /me. Anything not in
# this set is silently dropped to prevent clients from injecting privileged
# fields like ``role`` or ``plan`` into the User.settings JSON.
PRD10_SETTINGS_WHITELIST = frozenset({
    "theme",
    "language",
    "locale",
    "timezone",
    "default_view",
    "default_input_mode",
    "ai_response_style",
    "ai_detail_level",
    "cite_knowledge_by_default",
    "ai_auto_suggest",
    "ai_streaming",
    "default_ai_model",
    "auto_save",
    "two_factor_enabled",
    "daily_report_time",
    "notification_enabled",
    "notification_channels",
    "permission_acl_mode",
    "permission_default_visibility",
    "permission_settings_opened_at",
    # §15.26 biz-prototype editProfile modal lets the user override the
    # plan-derived role label (Pro/Team/Free Plan 用户) with their own
    # text. Stored as a free-form display string on User.settings so it
    # doesn't have to be a real role grant.
    "display_role",
    # avatar / display-name are stored on User columns directly (not settings)
    # but allow toggle-style flags for future preferences here.
})

# Inside notification_channels, only these keys are allowed.
PRD10_NOTIFICATION_CHANNEL_KEYS = frozenset({
    "ai_done",
    "system_alert",
    "knowledge_link",
    "job_completed",
    "job_failed",
    "daily_insight",
    "weekly_insight",
})


class Prd10MeUpdateRequest(BaseModel):
    """PRD10 §5.1 / §5.2 partial update payload for ``PATCH /api/v1/me``.

    All fields are optional; only fields present in the request payload will
    be modified. ``settings`` is **deep-merged** into ``User.settings`` and
    filtered through ``PRD10_SETTINGS_WHITELIST`` so clients cannot promote
    themselves to ``role=system`` or ``plan=enterprise`` through this endpoint.

    Forbidden on purpose: ``email``, ``username``, ``role``, ``plan``,
    ``is_active``. Email change requires a separate verified flow; role/plan
    are admin-only.
    """

    name: str | None = Field(
        None,
        max_length=255,
        description="Display name; written to User.full_name.",
    )
    avatar_url: str | None = Field(
        None,
        max_length=500,
        description="Avatar URL.",
    )
    locale: str | None = Field(
        None,
        max_length=20,
        description="Convenience top-level locale (e.g. zh-CN). Mirrored into settings.locale.",
    )
    timezone: str | None = Field(
        None,
        max_length=64,
        description="Convenience top-level timezone (e.g. Asia/Shanghai). Mirrored into settings.timezone.",
    )
    settings: dict[str, Any] | None = Field(
        None,
        description=(
            "Partial UserPreference object (§5.2). Only keys in the PRD10 "
            "whitelist are persisted. ``notification_channels`` is itself a "
            "filtered dict."
        ),
    )

    model_config = ConfigDict(extra="forbid")


# ============== Error Schemas ==============

class ErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Application-specific error code")


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    detail: str = Field(default="Validation error", description="Error message")
    errors: dict[str, list[str]] = Field(default_factory=dict, description="Field errors")


# ============== Verification Code Schemas ==============

class SendCodeRequest(BaseModel):
    """Send verification code request."""
    email: EmailStr = Field(..., description="Email address to send code to")
    code_type: Literal["login", "bind", "reset"] = Field(
        default="login",
        description="Verification code type"
    )


class SendCodeResponse(BaseModel):
    """Send verification code response."""
    code: str = Field(default="SUCCESS", description="Response code")
    message: str = Field(..., description="Response message")
    data: dict | None = None


class VerifyCodeRequest(BaseModel):
    """Verify code request."""
    email: EmailStr = Field(..., description="Email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    code_type: Literal["login", "bind", "reset"] = Field(
        default="login",
        description="Verification code type"
    )


class VerifyCodeResponse(BaseModel):
    """Verify code response."""
    code: str = Field(..., description="Response code")
    message: str = Field(..., description="Response message")
    data: dict[str, Any] | None = None


class RateLimitResponse(BaseModel):
    """Rate limit error response."""
    code: str = Field(default="RATE_LIMITED", description="Error code")
    message: str = Field(..., description="Error message")
    retry_after: int = Field(..., description="Seconds until retry allowed")
