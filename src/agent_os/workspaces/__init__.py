"""PRD10 workspace permission module."""

from agent_os.workspaces.models import WorkspaceMember
from agent_os.workspaces.router import router as workspaces_router

__all__ = ["WorkspaceMember", "workspaces_router"]
