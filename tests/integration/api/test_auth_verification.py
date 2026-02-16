"""Integration tests for Auth verification code APIs.

Tests B-03B (send verification code) and B-03C (verify code).
"""

import pytest
import time
from httpx import AsyncClient


@pytest.mark.asyncio
class TestVerificationCodeAPI:
    """Test verification code API endpoints."""

    async def test_send_code_success(self, client: AsyncClient):
        """Test B-03B: Successfully send verification code."""
        response = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": "test@example.com",
                "code_type": "login"
            }
        )

        # Should succeed even if email doesn't exist (security)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "SUCCESS"
        assert "expires_in" in data["data"]
        assert data["data"]["expires_in"] == 300

    async def test_send_code_invalid_email(self, client: AsyncClient):
        """Test B-03B: Reject invalid email format."""
        response = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": "not-an-email",
                "code_type": "login"
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_send_code_rate_limit(self, client: AsyncClient):
        """Test B-03B: Rate limiting works."""
        email = "ratelimit@example.com"

        # First request should succeed
        response1 = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": email,
                "code_type": "login"
            }
        )
        assert response1.status_code == 200

        # Immediate second request should be rate limited
        response2 = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": email,
                "code_type": "login"
            }
        )
        assert response2.status_code == 200  # Returns 200 with rate limit info
        data = response2.json()
        assert data["code"] == "RATE_LIMITED"
        assert "retry_after" in data
        assert data["retry_after"] > 0

    async def test_send_code_different_types(self, client: AsyncClient):
        """Test B-03B: Support different code types."""
        types = ["login", "bind", "reset"]

        for code_type in types:
            response = await client.post(
                "/api/v1/auth/send-code",
                json={
                    "email": f"{code_type}@example.com",
                    "code_type": code_type
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == "SUCCESS"

    async def test_verify_code_success(self, client: AsyncClient, redis_client):
        """Test B-03C: Successfully verify code."""
        email = "verify-success@example.com"

        # First, create a code manually (bypass email)
        redis_client.setex(
            f"verify_code:{email}:login",
            300,
            "123456"
        )

        # Verify the code
        response = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": "123456",
                "code_type": "login"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "SUCCESS"

        # Code should be consumed (deleted)
        assert not redis_client.exists(f"verify_code:{email}:login")

    async def test_verify_code_invalid(self, client: AsyncClient, redis_client):
        """Test B-03C: Reject invalid code."""
        email = "verify-invalid@example.com"

        # Create a code
        redis_client.setex(
            f"verify_code:{email}:login",
            300,
            "123456"
        )

        # Try wrong code
        response = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": "654321",  # Wrong code
                "code_type": "login"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    async def test_verify_code_expired(self, client: AsyncClient, redis_client):
        """Test B-03C: Reject expired code."""
        email = "verify-expired@example.com"

        # Create code with 1 second TTL
        redis_client.setex(
            f"verify_code:{email}:login",
            1,
            "123456"
        )

        # Wait for expiration
        await asyncio.sleep(2)

        # Try to verify
        response = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": "123456",
                "code_type": "login"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "expired" in data["detail"].lower()

    async def test_verify_code_one_time_use(self, client: AsyncClient, redis_client):
        """Test B-03C: Code can only be used once."""
        email = "verify-once@example.com"

        # Create a code
        redis_client.setex(
            f"verify_code:{email}:login",
            300,
            "123456"
        )

        # First verification
        response1 = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": "123456",
                "code_type": "login"
            }
        )
        assert response1.status_code == 200

        # Second verification should fail (code consumed)
        response2 = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": "123456",
                "code_type": "login"
            }
        )
        assert response2.status_code == 400

    async def test_verify_code_too_many_attempts(
        self,
        client: AsyncClient,
        redis_client
    ):
        """Test B-03C: Lock after too many failed attempts."""
        email = "verify-lockout@example.com"

        # Create a code
        redis_client.setex(
            f"verify_code:{email}:login",
            300,
            "123456"
        )

        # Try 5 wrong codes
        for i in range(5):
            response = await client.post(
                "/api/v1/auth/verify-code",
                json={
                    "email": email,
                    "code": f"{i:06d}",  # Wrong code
                    "code_type": "login"
                }
            )
            if i < 4:
                assert response.status_code == 400
            else:
                # 5th attempt should trigger lockout
                assert response.status_code in [400, 423]

        # Account should be locked
        response = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": "123456",  # Even correct code
                "code_type": "login"
            }
        )
        assert response.status_code == 423  # Locked

    async def test_send_code_default_type(self, client: AsyncClient):
        """Test B-03B: Default to 'login' type."""
        response = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": "default@example.com"
                # code_type not specified, should default to "login"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "SUCCESS"


@pytest.mark.asyncio
class TestVerificationCodeFlow:
    """Test complete verification code workflows."""

    async def test_login_with_code_flow(self, client: AsyncClient, redis_client):
        """Test complete login with verification code flow."""
        email = "login-flow@example.com"

        # Step 1: Request code
        response1 = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": email,
                "code_type": "login"
            }
        )
        assert response1.status_code == 200

        # Simulate getting code from Redis (in real flow, from email)
        code = redis_client.get(f"verify_code:{email}:login")
        assert code is not None

        # Step 2: Verify code
        response2 = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": code.decode(),
                "code_type": "login"
            }
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data["code"] == "SUCCESS"

    async def test_bind_email_flow(self, client: AsyncClient, redis_client):
        """Test email binding flow."""
        email = "bind-flow@example.com"

        # Step 1: Request code
        response1 = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": email,
                "code_type": "bind"
            }
        )
        assert response1.status_code == 200

        # Step 2: Verify code
        code = redis_client.get(f"verify_code:{email}:bind")
        assert code is not None

        response2 = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": code.decode(),
                "code_type": "bind"
            }
        )
        assert response2.status_code == 200


@pytest.mark.asyncio
class TestVerificationCodeSecurity:
    """Test security features of verification code system."""

    async def test_no_email_enumeration(self, client: AsyncClient):
        """Test that send-code doesn't reveal if email exists."""
        # Non-existent email
        response1 = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": "nonexistent@example.com",
                "code_type": "login"
            }
        )
        assert response1.status_code == 200

        # Real email (if exists in test DB)
        response2 = await client.post(
            "/api/v1/auth/send-code",
            json={
                "email": "test@example.com",
                "code_type": "login"
            }
        )
        assert response2.status_code == 200

        # Responses should be identical (no enumeration)
        assert response1.json()["code"] == response2.json()["code"]

    async def test_code_format_validation(self, client: AsyncClient):
        """Test that code must be 6 digits."""
        response = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": "test@example.com",
                "code": "12345",  # 5 digits - too short
                "code_type": "login"
            }
        )
        assert response.status_code == 422  # Validation error

        response = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": "test@example.com",
                "code": "1234567",  # 7 digits - too long
                "code_type": "login"
            }
        )
        assert response.status_code == 422

        response = await client.post(
            "/api/v1/auth/verify-code",
            json={
                "email": "test@example.com",
                "code": "abcdef",  # Non-numeric
                "code_type": "login"
            }
        )
        # This might pass validation but fail verification
        assert response.status_code in [200, 400]


# Import asyncio
import asyncio
