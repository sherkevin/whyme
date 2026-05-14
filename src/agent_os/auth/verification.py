"""Verification code service with the following features:

- Redis-based storage with TTL
- Rate limiting (email and IP)
- One-time use consumption
- Attempt counting and lockout
"""

import logging
import secrets
from typing import Literal, Optional

logger = logging.getLogger(__name__)


class VerificationCodeError(Exception):
    """Base exception for verification code errors."""
    pass


class RateLimitError(VerificationCodeError):
    """Raised when rate limit is exceeded."""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class InvalidCodeError(VerificationCodeError):
    """Raised when verification code is invalid."""
    pass


class ExpiredCodeError(VerificationCodeError):
    """Raised when verification code has expired."""
    pass


class TooManyAttemptsError(VerificationCodeError):
    """Raised when too many failed attempts."""
    pass


class LockedError(VerificationCodeError):
    """Raised when account is locked."""
    pass


class VerificationService:
    """Verification code management service."""

    # Redis key patterns
    KEY_CODE = "verify_code:{email}:{type}"  # TTL: 300s (5 minutes)
    KEY_RATE_LIMIT_EMAIL = "rate_limit:email:{email}"  # TTL: 60s
    KEY_RATE_LIMIT_IP = "rate_limit:ip:{ip}"  # TTL: 60s
    KEY_ATTEMPTS = "verify_attempts:{email}:{type}"  # TTL: 1800s (30 minutes)
    KEY_LOCKED = "verify_locked:{email}:{type}"  # TTL: 1800s (30 minutes)

    # Configuration
    CODE_LENGTH = 6
    CODE_EXPIRY_SECONDS = 300  # 5 minutes
    RATE_LIMIT_SECONDS = 60  # 60 seconds
    MAX_ATTEMPTS = 5
    LOCKOUT_SECONDS = 1800  # 30 minutes

    # Verification code types
    TYPE_LOGIN = "login"
    TYPE_BIND = "bind"
    TYPE_RESET = "reset"
    VALID_TYPES = {TYPE_LOGIN, TYPE_BIND, TYPE_RESET}

    def __init__(self, redis):
        """Initialize verification service.

        Args:
            redis: Redis client instance
        """
        self.redis = redis

    def generate_code(self) -> str:
        """Generate a 6-digit cryptographically secure verification code.

        Returns:
            6-digit numeric code as string
        """
        return f"{secrets.randbelow(10 ** self.CODE_LENGTH):0{self.CODE_LENGTH}d}"

    def check_rate_limit(self, email: str, ip: str) -> None:
        """Check if email/IP is rate limited.

        Args:
            email: User email address
            ip: User IP address

        Raises:
            RateLimitError: If rate limit exceeded
        """
        # Check email rate limit
        email_key = self.KEY_RATE_LIMIT_EMAIL.format(email=email)
        if self.redis.exists(email_key):
            ttl = self.redis.ttl(email_key)
            raise RateLimitError(retry_after=ttl)

        # Check IP rate limit
        ip_key = self.KEY_RATE_LIMIT_IP.format(ip=ip)
        if self.redis.exists(ip_key):
            ttl = self.redis.ttl(ip_key)
            raise RateLimitError(retry_after=ttl)

    def check_locked(self, email: str, code_type: str) -> None:
        """Check if email is locked due to too many failed attempts.

        Args:
            email: User email address
            code_type: Verification code type

        Raises:
            LockedError: If account is locked
        """
        lock_key = self.KEY_LOCKED.format(email=email, type=code_type)
        if self.redis.exists(lock_key):
            ttl = self.redis.ttl(lock_key)
            raise LockedError(f"Account locked for {ttl}s")

    def create_code(
        self,
        email: str,
        code_type: Literal["login", "bind", "reset"] = TYPE_LOGIN,
        ip: str | None = None
    ) -> str:
        """Create and store verification code.

        Args:
            email: User email address
            code_type: Type of verification code
            ip: User IP address (for rate limiting)

        Returns:
            Generated 6-digit code

        Raises:
            RateLimitError: If rate limit exceeded
            ValueError: If code_type is invalid
            LockedError: If account is locked
        """
        # Validate code type
        if code_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid code type: {code_type}")

        # Check rate limits
        self.check_rate_limit(email, ip)

        # Check if locked
        self.check_locked(email, code_type)

        # Generate code
        code = self.generate_code()

        # Store code in Redis with TTL
        code_key = self.KEY_CODE.format(email=email, type=code_type)
        self.redis.setex(code_key, self.CODE_EXPIRY_SECONDS, code)

        # Set rate limit locks (email and IP)
        email_limit_key = self.KEY_RATE_LIMIT_EMAIL.format(email=email)
        self.redis.setex(email_limit_key, self.RATE_LIMIT_SECONDS, "1")

        if ip:
            ip_limit_key = self.KEY_RATE_LIMIT_IP.format(ip=ip)
            self.redis.setex(ip_limit_key, self.RATE_LIMIT_SECONDS, "1")

        logger.info(
            f"Verification code created for {email}",
            extra={
                "email": email,
                "type": code_type,
                "ip": ip
            }
        )

        return code

    def verify_code(
        self,
        email: str,
        code: str,
        code_type: Literal["login", "bind", "reset"] = TYPE_LOGIN
    ) -> bool:
        """Verify and consume verification code.

        Args:
            email: User email address
            code: User-provided verification code
            code_type: Type of verification code

        Returns:
            True if code is valid

        Raises:
            InvalidCodeError: If code is incorrect
            ExpiredCodeError: If code has expired
            TooManyAttemptsError: If too many failed attempts
            LockedError: If account is locked
        """
        # Check if locked first
        self.check_locked(email, code_type)

        # Get stored code
        code_key = self.KEY_CODE.format(email=email, type=code_type)
        stored_code = self.redis.get(code_key)

        if not stored_code:
            # Code doesn't exist (expired or never created)
            raise ExpiredCodeError("Verification code has expired")

        if stored_code != code:
            # Incorrect code - increment attempt counter
            attempts_key = self.KEY_ATTEMPTS.format(email=email, type=code_type)
            attempts = int(self.redis.incr(attempts_key) or 0)

            # Set TTL on first attempt
            if attempts == 1:
                self.redis.expire(attempts_key, self.LOCKOUT_SECONDS)

            # Check if too many attempts
            if attempts >= self.MAX_ATTEMPTS:
                # Lock the account
                lock_key = self.KEY_LOCKED.format(email=email, type=code_type)
                self.redis.setex(lock_key, self.LOCKOUT_SECONDS, "1")
                raise TooManyAttemptsError(f"Too many failed attempts ({attempts}/{self.MAX_ATTEMPTS})")

            # Calculate remaining attempts
            remaining = self.MAX_ATTEMPTS - attempts

            logger.info(
                f"Invalid code for {email}, {remaining} attempts remaining"
            )

            raise InvalidCodeError(f"Invalid code, {remaining} attempts remaining")

        # Code is correct - consume it (delete from Redis)
        self.redis.delete(code_key)

        # Clear attempt counter and locked status
        attempts_key = self.KEY_ATTEMPTS.format(email=email, type=code_type)
        self.redis.delete(attempts_key)

        lock_key = self.KEY_LOCKED.format(email=email, type=code_type)
        self.redis.delete(lock_key)

        logger.info(
            f"Verification code consumed for {email}",
            extra={
                "email": email,
                "type": code_type
            }
            )

        return True

    def get_remaining_attempts(
        self,
        email: str,
        code_type: Literal["login", "bind", "reset"] = TYPE_LOGIN
    ) -> int:
        """Get remaining verification attempts.

        Args:
            email: User email address
            code_type: Type of verification code

        Returns:
            Number of remaining attempts (0 if locked)
        """
        # Check if locked
        lock_key = self.KEY_LOCKED.format(email=email, type=code_type)
        if self.redis.exists(lock_key):
            return 0

        # Get attempt count
        attempts_key = self.KEY_ATTEMPTS.format(email=email, type=code_type)
        attempts = int(self.redis.get(attempts_key) or 0)

        return max(0, self.MAX_ATTEMPTS - attempts)


def get_verification_service() -> VerificationService | None:
    """Get verification service instance.

    Returns:
        VerificationService instance or None if Redis not available
    """
    try:
        from agent_os.db.cache import get_redis
        redis = get_redis()
        if redis:
            return VerificationService(redis)
    except Exception as e:
            logger.warning(f"Failed to initialize verification service: {e}")
    return None
