"""Authentication and Authorization Module - Stage 7.

Exports all authentication models and security utilities.
"""

from agent_os.auth.models import (
    User,
    APIKey,
    Session,
    Role,
    UserRole,
    AuditLog
)
from agent_os.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    generate_api_key,
    get_api_key_prefix,
    hash_api_key,
    check_permission,
    has_workspace_access,
    DEFAULT_PERMISSIONS
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
