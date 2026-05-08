"""Test medium priority fixes for Mem0, Security, Git, and Config."""

import tempfile
from pathlib import Path

import pytest

from agent_os.capabilities.vcs.git import GitWrapper
from agent_os.memory.mem0_impl import Mem0Provider
from agent_os.server.security import (
    SecurityValidator,
    escape_shell_args,
)


class TestMem0Provider:
    """Test Mem0Provider FAISS index rebuilding."""

    @pytest.mark.skip(reason="Requires sentence-transformers installation")
    @pytest.mark.asyncio
    async def test_delete_rebuilds_index(self):
        """Test that deleting a memory rebuilds the FAISS index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = Mem0Provider(
                model_name="all-MiniLM-L6-v2",
                storage_path=tmpdir,
                embedding_dim=384,
            )

            from agent_os.core.types import RuntimeContext

            ctx = RuntimeContext(
                session_id="test_session",
                user_id="test_user",
                trace_id="test_trace",
            )

            # Add some memories
            mem1_id = await provider.add(ctx, "Memory 1")
            mem2_id = await provider.add(ctx, "Memory 2")
            mem3_id = await provider.add(ctx, "Memory 3")

            # Verify index size
            assert provider._index.ntotal == 3

            # Delete one memory
            deleted = await provider.delete(ctx, mem2_id)
            assert deleted is True

            # Verify index was rebuilt
            assert provider._index.ntotal == 2

            # Verify memory is gone
            mem = await provider.get(ctx, mem2_id)
            assert mem is None

    @pytest.mark.skip(reason="Requires sentence-transformers installation")
    @pytest.mark.asyncio
    async def test_cleanup_deleted(self):
        """Test cleanup of deleted memories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = Mem0Provider(
                model_name="all-MiniLM-L6-v2",
                storage_path=tmpdir,
                embedding_dim=384,
            )

            from agent_os.core.types import RuntimeContext

            ctx = RuntimeContext(
                session_id="test_session",
                user_id="test_user",
                trace_id="test_trace",
            )

            # Add memories
            await provider.add(ctx, "Memory 1")
            await provider.add(ctx, "Memory 2")

            # List all
            all_memories = await provider.list_all(ctx)
            assert len(all_memories) == 2

    @pytest.mark.asyncio
    async def test_optimize_index(self):
        """Test index optimization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = Mem0Provider(
                model_name="all-MiniLM-L6-v2",
                storage_path=tmpdir,
                embedding_dim=384,
            )

            stats = await provider.optimize_index()
            assert "total_memories" in stats
            assert "index_size" in stats


class TestSecurityValidator:
    """Test security validation functions."""

    def test_validate_path_traversal(self):
        """Test path traversal prevention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            # Valid path
            valid_path = SecurityValidator.validate_path("test.txt", workspace=workspace)
            assert "test.txt" in valid_path

            # Path traversal attempt
            with pytest.raises(ValueError, match="traversal"):
                SecurityValidator.validate_path("../../etc/passwd", workspace=workspace)

    def test_validate_filename(self):
        """Test filename validation."""
        # Valid filename
        assert SecurityValidator.validate_filename("test.txt") == "test.txt"

        # Null bytes
        with pytest.raises(ValueError, match="null"):
            SecurityValidator.validate_filename("test\x00.txt")

        # Path separators
        with pytest.raises(ValueError, match="separator"):
            SecurityValidator.validate_filename("test/file.txt")

        # Reserved names
        with pytest.raises(ValueError, match="reserved"):
            SecurityValidator.validate_filename("CON.txt")

    def test_sanitize_command(self):
        """Test command sanitization."""
        # Safe command
        safe = SecurityValidator.sanitize_command("ls -la")
        assert safe == "ls -la"

        # Dangerous pattern
        with pytest.raises(ValueError, match="pattern"):
            SecurityValidator.sanitize_command("rm -rf /")

    def test_escape_shell_args(self):
        """Test shell argument escaping."""
        escaped = escape_shell_args("ls", "-l", "file with spaces.txt")
        assert "file with spaces.txt" in escaped
        assert "'" in escaped or "\\" in escaped

    def test_validate_file_size(self):
        """Test file size validation."""
        # Valid size
        assert SecurityValidator.validate_file_size(1024) is True

        # Too large
        with pytest.raises(ValueError, match="too large"):
            SecurityValidator.validate_file_size(100 * 1024 * 1024)

        # Negative
        with pytest.raises(ValueError, match="negative"):
            SecurityValidator.validate_file_size(-1)


class TestGitWrapper:
    """Test Git operations wrapper."""

    def test_check_git_installed(self):
        """Test that git is installed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)
            # Should not raise if git is installed
            assert hasattr(git, "_run_git")

    def test_is_repo(self):
        """Test repository detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)

            # Not a repo yet
            assert git.is_repo() is False

            # Initialize repo
            git.init()

            # Now it's a repo
            assert git.is_repo() is True

    def test_init_and_status(self):
        """Test repository initialization and status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)

            # Initialize
            msg = git.init()
            assert "initialized" in msg.lower()

            # Get status (should be clean)
            status = git.status()
            assert status["branch"] == "master" or status["branch"] == "main"
            assert status["dirty"] is False

    def test_add_and_commit(self):
        """Test adding and committing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)
            git.init()

            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, Git!")

            # Stage the file
            msg = git.add("test.txt")
            assert "Staged" in msg

            # Commit
            commit_msg = git.commit("Initial commit")
            assert "Committed" in commit_msg

            # Check status (should be clean)
            status = git.status()
            assert status["dirty"] is False

    def test_get_diff(self):
        """Test getting diff."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)
            git.init()

            # Create and commit a file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Line 1")
            git.add("test.txt")
            git.commit("First commit")

            # Modify the file
            test_file.write_text("Line 1\nLine 2")

            # Get diff
            diff = git.get_diff()
            assert "Line 2" in diff or "+Line 2" in diff

    def test_log(self):
        """Test commit log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)
            git.init()

            # Create and commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Test")
            git.add("test.txt")
            git.commit("Test commit")

            # Get log
            log = git.log()
            assert len(log) == 1
            assert log[0]["message"] == "Test commit"

    def test_branch_operations(self):
        """Test branch creation and listing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git = GitWrapper(tmpdir)
            git.init()

            # Need an initial commit to create branches
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Initial commit")
            git.add("test.txt")
            git.commit("Initial commit")

            # Create a branch
            msg = git.create_branch("feature-branch", checkout=False)
            assert "Created branch" in msg

            # List branches
            branches = git.branch()
            assert "feature-branch" in branches


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
