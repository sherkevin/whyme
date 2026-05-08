"""Version Control System (VCS) capabilities."""

from agent_os.capabilities.vcs.git import GitOperationError, GitWrapper

__all__ = [
    "GitWrapper",
    "GitOperationError",
]
