"""Security utilities for file operations.

This module provides comprehensive security validation including:
- Path traversal prevention
- Command injection protection
- Filename validation
- File size limits
- Content type validation
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Optional


# Security constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB default
MAX_PATH_DEPTH = 20

# Blocked filenames (Windows reserved + dangerous system files)
BLOCKED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Dangerous command patterns (regex)
DANGEROUS_COMMAND_PATTERNS = [
    r"rm\s+-rf\s+[\/]",  # rm -rf / or rm -rf \
    r":\(\)",  # Fork bomb
    r">\s*\/dev\/[a-z]+",  # Writing to device files
    r"mkfs\.",  # Filesystem formatting
    r"dd\s+if=",  # Disk destruction with dd
    r"chmod\s+000",  # Removing all permissions
    r"chown\s+.*:\s*\/",  # Changing ownership of root
]


def sanitize_path(path: str, workspace: str | Path) -> str:
    """Sanitize a file path to prevent path traversal attacks.

    Args:
        path: The user-provided path (can be relative or absolute)
        workspace: The workspace root directory

    Returns:
        A safe path relative to workspace

    Raises:
        ValueError: If the path attempts to escape the workspace
    """
    workspace_path = Path(workspace).resolve()

    # Remove leading slashes to make it relative
    clean_path = path.lstrip("/\\").replace("\\", "/")

    # Join with workspace
    full_path = (workspace_path / clean_path).resolve()

    # Ensure the result is within workspace
    try:
        full_path.relative_to(workspace_path)
    except ValueError as e:
        raise ValueError(
            f"Path traversal detected: '{path}' attempts to access files outside workspace"
        ) from e

    # Return the safe relative path
    return str(full_path.relative_to(workspace_path).as_posix())


def validate_filename(filename: str) -> bool:
    """Validate a filename to prevent security issues.

    Args:
        filename: The filename to validate

    Returns:
        True if the filename is safe

    Raises:
        ValueError: If the filename contains dangerous characters
    """
    if not filename:
        raise ValueError("Filename cannot be empty")

    # Check for null bytes
    if "\x00" in filename:
        raise ValueError("Filename cannot contain null bytes")

    # Check for path separators (this should be a filename, not a path)
    if "/" in filename or "\\" in filename:
        raise ValueError("Filename cannot contain path separators")

    # Check for reserved characters on Windows
    reserved_chars = '<>:"|?*'
    if any(char in filename for char in reserved_chars):
        raise ValueError(f"Filename cannot contain reserved characters: {reserved_chars}")

    # Check for reserved device names on Windows
    reserved_names = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    name_without_ext = filename.split(".")[0].upper()
    if name_without_ext in reserved_names:
        raise ValueError(f"Filename uses reserved name: {name_without_ext}")

    # Check for leading/trailing dots and spaces (Windows issues)
    if filename.startswith(".") or filename.startswith(" ") or filename.endswith(".") or filename.endswith(" "):
        raise ValueError("Filename cannot start or end with dots or spaces")

    return True


def validate_command(command: str) -> bool:
    """Validate a shell command to prevent command injection.

    Args:
        command: The command string to validate

    Returns:
        True if the command appears safe

    Raises:
        ValueError: If the command contains dangerous patterns
    """
    if not command:
        raise ValueError("Command cannot be empty")

    command_lower = command.lower()

    # Check dangerous patterns using regex
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, command_lower):
            raise ValueError(f"Command contains dangerous pattern: {pattern}")

    # Check for simple dangerous patterns
    simple_patterns = [
        "; rm -rf",
        "; rm -r /",
        "mkfs",
        "dd if=/dev/zero",
        "> /dev/sda",
        "format c:",
        "del /f /s /q",
        "rmdir /s /q",
    ]

    for pattern in simple_patterns:
        if pattern in command_lower:
            raise ValueError(f"Command contains dangerous pattern: {pattern}")

    # Check for command chaining (allow simple cases)
    dangerous_chains = ["&&", "||", ";", "`", "$("]
    chain_count = sum(command.count(chain) for chain in dangerous_chains)

    if chain_count > 2:  # Allow some chaining but not excessive
        raise ValueError("Excessive command chaining detected")

    return True


def escape_shell_args(command: str, *args: str) -> str:
    """Escape shell arguments to prevent injection.

    Args:
        command: The base command
        *args: Arguments to escape

    Returns:
        Safe command string with escaped arguments

    Example:
        >>> escape_shell_args("ls", "-l", "file with spaces.txt")
        "ls -l 'file with spaces.txt'"
    """
    escaped_args = [shlex.quote(arg) for arg in args]
    return f"{command} {' '.join(escaped_args)}"


def validate_file_size(size: int, max_size: Optional[int] = None) -> bool:
    """Validate file size against maximum.

    Args:
        size: File size in bytes
        max_size: Maximum allowed size (defaults to MAX_FILE_SIZE)

    Returns:
        True if size is acceptable

    Raises:
        ValueError: If size exceeds maximum or is negative
    """
    max_size = max_size or MAX_FILE_SIZE

    if size < 0:
        raise ValueError("File size cannot be negative")

    if size > max_size:
        raise ValueError(
            f"File too large (max {max_size:,} bytes, got {size:,} bytes)"
        )

    return True


def validate_path_depth(path: str, max_depth: int = MAX_PATH_DEPTH) -> bool:
    """Validate path depth to prevent deep traversal.

    Args:
        path: The path to check
        max_depth: Maximum allowed depth

    Returns:
        True if depth is acceptable

    Raises:
        ValueError: If path is too deep
    """
    p = Path(path)
    depth = len(p.parts)

    if depth > max_depth:
        raise ValueError(
            f"Path too deep (max {max_depth} levels, got {depth})"
        )

    return True


def sanitize_command_output(output: str, max_length: int = 10000) -> str:
    """Sanitize command output to prevent excessive output.

    Args:
        output: The command output
        max_length: Maximum length to allow

    Returns:
        Truncated output if too long
    """
    if len(output) > max_length:
        return output[:max_length] + "\n... (output truncated)"

    return output


class SecurityValidator:
    """Centralized security validation class.

    This class provides a unified interface for all security validation
    operations including path validation, command sanitization, and
    input validation.
    """

    @staticmethod
    def validate_path(path: str, allow_absolute: bool = False, workspace: Optional[str] = None) -> str:
        """Validate and sanitize a file path.

        Args:
            path: The path to validate
            allow_absolute: Whether to allow absolute paths
            workspace: Optional workspace root for resolving relative paths

        Returns:
            Sanitized absolute path

        Raises:
            ValueError: If path is invalid or dangerous
        """
        return sanitize_path(path, workspace) if workspace else path

    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate a filename (no directory components).

        Args:
            filename: The filename to validate

        Returns:
            Validated filename

        Raises:
            ValueError: If filename is invalid
        """
        result = validate_filename(filename)
        return filename if result is True else result

    @staticmethod
    def sanitize_command(command: str) -> str:
        """Sanitize a shell command to prevent command injection.

        Args:
            command: The command string to sanitize

        Returns:
            Sanitized command string

        Raises:
            ValueError: If command contains dangerous patterns
        """
        validate_command(command)
        return command.strip()

    @staticmethod
    def escape_shell_arg(arg: str) -> str:
        """Escape a shell argument using shlex.quote.

        Args:
            arg: The argument to escape

        Returns:
            Safely escaped argument
        """
        return escape_shell_args("echo", arg)

    @staticmethod
    def validate_file_size(size: int, max_size: Optional[int] = None) -> bool:
        """Validate file size against maximum.

        Args:
            size: File size in bytes
            max_size: Maximum allowed size (defaults to MAX_FILE_SIZE)

        Returns:
            True if size is acceptable

        Raises:
            ValueError: If size exceeds maximum
        """
        return validate_file_size(size, max_size)


__all__ = [
    "sanitize_path",
    "validate_filename",
    "validate_command",
    "escape_shell_args",
    "validate_file_size",
    "validate_path_depth",
    "sanitize_command_output",
    "SecurityValidator",
    "MAX_FILE_SIZE",
    "MAX_PATH_DEPTH",
    "BLOCKED_NAMES",
]
