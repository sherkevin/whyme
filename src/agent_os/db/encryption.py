"""Field-level encryption for sensitive data.

Uses Fernet symmetric encryption from cryptography library to encrypt
sensitive fields before storing them in the database.

Usage:
    ```python
    from agent_os.db.encryption import field_encryptor

    # Encrypt
    encrypted = field_encryptor.encrypt("sensitive_data")

    # Decrypt
    decrypted = field_encryptor.decrypt(encrypted)
    ```
"""

import os
import base64
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken


class FieldEncryption:
    """Field-level encryption for sensitive data.

    Encrypts individual fields before storing in database.
    Uses Fernet (symmetric encryption) with AES-128-CBC.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize encryption.

        Args:
            encryption_key: 32-byte URL-safe base64-encoded key.
                          If None, reads from FIELD_ENCRYPTION_KEY env var.

        Raises:
            ValueError: If key not provided and not in environment
        """
        if encryption_key:
            self.key = encryption_key
        else:
            self.key = os.getenv('FIELD_ENCRYPTION_KEY')

        if not self.key:
            raise ValueError(
                "Encryption key not provided. Set FIELD_ENCRYPTION_KEY environment variable."
            )

        # Ensure key is valid for Fernet
        try:
            self.cipher = Fernet(self.key)
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """Encrypt a plaintext string.

        Args:
            plaintext: String to encrypt (or None)

        Returns:
            Encrypted string as base64-encoded bytes (or None if input is None)

        Example:
            >>> encryptor = FieldEncryption()
            >>> encrypted = encryptor.encrypt("my_secret")
            >>> print(encrypted)
            'gAAAAABh...'
        """
        if plaintext is None:
            return None

        if not plaintext:
            return ""

        # Encrypt and return as string
        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """Decrypt an encrypted string.

        Args:
            ciphertext: Encrypted string from encrypt() (or None)

        Returns:
            Decrypted plaintext string (or None if input is None)

        Raises:
            InvalidToken: If ciphertext is invalid or corrupted

        Example:
            >>> encryptor = FieldEncryption()
            >>> decrypted = encryptor.decrypt("gAAAAABh...")
            >>> print(decrypted)
            'my_secret'
        """
        if ciphertext is None:
            return None

        if not ciphertext:
            return ""

        try:
            decrypted_bytes = self.cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken as e:
            raise ValueError(f"Failed to decrypt data: {e}")

    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key.

        Returns:
            URL-safe base64-encoded 32-byte key

        Example:
            >>> key = FieldEncryption.generate_key()
            >>> print(key)
            'abcdefghijklmnopqrstuvwxyz123456='
        """
        return Fernet.generate_key().decode()


# Global instance for convenience
field_encryptor = FieldEncryption()


def generate_encryption_key() -> str:
    """Generate a new encryption key for field encryption.

    Returns:
        URL-safe base64-encoded 32-byte key

    Usage:
        ```python
        from agent_os.db.encryption import generate_encryption_key

        # Generate key
        key = generate_encryption_key()

        # Set in environment
        export FIELD_ENCRYPTION_KEY=<key>
        ```
    """
    return FieldEncryption.generate_key()


# ============================================================================
# Database encryption utilities
# ============================================================================

class EncryptedField:
    """Encrypted database field helper.

    Provides automatic encryption/decryption for database fields.

    Usage:
        ```python
        # In model
        from sqlalchemy import Column, String
        from agent_os.db.encryption import EncryptedField

        class User(Base):
            __tablename__ = 'users'

            id = Column(Integer, primary_key=True)
            email = Column(String)  # Normal field
            api_key = Column(String)  # Encrypted field

        # In CRUD
        def create_user(db, email: str, api_key: str):
            # Encrypt API key before storing
            encrypted_key = EncryptedField.encrypt(api_key)

            user = User(
                email=email,
                api_key=encrypted_key
            )
            db.add(user)
            db.commit()

        def get_user_api_key(db, user_id: int):
            user = db.query(User).filter_by(id=user_id).first()

            # Decrypt API key after retrieving
            return EncryptedField.decrypt(user.api_key)
        ```
    """

    @staticmethod
    def encrypt(plaintext: Optional[str]) -> Optional[str]:
        """Encrypt field value."""
        return field_encryptor.encrypt(plaintext)

    @staticmethod
    def decrypt(ciphertext: Optional[str]) -> Optional[str]:
        """Decrypt field value."""
        return field_encryptor.decrypt(ciphertext)


# ============================================================================
# Database password encryption for tenant databases
# ============================================================================

def encrypt_db_password(password: str) -> str:
    """Encrypt database password for storage.

    Used to encrypt organization's database password in organizations table.

    Args:
        password: Database password to encrypt

    Returns:
        Encrypted password

    Example:
        >>> from agent_os.db.encryption import encrypt_db_password
        >>> encrypted = encrypt_db_password("my_db_password")
        >>> # Store encrypted in organizations.db_password
    """
    return field_encryptor.encrypt(password)


def decrypt_db_password(encrypted_password: str) -> str:
    """Decrypt database password from storage.

    Args:
        encrypted_password: Encrypted password from organizations.db_password

    Returns:
        Decrypted password

    Example:
        >>> from agent_os.db.encryption import decrypt_db_password
        >>> decrypted = decrypt_db_password(org.db_password)
        >>> # Use decrypted password to connect
    """
    return field_encryptor.decrypt(encrypted_password)
