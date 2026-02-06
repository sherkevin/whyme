"""Security utilities - Password hashing, JWT, API Keys."""

import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext

# Password hashing context
# Uses bcrypt algorithm (widely supported, good security)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ============================================================================
# Password Utilities
# ============================================================================

def get_password_hash(password: str) -> str:
    """Hash a password using SHA-256 + salt.

    Args:
        password: Plain text password

    Returns:
        Hashed password with salt (format: salt$hash)
    """
    # Generate random salt
    salt = secrets.token_hex(16)

    # Hash password with salt
    salted_password = f"{salt}{password}".encode('utf-8')
    password_hash = hashlib.sha256(salted_password).hexdigest()

    # Return salt$hash format for verification
    return f"{salt}${password_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database (format: salt$hash)

    Returns:
        True if password matches, False otherwise
    """
    try:
        # Split salt and hash
        salt, password_hash = hashed_password.split('$', 1)

        # Hash the plain password with the same salt
        salted_password = f"{salt}{plain_password}".encode('utf-8')
        computed_hash = hashlib.sha256(salted_password).hexdigest()

        # Compare hashes
        return computed_hash == password_hash
    except (ValueError, AttributeError):
        return False


# ============================================================================
# JWT Utilities
# ============================================================================

# JWT Configuration
SECRET_KEY = secrets.token_urlsafe(64)  # Should be from env in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
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
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
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
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
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
