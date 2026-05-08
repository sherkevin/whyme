"""Test FastAPI application configuration for API integration testing."""

from fastapi import FastAPI

# Import router instances, not modules
from agent_os.auth.router import router as auth_router
from agent_os.knowledge.router import router as knowledge_router
from agent_os.tasks.router import router as tasks_router

try:
    from agent_os.agent.router import router as agent_router
    _agent_router_available = True
except ImportError:
    _agent_router_available = False

# Create test app
test_app = FastAPI(title="AgentOS Test API")

# Include routers (note: routers already have their prefixes configured)
test_app.include_router(auth_router)
test_app.include_router(knowledge_router)
test_app.include_router(tasks_router)

# Include agent router if available
if _agent_router_available:
    test_app.include_router(agent_router)
