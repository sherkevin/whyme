"""
User authentication and management module for AgentOS.
"""
import os
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
import jwt

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# File-based user storage (in production, use a real database)
USERS_FILE = "data/users.json"

# Security scheme
security = HTTPBearer()


@dataclass
class User:
    """User model."""
    id: str
    username: str
    email: str
    created_at: str
    is_guest: bool = False


@dataclass
class UserCreate:
    """User registration model."""
    username: str
    email: str
    password: str


@dataclass
class UserInDB:
    """User with password hash (internal only)."""
    id: str
    username: str
    email: str
    password_hash: str
    created_at: str
    is_guest: bool = False

    def to_user(self) -> User:
        """Convert to User (without password)."""
        return User(
            id=self.id,
            username=self.username,
            email=self.email,
            created_at=self.created_at,
            is_guest=self.is_guest
        )


class UserManager:
    """Manage user accounts and authentication."""

    def __init__(self, users_file: str = USERS_FILE):
        self.users_file = users_file
        self._ensure_data_dir()
        self._load_users()

    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        os.makedirs(os.path.dirname(self.users_file) if os.path.dirname(self.users_file) else "data", exist_ok=True)

    def _load_users(self):
        """Load users from file."""
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}

    def _save_users(self):
        """Save users to file."""
        self._ensure_data_dir()
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt. Truncates to 72 bytes if needed."""
        # Truncate password if too long for bcrypt (max 72 bytes)
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password using bcrypt."""
        # Truncate password if too long for bcrypt (max 72 bytes)
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))

    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get user by username."""
        user_data = self.users.get(username)
        if user_data:
            return UserInDB(**user_data)
        return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        for user_data in self.users.values():
            if user_data.get('id') == user_id:
                return User(**{k: v for k, v in user_data.items() if k != 'password_hash'})
        return None

    def create_user(self, user_create: UserCreate) -> User:
        """Create a new user."""
        # Check if username already exists
        if user_create.username in self.users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )

        # Check if email already exists
        for user_data in self.users.values():
            if user_data.get('email') == user_create.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

        # Create user
        user_id = hashlib.sha256(user_create.username.encode()).hexdigest()[:16]
        user = UserInDB(
            id=user_id,
            username=user_create.username,
            email=user_create.email,
            password_hash=self._hash_password(user_create.password),
            created_at=datetime.utcnow().isoformat(),
            is_guest=False
        )

        # Save user
        self.users[user_create.username] = asdict(user)
        self._save_users()

        # Return user without password
        return User(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at
        )

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        user = self.get_user(username)
        if not user:
            return None

        if not self._verify_password(password, user.password_hash):
            return None

        # Return user without password
        return User(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at
        )

    def create_access_token(self, user: User) -> str:
        """Create JWT access token."""
        to_encode = {
            "sub": user.id,
            "username": user.username,
            "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        }
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[User]:
        """Verify JWT token and return user."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = self.get_user_by_id(user_id)
                return user
        except jwt.PyJWTError:
            pass
        return None


# Global user manager instance
user_manager = UserManager()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User:
    """Get current user from JWT token."""
    token = credentials.credentials

    # Allow guest access if no token
    if not token:
        return User(
            id="guest",
            username="Guest",
            email="guest@agentos.local",
            created_at=datetime.utcnow().isoformat(),
            is_guest=True
        )

    user = user_manager.verify_token(token)
    if user:
        return user

    # If token is invalid, return guest
    return User(
        id="guest",
        username="Guest",
        email="guest@agentos.local",
        created_at=datetime.utcnow().isoformat(),
        is_guest=True
    )


def get_user_manager() -> UserManager:
    """Get user manager instance."""
    return user_manager
