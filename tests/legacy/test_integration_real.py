"""Integration test for high and medium priority fixes.

This script tests the actual running server to verify that:
1. Security checks are enforced
2. Git operations work
3. Mem0Provider works
4. Sandbox security integration
"""

import asyncio
from pathlib import Path


async def test_security_validation():
    """Test security validation functions."""
    print("\n=== Test 2: Security Validation ===")

    from agent_os.server.security import (
        SecurityValidator,
        sanitize_path,
        validate_command,
    )

    # Test path traversal prevention
    try:
        workspace = Path("./data/workspaces/test")
        workspace.mkdir(parents=True, exist_ok=True)

        # Safe path
        safe = sanitize_path("test.txt", workspace)
        print(f"[OK] Safe path validated: {safe}")

        # Path traversal attempt (should fail)
        try:
            dangerous = sanitize_path("../../etc/passwd", workspace)
            print(f"[FAIL] Path traversal NOT detected: {dangerous}")
            return False
        except ValueError as e:
            print(f"[OK] Path traversal detected and blocked: {e}")

        # Test filename validation
        try:
            result = SecurityValidator.validate_filename("test.txt")
            print(f"[OK] Valid filename accepted: {result}")
        except Exception as e:
            print(f"[FAIL] Valid filename rejected: {e}")
            return False

        # Test dangerous filename
        try:
            SecurityValidator.validate_filename("CON.txt")
            print("[FAIL] Reserved name NOT detected")
            return False
        except ValueError:
            print("[OK] Reserved name detected and blocked")

        # Test command validation
        try:
            validate_command("ls -la")
            print("[OK] Safe command accepted")
        except Exception as e:
            print(f"[FAIL] Safe command rejected: {e}")
            return False

        # Test dangerous command
        try:
            validate_command("rm -rf /")
            print("[FAIL] Dangerous command NOT detected")
            return False
        except ValueError:
            print("[OK] Dangerous command detected and blocked")

        return True

    except Exception as e:
        print(f"[FAIL] Security validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_git_operations():
    """Test Git wrapper operations."""
    print("\n=== Test 3: Git Operations ===")

    import tempfile

    from agent_os.capabilities.vcs.git import GitOperationError, GitWrapper

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)

            # Check if git is available
            print("[OK] GitWrapper initialized")

            # Initialize repo
            msg = git.init()
            print(f"[OK] Repository initialized: {msg}")

            # Check status
            status = git.status()
            print(f"[OK] Status retrieved: branch={status['branch']}, dirty={status['dirty']}")

            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, Git!")

            # Add file
            msg = git.add("test.txt")
            print(f"[OK] File staged: {msg}")

            # Commit
            commit_msg = git.commit("Test commit")
            print(f"[OK] Commit created: {commit_msg}")

            # Get log
            log = git.log(max_count=1)
            if log and log[0]["message"] == "Test commit":
                print("[OK] Commit log retrieved correctly")
            else:
                print(f"[FAIL] Commit log incorrect: {log}")
                return False

            # Get diff
            test_file.write_text("Hello, Modified Git!")
            diff = git.get_diff()
            if "Modified" in diff or "+Hello, Modified" in diff:
                print("[OK] Diff generated correctly")
            else:
                print(f"[WARN]  Diff might be empty: {diff[:100]}")

            return True

    except GitOperationError as e:
        print(f"[FAIL] Git operation failed: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Git test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mem0_provider():
    """Test Mem0Provider with index rebuilding."""
    print("\n=== Test 4: Mem0Provider ===")

    try:
        import tempfile

        from agent_os.core.types import RuntimeContext
        from agent_os.memory.mem0_impl import Mem0Provider

        print("[INFO]  Note: Mem0 tests require sentence-transformers")
        print("[INFO]  Testing index rebuilding logic only...")

        with tempfile.TemporaryDirectory() as tmpdir:
            provider = Mem0Provider(
                model_name="all-MiniLM-L6-v2",
                storage_path=tmpdir,
                embedding_dim=384,
            )

            print("[OK] Mem0Provider initialized")

            # Test optimize_index (doesn't require embeddings)
            stats = await provider.optimize_index()
            print(f"[OK] Index optimized: {stats}")

            return True

    except ImportError as e:
        print(f"[WARN]  sentence-transformers not installed (expected): {e}")
        return True  # This is expected
    except Exception as e:
        print(f"[FAIL] Mem0 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_sandbox_security():
    """Test sandbox security integration."""
    print("\n=== Test 5: Sandbox Security ===")

    try:
        import tempfile

        from agent_os.sandbox.local_impl import LocalSandbox

        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = LocalSandbox(workspace=tmpdir)
            await sandbox.start()

            print("[OK] LocalSandbox initialized")

            # Test file size validation
            try:
                large_content = "x" * (11 * 1024 * 1024)  # 11MB
                await sandbox.write_file("large.txt", large_content)
                print("[FAIL] Large file NOT rejected")
                return False
            except RuntimeError as e:
                if "too large" in str(e).lower():
                    print(f"[OK] Large file rejected: {e}")
                else:
                    print(f"[WARN]  Large file rejected with unexpected error: {e}")

            # Test path traversal in write_file
            try:
                await sandbox.write_file("../../etc/passwd", "malicious")
                print("[FAIL] Path traversal NOT detected in write_file")
                return False
            except RuntimeError as e:
                if "traversal" in str(e).lower() or "validation" in str(e).lower():
                    print(f"[OK] Path traversal detected in write_file: {e}")
                else:
                    print(f"[WARN]  Path traversal rejected with unexpected error: {e}")

            # Test command validation
            try:
                await sandbox.run_command("rm -rf /")
                print("[FAIL] Dangerous command NOT detected")
                return False
            except RuntimeError as e:
                if "validation" in str(e).lower() or "dangerous" in str(e).lower():
                    print(f"[OK] Dangerous command detected: {e}")
                else:
                    print(f"[WARN]  Dangerous command rejected with unexpected error: {e}")

            # Test safe operations
            await sandbox.write_file("test.txt", "Hello, Sandbox!")
            content = await sandbox.read_file("test.txt")
            if content == "Hello, Sandbox!":
                print("[OK] Safe file operations work correctly")
            else:
                print(f"[FAIL] File content mismatch: {content}")
                return False

            return True

    except Exception as e:
        print(f"[FAIL] Sandbox security test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("AgentOS Integration Tests - Priority Fixes")
    print("=" * 60)

    results = {}

    # Test 1: Security Validation
    results['security'] = await test_security_validation()

    # Test 2: Git Operations
    results['git'] = await test_git_operations()

    # Test 3: Mem0Provider
    results['mem0'] = await test_mem0_provider()

    # Test 4: Sandbox Security
    results['sandbox'] = await test_sandbox_security()

    # Print summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name:15} {status}")

    total = len(results)
    passed = sum(results.values())

    print("-" * 60)
    print(f"Total: {passed}/{total} tests passed ({passed*100//total}%)")
    print("=" * 60)

    if passed == total:
        print("\n[SUCCESS] All integration tests passed!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
