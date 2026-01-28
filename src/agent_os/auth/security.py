"""Password hashing and verification utilities."""

from passlib.context import CryptContext

# Password hashing context
# Uses argon2 algorithm (more secure than bcrypt, no length limit)
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using argon2.

    Args:
        password: Plain text password

    Returns:
        Hashed password (starts with $argon2...)
    """
    return pwd_context.hash(password)
