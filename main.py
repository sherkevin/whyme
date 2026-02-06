"""Main application entry point for AgentOS.

This file provides a simple entry point that imports the FastAPI app
from the server module.
"""

from agent_os.server.app import app

__all__ = ["app"]
