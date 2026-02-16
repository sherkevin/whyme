"""PRD5 Verification Code API Test Script

This script tests all PRD5 functionality:
- B-03A: SMTP email service
- B-03B: Send verification code API
- B-03C: Verify code API

Run with: python test_prd5.py
"""

import requests
import time
import json
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8003"  # Adjust if needed
TEST_EMAIL = "test@example.com"  # Change to your test email


class PRD5Tester:
    """Test PRD5 verification code APIs."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def print_section(self, title: str):
        """Print section header."""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")

    def print_result(self, test_name: str, success: bool, details: str = ""):
        """Print test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {test_name}")
        if details:
            print(f"     {details}")

    def test_send_code_success(self) -> bool:
        """Test B-03B: Successfully send verification code."""
        self.print_section("Test 1: Send Verification Code (B-03B)")

        response = self.session.post(
            f"{self.base_url}/api/v1/auth/send-code",
            json={
                "email": TEST_EMAIL,
                "code_type": "login"
            }
        )

        success = response.status_code == 200
        data = response.json() if success else {}

        self.print_result(
            "Send verification code",
            success,
            f"Status: {response.status_code}, Response: {data}"
        )

        if success:
            print(f"\n   📧 Code sent to: {TEST_EMAIL}")
            print(f"   ⏰ Expires in: {data.get('data', {}).get('expires_in')} seconds")

        return success

    def test_send_code_invalid_email(self) -> bool:
        """Test B-03B: Reject invalid email format."""
        print("\n--- Test 2: Invalid Email Format ---")

        response = self.session.post(
            f"{self.base_url}/api/v1/auth/send-code",
            json={
                "email": "not-an-email",
                "code_type": "login"
            }
        )

        # Should return 422 (validation error)
        success = response.status_code == 422

        self.print_result(
            "Reject invalid email",
            success,
            f"Status: {response.status_code}"
        )

        return success

    def test_send_code_rate_limit(self) -> bool:
        """Test B-03B: Rate limiting works."""
        print("\n--- Test 3: Rate Limiting ---")

        email = f"ratelimit-{int(time.time())}@example.com"

        # First request
        response1 = self.session.post(
            f"{self.base_url}/api/v1/auth/send-code",
            json={
                "email": email,
                "code_type": "login"
            }
        )

        # Immediate second request (should be rate limited)
        response2 = self.session.post(
            f"{self.base_url}/api/v1/auth/send-code",
            json={
                "email": email,
                "code_type": "login"
            }
        )

        data1 = response1.json()
        data2 = response2.json()

        rate_limited = (
            response1.status_code == 200 and
            response2.status_code == 200 and
            data2.get("code") == "RATE_LIMITED"
        )

        self.print_result(
            "Rate limiting works",
            rate_limited,
            f"First: {data1.get('code')}, Second: {data2.get('code')}"
        )

        if rate_limited:
            print(f"\n   ⏱️  Retry after: {data2.get('retry_after')} seconds")

        return rate_limited

    def test_send_code_different_types(self) -> bool:
        """Test B-03B: Support different code types."""
        print("\n--- Test 4: Different Code Types ---")

        types = ["login", "bind", "reset"]
        all_success = True

        for code_type in types:
            email = f"{code_type}-{int(time.time())}@example.com"
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/send-code",
                json={
                    "email": email,
                    "code_type": code_type
                }
            )

            success = response.status_code == 200
            all_success = all_success and success

            self.print_result(
                f"Send '{code_type}' code",
                success,
                f"Status: {response.status_code}"
            )

        return all_success

    def test_verify_code_missing(self) -> bool:
        """Test B-03C: Verify code requires code to exist."""
        self.print_section("Test 5: Verify Code (B-03C)")

        email = f"verify-{int(time.time())}@example.com"

        response = self.session.post(
            f"{self.base_url}/api/v1/auth/verify-code",
            json={
                "email": email,
                "code": "123456",  # Code doesn't exist
                "code_type": "login"
            }
        )

        # Should return 400 (expired/missing)
        success = response.status_code == 400

        self.print_result(
            "Reject non-existent code",
            success,
            f"Status: {response.status_code}, Detail: {response.json().get('detail')}"
        )

        return success

    def test_verify_code_invalid_format(self) -> bool:
        """Test B-03C: Reject invalid code format."""
        print("\n--- Test 6: Invalid Code Format ---")

        test_cases = [
            ("12345", "5 digits - too short"),
            ("1234567", "7 digits - too long"),
            ("abcdef", "Non-numeric")
        ]

        all_success = True

        for code, description in test_cases:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/verify-code",
                json={
                    "email": "test@example.com",
                    "code": code,
                    "code_type": "login"
                }
            )

            # Should return 422 (validation error)
            success = response.status_code == 422
            all_success = all_success and success

            self.print_result(
                f"Reject {description}",
                success,
                f"Code: {code}, Status: {response.status_code}"
            )

        return all_success

    def test_verify_code_invalid_format_response(self) -> bool:
        """Test B-03C: Verify invalid format returns validation error."""
        print("\n--- Test 7: Code Format Validation ---")

        # Test with 5 digits (should fail)
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/verify-code",
            json={
                "email": "test@example.com",
                "code": "12345",  # Invalid: only 5 digits
                "code_type": "login"
            }
        )

        # Expect 422 Unprocessable Entity for validation error
        success = response.status_code == 422
        detail = response.json().get('detail', 'No detail')

        self.print_result(
            "Validate code format (6 digits required)",
            success,
            f"Status: {response.status_code}, Detail: {detail}"
        )

        return success

    def test_api_health(self) -> bool:
        """Test that API server is running."""
        self.print_section("Health Check")

        try:
            response = self.session.get(f"{self.base_url}/docs")
            success = response.status_code == 200

            self.print_result(
                "API server is running",
                success,
                f"Status: {response.status_code}"
            )

            return success
        except Exception as e:
            self.print_result(
                "API server is running",
                False,
                f"Error: {str(e)}"
            )
            return False

    def run_all_tests(self):
        """Run all PRD5 tests."""
        print("\n" + "="*60)
        print("  PRD5 Verification Code API Test Suite")
        print("="*60)

        results = []

        # Health check
        results.append(("Health Check", self.test_api_health()))

        # B-03B Tests
        results.append(("Send Code Success", self.test_send_code_success()))
        results.append(("Invalid Email", self.test_send_code_invalid_email()))
        results.append(("Rate Limiting", self.test_send_code_rate_limit()))
        results.append(("Different Types", self.test_send_code_different_types()))

        # B-03C Tests
        results.append(("Verify Missing Code", self.test_verify_code_missing()))
        results.append(("Invalid Format", self.test_verify_code_invalid_format()))
        results.append(("Format Validation", self.test_verify_code_invalid_format_response()))

        # Summary
        self.print_section("Test Summary")

        passed = sum(1 for _, result in results if result)
        total = len(results)

        print(f"\n  Total Tests: {total}")
        print(f"  ✅ Passed: {passed}")
        print(f"  ❌ Failed: {total - passed}")
        print(f"  Success Rate: {passed/total*100:.1f}%")

        print("\n" + "="*60)
        if passed == total:
            print("  🎉 ALL TESTS PASSED!")
        else:
            print(f"  ⚠️  {total - passed} test(s) failed")
        print("="*60 + "\n")

        return passed == total


def main():
    """Main entry point."""
    import sys

    # Check base URL
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL

    print(f"\n🚀 Testing PRD5 APIs at: {base_url}")
    print(f"📧 Test email: {TEST_EMAIL}")
    print(f"\n⚠️  Make sure:")
    print(f"   1. Server is running at {base_url}")
    print(f"   2. Redis is available")
    print(f"   3. Check your email for verification codes")
    print(f"\n🔄 Starting tests...\n")

    # Run tests
    tester = PRD5Tester(base_url)
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
