"""Security utilities - Password hashing, JWT, API Keys."""

import hashlib
import logging
import os
import secrets
import base64
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
import jwt

logger = logging.getLogger(__name__)

BCRYPT_SHA256_PREFIX = "$bcrypt-sha256$"


# ============================================================================
# Password Utilities
# ============================================================================

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt over a SHA-256 prehash.

    The SHA-256 prehash avoids bcrypt's 72-byte input limit while preserving
    bcrypt as the slow password hash. The stored format is
    ``$bcrypt-sha256$<bcrypt-hash>``.

    Args:
        password: Plain text password

    Returns:
        Bcrypt password hash. The raw password is never persisted.
    """
    digest = _bcrypt_sha256_digest(password)
    return BCRYPT_SHA256_PREFIX + bcrypt.hashpw(digest, bcrypt.gensalt()).decode("ascii")


def _bcrypt_sha256_digest(password: str) -> bytes:
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def _verify_legacy_sha256_password(plain_password: str, hashed_password: str) -> bool:
    """Verify legacy V1 ``salt$sha256`` hashes.

    Older PRD10 builds incorrectly stored passwords as ``salt$sha256`` even
    though the model contract said bcrypt. Keep a compatibility path so users
    can log in once and have the hash upgraded transparently.
    """

    try:
        salt, password_hash = hashed_password.split("$", 1)
    except (ValueError, AttributeError):
        return False
    if len(salt) != 32 or len(password_hash) != 64:
        return False
    salted_password = f"{salt}{plain_password}".encode()
    computed_hash = hashlib.sha256(salted_password).hexdigest()
    return secrets.compare_digest(computed_hash, password_hash)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database (format: salt$hash)

    Returns:
        True if password matches, False otherwise
    """
    if not hashed_password:
        return False

    if hashed_password.startswith(BCRYPT_SHA256_PREFIX):
        stored = hashed_password[len(BCRYPT_SHA256_PREFIX):].encode("ascii")
        try:
            return bcrypt.checkpw(_bcrypt_sha256_digest(plain_password), stored)
        except (ValueError, TypeError):
            return False

    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("ascii"))
        except (ValueError, TypeError):
            return False

    return _verify_legacy_sha256_password(plain_password, hashed_password)


def password_needs_rehash(hashed_password: str) -> bool:
    """Return whether a stored password should be upgraded on next login."""

    return not (hashed_password or "").startswith(BCRYPT_SHA256_PREFIX)


# ============================================================================
# JWT Utilities
# ============================================================================

def _get_env_int(*names: str, default: int) -> int:
    for name in names:
        raw = os.getenv(name)
        if raw is None or raw == "":
            continue
        try:
            return int(raw)
        except ValueError:
            logger.warning("Ignoring invalid integer env %s=%r", name, raw)
    return default


def _load_jwt_secret() -> str:
    secret = (os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "").strip()
    if secret:
        return secret

    generated = secrets.token_urlsafe(64)
    logger.warning(
        "JWT_SECRET_KEY/SECRET_KEY is not set; using an ephemeral development "
        "secret. Existing sessions will be invalid after process restart."
    )
    return generated


# JWT Configuration. Production/docker compose requires JWT_SECRET_KEY/SECRET_KEY;
# the fallback only keeps local tests and throwaway dev servers bootable.
SECRET_KEY = _load_jwt_secret()
ALGORITHM = (os.getenv("JWT_ALGORITHM") or "HS256").strip() or "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _get_env_int(
    "JWT_EXPIRE_MINUTES",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    default=30,
)
REFRESH_TOKEN_EXPIRE_DAYS = _get_env_int(
    "JWT_REFRESH_EXPIRE_DAYS",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    default=7,
)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None
) -> str:
    """Create a JWT access token.

    Args:
        data: Payload data (e.g., {"sub": user_id, "username": "..."})
        expires_delta: Optional custom expiration

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_urlsafe(16),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None
) -> str:
    """Create a JWT refresh token.

    Args:
        data: Payload data (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration

    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_urlsafe(16),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


def hash_token(token: str) -> str:
    """Hash a token for secure storage.

    Args:
        token: Token string

    Returns:
        SHA-256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


# ============================================================================
# API Key Utilities
# ============================================================================

def generate_api_key() -> str:
    """Generate a secure API key.

    Format: mydow_<random 32 chars>

    Returns:
        API key string
    """
    random_part = secrets.token_urlsafe(32)
    return f"mydow_{random_part}"


def get_api_key_prefix(api_key: str) -> str:
    """Extract the prefix from an API key for identification.

    Args:
        api_key: Full API key

    Returns:
        First 10 characters (mydow_xxx)
    """
    return api_key[:10]


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage.

    Args:
        api_key: API key string

    Returns:
        SHA-256 hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


# ============================================================================
# Permission Utilities
# ============================================================================

# Define permission format: resource:action
# Examples: "items:read", "items:write", "workspaces:admin"
DEFAULT_PERMISSIONS = {
    "admin": [
        "items:*",
        "workspaces:*",
        "users:*",
        "connections:*",
        "insights:*",
        "auth:*"
    ],
    "user": [
        "items:read",
        "items:write",
        "items:delete",
        "workspaces:read",
        "connections:read",
        "connections:write",
        "insights:read"
    ],
    "viewer": [
        "items:read",
        "workspaces:read",
        "connections:read",
        "insights:read"
    ]
}


def check_permission(
    user_permissions: list[str],
    required_permission: str
) -> bool:
    """Check if user has a required permission.

    Args:
        user_permissions: List of user's permissions
        required_permission: Permission to check (e.g., "items:write")

    Returns:
        True if user has permission, False otherwise
    """
    # Check for wildcard permissions
    for perm in user_permissions:
        # Exact match
        if perm == required_permission:
            return True

        # Wildcard resource (e.g., "items:*")
        if ":" in perm:
            resource, action = perm.split(":")
            if action == "*" and required_permission.startswith(f"{resource}:"):
                return True

        # Global wildcard
        if perm == "*":
            return True

    return False


def has_workspace_access(
    user_id: str,
    workspace_id: str,
    user_roles: list
) -> bool:
    """Check if user has access to a workspace.

    Args:
        user_id: User ID
        workspace_id: Workspace ID
        user_roles: List of user's roles with workspace context

    Returns:
        True if user has access, False otherwise
    """
    # Superuser has access to everything
    for role in user_roles:
        if role.get("is_superuser"):
            return True

    # Check workspace-specific roles
    for role in user_roles:
        role_workspace_id = role.get("workspace_id")
        if role_workspace_id == workspace_id or role_workspace_id is None:
            return True

    return False
