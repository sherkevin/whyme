"""Authentication schemas for API requests and responses."""

import uuid
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Dict, Any, Literal
from datetime import datetime


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
    settings: Dict[str, Any] = Field(..., description="User settings to update")


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
    settings: Dict[str, Any] = Field(default_factory=dict, description="User settings")
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserInfo(BaseModel):
    """Current user info response."""
    id: uuid.UUID
    username: str
    email: EmailStr
    settings: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSettings(BaseModel):
    """User settings schema."""
    theme: str = Field(default="light", description="UI theme preference")
    language: str = Field(default="en", description="Language preference")
    timezone: str = Field(default="UTC", description="Timezone setting")
    email_notifications: bool = Field(default=True, description="Email notification preference")
    desktop_notifications: bool = Field(default=True, description="Desktop notification preference")

    model_config = ConfigDict(from_attributes=True, extra="allow")


# ============== Error Schemas ==============

class ErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    detail: str = Field(default="Validation error", description="Error message")
    errors: Dict[str, list[str]] = Field(default_factory=dict, description="Field errors")


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
    data: Optional[dict] = None


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
    data: Optional[Dict[str, Any]] = None


class RateLimitResponse(BaseModel):
    """Rate limit error response."""
    code: str = Field(default="RATE_LIMITED", description="Error code")
    message: str = Field(..., description="Error message")
    retry_after: int = Field(..., description="Seconds until retry allowed")
