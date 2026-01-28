"""Local filesystem sandbox implementation."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from agent_os.core.interfaces import ExecutionEnvironment
from agent_os.server.security import (
    validate_command,
    validate_file_size,
    sanitize_path,
)


class LocalSandbox(ExecutionEnvironment):
    """Execution environment that runs locally in a temp directory."""

    def __init__(self, image: str = "", workspace: str = "") -> None:
        # image arg is ignored for local
        self.workspace_root: Optional[Path] = None
        self._custom_workspace = workspace if workspace and workspace != "/workspace" else None

    async def start(self) -> None:
        """Prepare the local workspace."""
        if self.workspace_root and self.workspace_root.exists():
            return

        if self._custom_workspace:
            # Convert to absolute path to avoid issues
            workspace_path = Path(self._custom_workspace)
            if not workspace_path.is_absolute():
                # Resolve relative path from current working directory
                workspace_path = Path.cwd() / workspace_path
            self.workspace_root = workspace_path.resolve()
            self.workspace_root.mkdir(parents=True, exist_ok=True)
        else:
            # Create a temp directory
            self.workspace_root = Path(tempfile.mkdtemp(prefix="agentos_session_"))
            
        # Create a README to show it's working
        readme = self.workspace_root / "README.md"
        if not readme.exists():
            readme.write_text("# Sandbox Workspace\n\nThis is a temporary local workspace.")

    async def run_command(self, cmd: str) -> str:
        """Run a shell command in the workspace."""
        if not self.workspace_root:
            await self.start()

        # Security: Validate command before execution
        try:
            validate_command(cmd)
        except ValueError as e:
            raise RuntimeError(f"Command validation failed: {e}")

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace_root)
        )

        stdout, stderr = await process.communicate()

        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""

        if process.returncode != 0:
            raise RuntimeError(f"Command failed: {cmd}\n{error}\n{output}")

        return output

    async def write_file(self, path: str, content: str) -> None:
        """Write content to a file."""
        if not self.workspace_root:
            await self.start()

        # Security: Validate file size
        try:
            validate_file_size(len(content))
        except ValueError as e:
            raise RuntimeError(f"File size validation failed: {e}")

        # Security: Sanitize path
        try:
            safe_path = sanitize_path(path, self.workspace_root)
            full_path = self.workspace_root / safe_path
        except ValueError as e:
            raise RuntimeError(f"Path validation failed: {e}")

        # Ensure parent dirs exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    async def read_file(self, path: str) -> str:
        """Read content from a file."""
        if not self.workspace_root:
            await self.start()

        # Security: Sanitize path
        try:
            safe_path = sanitize_path(path, self.workspace_root)
            full_path = self.workspace_root / safe_path
        except ValueError as e:
            raise RuntimeError(f"Path validation failed: {e}")

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Security: Check file size before reading
        file_size = full_path.stat().st_size
        try:
            validate_file_size(file_size)
        except ValueError as e:
            raise RuntimeError(f"File too large: {e}")

        return full_path.read_text(encoding="utf-8")

    async def list_files(self, path: str = ".") -> list[str]:
        """List files in the workspace."""
        if not self.workspace_root:
            await self.start()

        # Security: Sanitize path
        try:
            safe_path = sanitize_path(path, self.workspace_root) if path != "." else "."
            base_path = self.workspace_root
            target_path = base_path / safe_path if path != "." else base_path
        except ValueError as e:
            raise RuntimeError(f"Path validation failed: {e}")

        if not target_path.exists():
            return []

        files = []
        # Return all files relative to workspace root
        for p in target_path.rglob("*"):
            if p.is_file():
                # Filter out hidden files/dirs if desired, simplistic check
                if not any(part.startswith(".") for part in p.relative_to(base_path).parts):
                    # Return posix style paths for consistency
                    files.append(p.relative_to(base_path).as_posix())
        return files

    async def stop(self) -> None:
        """Cleanup."""
        if self.workspace_root and not self._custom_workspace:
            # Only remove if it was a temp directory
            try:
                shutil.rmtree(self.workspace_root)
            except Exception:
                pass
        self.workspace_root = None
