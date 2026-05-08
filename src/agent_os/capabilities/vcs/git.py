"""Git operations wrapper for version control functionality.

This module provides high-level Git operations that can be used
by the coding agent for version control tasks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class GitOperationError(Exception):
    """Exception raised when Git operations fail."""
    pass


class GitWrapper:
    """High-level Git operations wrapper."""

    def __init__(self, workspace: str | Path):
        """Initialize Git wrapper for a workspace.

        Args:
            workspace: Path to the git repository
        """
        self.workspace = Path(workspace).resolve()
        self._check_git_installed()

    def _check_git_installed(self) -> None:
        """Check if git is installed and available."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
                text=True
            )
            print(f"[Git] Git version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise GitOperationError(
                "Git is not installed or not accessible. "
                "Please install Git to use version control features."
            ) from e

    def _run_git(self, args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the workspace.

        Args:
            args: Git command arguments (without 'git' prefix)
            capture: Whether to capture output

        Returns:
            Completed process result

        Raises:
            GitOperationError: If command fails
        """
        cmd = ["git"] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                check=True,
                text=True,
                cwd=str(self.workspace)
            )
            return result
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise GitOperationError(
                f"Git command failed: {' '.join(cmd)}\n{error_msg}"
            ) from e

    def is_repo(self) -> bool:
        """Check if the workspace is a git repository.

        Returns:
            True if .git directory exists
        """
        git_dir = self.workspace / ".git"
        return git_dir.exists() or git_dir.is_dir()

    def init(self) -> str:
        """Initialize a new git repository.

        Returns:
            Success message
        """
        if self.is_repo():
            return "Repository already initialized"

        result = self._run_git(["init"])
        return f"Initialized empty Git repository: {result.stdout.strip()}"

    def status(self) -> dict[str, Any]:
        """Get repository status.

        Returns:
            Dictionary with status information:
            - branch: Current branch name
            - dirty: True if there are uncommitted changes
            - staged: List of staged files
            - modified: List of modified files
            - untracked: List of untracked files
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        # Get current branch
        try:
            branch_result = self._run_git(["branch", "--show-current"])
            branch = branch_result.stdout.strip()
        except GitOperationError:
            branch = "HEAD (detached)"

        # Get status
        status_result = self._run_git(["status", "--porcelain"])
        status_lines = status_result.stdout.strip().split("\n") if status_result.stdout.strip() else []

        staged = []
        modified = []
        untracked = []

        for line in status_lines:
            if not line:
                continue
            status_code = line[:2]
            filepath = line[3:]

            if status_code[0] in ["M", "A", "D", "R"]:
                staged.append(filepath)
            if status_code[1] in ["M", "D"]:
                modified.append(filepath)
            if status_code == "??":
                untracked.append(filepath)

        return {
            "branch": branch,
            "dirty": len(status_lines) > 0,
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
        }

    def add(self, files: list[str] | str = ".") -> str:
        """Stage files for commit.

        Args:
            files: File path(s) to add, or "." for all files

        Returns:
            Success message
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        if isinstance(files, str):
            files = [files]

        # Add files
        self._run_git(["add"] + files)

        # Count staged files
        status_result = self._run_git(["diff", "--cached", "--name-only"])
        staged_count = len(status_result.stdout.strip().split("\n")) if status_result.stdout.strip() else 0

        return f"Staged {staged_count} file(s)"

    def commit(self, message: str, allow_empty: bool = False) -> str:
        """Create a commit.

        Args:
            message: Commit message
            allow_empty: Whether to allow empty commits

        Returns:
            Commit SHA
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")

        result = self._run_git(args)

        # Extract commit SHA
        sha_result = self._run_git(["rev-parse", "HEAD"])
        commit_sha = sha_result.stdout.strip()[:8]

        return f"Committed: {commit_sha}"

    def get_diff(self, cached: bool = False, file: str | None = None) -> str:
        """Get git diff.

        Args:
            cached: If True, show staged changes (default: False)
            file: Optional file path to diff

        Returns:
            Diff content
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        args = ["diff"]
        if cached:
            args.append("--cached")
        if file:
            args.append(file)

        result = self._run_git(args)
        return result.stdout

    def log(self, max_count: int = 10) -> list[dict[str, str]]:
        """Get commit history.

        Args:
            max_count: Maximum number of commits to return

        Returns:
            List of commit dictionaries with:
            - sha: Commit SHA (short)
            - message: Commit message
            - author: Author name
            - date: Commit date
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        args = [
            "log",
            f"-{max_count}",
            "--pretty=format:%H|%s|%an|%ad",
            "--date=short"
        ]

        result = self._run_git(args)
        commits = []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                commits.append({
                    "sha": parts[0][:8],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                })

        return commits

    def create_branch(self, branch_name: str, checkout: bool = True) -> str:
        """Create a new branch.

        Args:
            branch_name: Name for the new branch
            checkout: Whether to checkout the new branch

        Returns:
            Success message
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        # Create branch
        self._run_git(["branch", branch_name])

        msg = f"Created branch '{branch_name}'"

        if checkout:
            self.checkout(branch_name)
            msg += " and checked it out"

        return msg

    def checkout(self, branch_or_sha: str) -> str:
        """Checkout a branch or commit.

        Args:
            branch_or_sha: Branch name or commit SHA

        Returns:
            Success message
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        self._run_git(["checkout", branch_or_sha])
        return f"Checked out '{branch_or_sha}'"

    def branch(self) -> list[str]:
        """List all branches.

        Returns:
            List of branch names
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        result = self._run_git(["branch", "--format=%(refname:short)"])
        branches = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return branches

    def is_dirty(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if working directory is dirty
        """
        if not self.is_repo():
            return False

        try:
            status_result = self._run_git(["status", "--porcelain"])
            return len(status_result.stdout.strip()) > 0
        except GitOperationError:
            return False

    def get_changed_files(self) -> list[str]:
        """Get list of changed (modified) files.

        Returns:
            List of file paths
        """
        if not self.is_repo():
            return []

        try:
            result = self._run_git(["diff", "--name-only"])
            files = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return [f for f in files if f]
        except GitOperationError:
            return []

    def reset_file(self, filepath: str) -> str:
        """Reset a file to its last committed state.

        Args:
            filepath: Path to the file to reset

        Returns:
            Success message
        """
        if not self.is_repo():
            raise GitOperationError("Not a git repository")

        self._run_git(["checkout", "--", filepath])
        return f"Reset '{filepath}' to last commit"

    def clone(self, url: str, destination: str | None = None) -> str:
        """Clone a repository.

        Args:
            url: Repository URL
            destination: Optional destination directory

        Returns:
            Success message
        """
        args = ["clone", url]
        if destination:
            args.append(destination)

        result = self._run_git(args, capture=False)

        # Determine clone location
        clone_dir = destination or url.split("/")[-1].replace(".git", "")
        return f"Cloned repository to '{clone_dir}'"


__all__ = [
    "GitWrapper",
    "GitOperationError",
]
