"""Authentication and Authorization Module - Stage 7.

Exports all authentication models and security utilities.
"""

from agent_os.auth.models import APIKey, AuditLog, Role, Session, User, UserRole
from agent_os.auth.security import (
    DEFAULT_PERMISSIONS,
    check_permission,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_api_key_prefix,
    get_password_hash,
    has_workspace_access,
    hash_api_key,
    hash_token,
    verify_password,
)

__all__ = [
    # Models
    "User",
    "APIKey",
    "Session",
    "Role",
    "UserRole",
    "AuditLog",
    # Password Utilities
    "verify_password",
    "get_password_hash",
    # JWT Utilities
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_token",
    # API Key Utilities
    "generate_api_key",
    "get_api_key_prefix",
    "hash_api_key",
    # Permission Utilities
    "check_permission",
    "has_workspace_access",
    "DEFAULT_PERMISSIONS"
]
