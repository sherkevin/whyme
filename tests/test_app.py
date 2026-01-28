"""Test FastAPI application configuration for API integration testing."""

from fastapi import FastAPI
# Import router instances, not modules
from agent_os.auth.router import router as auth_router
from agent_os.knowledge.router import router as knowledge_router
from agent_os.tasks.router import router as tasks_router

# Create test app
test_app = FastAPI(title="AgentOS Test API")

# Include routers (note: routers already have their prefixes configured)
test_app.include_router(auth_router)
test_app.include_router(knowledge_router)
test_app.include_router(tasks_router)
