"""Test password hashing and verification."""


from agent_os.auth.security import get_password_hash, verify_password


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_hash_password_returns_string(self):
        """Test hashing returns a string."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert isinstance(hashed, str)
        assert len(hashed) > 0
        # PRD10/V1 ``get_password_hash`` returns ``salt$hash`` where both
        # halves are 64 hex chars (SHA-256 + 16-byte salt). See
        # ``agent_os.auth.security.get_password_hash``.
        assert "$" in hashed
        salt, body = hashed.split("$", 1)
        assert len(salt) == 32 and len(body) == 64

    def test_hash_same_password_different_hashes(self):
        """Test hashing same password twice gives different hashes (salt)."""
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to salt.
        assert hash1 != hash2
        # Both still match the salt$hash format.
        assert hash1.count("$") >= 1 and hash2.count("$") >= 1

    def test_verify_correct_password(self):
        """Test verifying correct password returns True."""
        password = "correct_password"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """Test verifying wrong password returns False."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_empty_password(self):
        """Test verifying empty password."""
        password = ""
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True
        assert verify_password("non_empty", hashed) is False

    def test_hash_unicode_password(self):
        """Test hashing unicode passwords."""
        password = "密码123!@#测试"
        hashed = get_password_hash(password)

        assert isinstance(hashed, str)
        assert verify_password(password, hashed) is True

    def test_hash_long_password(self):
        """Test hashing very long passwords."""
        password = "a" * 100  # 100 characters
        hashed = get_password_hash(password)

        assert isinstance(hashed, str)
        assert verify_password(password, hashed) is True
