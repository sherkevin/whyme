"""Authentication schemas for API requests and responses."""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
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


class UserSettingsUpdate(BaseModel):
    """User settings update request."""
    daily_goal: Optional[int] = Field(None, ge=1, le=100, description="Daily card goal")
    theme: Optional[str] = Field(None, pattern="^(light|dark)$", description="UI theme")
    language: Optional[str] = Field(None, min_length=2, max_length=10, description="Language code")


# ============== Response Schemas ==============

class Token(BaseModel):
    """Token response."""
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class UserBase(BaseModel):
    """Base user information."""
    id: int
    username: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class UserSettings(BaseModel):
    """User settings information."""
    daily_goal: int = Field(default=10, description="Daily card goal")
    theme: str = Field(default="light", description="UI theme")
    language: str = Field(default="zh", description="Language code")

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    """Complete user response with settings."""
    settings: Optional[UserSettings] = None


class UserInfo(BaseModel):
    """Current user info response."""
    id: int
    username: str
    email: EmailStr
    daily_goal: int
    theme: str
    language: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Error Schemas ==============

class ErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    detail: str = Field(default="Validation error", description="Error message")
    errors: dict[str, list[str]] = Field(default_factory=dict, description="Field errors")
