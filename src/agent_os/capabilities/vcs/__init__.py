"""Version Control System (VCS) capabilities."""

from agent_os.capabilities.vcs.git import GitWrapper, GitOperationError

__all__ = [
    "GitWrapper",
    "GitOperationError",
]
