"""AgentOS FastAPI application with WebSocket and REST API endpoints."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_os.server.diff_service import DiffService

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent_os.common import (
    ApiErrorCode,
    Prd10AccessLogMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    error_json_response,
    http_exception_to_envelope,
)
from agent_os.common.sentry_setup import init_sentry as _init_sentry

# PRD10 §11.5 — initialize Sentry as early as possible so module-import
# errors during router wiring also reach the dashboard. ``init_sentry`` is
# idempotent and a no-op when ``SENTRY_DSN`` is unset; the second call from
# ``startup_event`` keeps belt-and-suspenders coverage if env was set late.
_init_sentry()
# PRD10 §11.10 account-compliance router (data export / soft-delete /
# unsubscribe). Lives under /api/v1/me/* alongside the existing /api/v1/me
# profile endpoint mounted by ``me_router``.
from agent_os.account import account_router
from agent_os.agent_aider import AiderAgent
from agent_os.agent_legacy import Agent
from agent_os.ai.router import router as ai_router
from agent_os.auth.router import demo_router, me_router
from agent_os.auth.router import router as auth_router
from agent_os.billing import billing_router
from agent_os.workspaces import workspaces_router

# PRD10 product-data routers (Agent 2 ownership).
from agent_os.capture.router import router as capture_router
from agent_os.conversations.router import router as conversations_router
from agent_os.core.config import instantiate, load_config
from agent_os.core.interfaces import AgentCallbackHandler
from agent_os.feed.router import router as feed_router
from agent_os.garden.router import router as garden_router
from agent_os.garden.router_prd10 import router as garden_prd10_router
from agent_os.inbox.router import router as inbox_router
from agent_os.insights.router import router as insights_router
from agent_os.jobs.router import router as jobs_router
from agent_os.kb.router import router as kb_router
from agent_os.knowledge.router import router as knowledge_router
from agent_os.marketplace import marketplace_router
from agent_os.notifications.router import router as notifications_router
from agent_os.search_engine.router import router as stage4_router

# PRD10 intelligence-domain routers (Agent 3 ownership).
from agent_os.search_engine.router_prd10 import router as search_prd10_router
from agent_os.server.security import sanitize_path
from agent_os.skills.router import router as skills_prd10_router
from agent_os.stage3.router import router as stage3_router
from agent_os.tasks.prd10_router import router as tasks_prd10_router
from agent_os.tasks.router import router as tasks_router
from agent_os.today.prd10_router import router as today_prd10_router
from agent_os.today.router import router as today_router
from agent_os.uploads.router import router as uploads_router

# Import agent_router later to avoid circular import issues


# PRD10 §6.2 — Lifespan-based startup/shutdown (replaces deprecated
# ``@app.on_event(...)`` hooks). FastAPI / Starlette runs the function
# body up to ``yield`` on startup, hands control back to the application,
# then runs the rest after the last request finishes (or on SIGTERM).
#
# Invariants this preserves from the legacy hooks:
#   1. ``configure_logging`` runs once before any request — JSON
#      handler installs without races.
#   2. ``_init_sentry`` is called twice (module load + lifespan)
#      because env vars can be injected after import in containers;
#      the call is idempotent.
#   3. DB engine + tables initialize before the first request hits
#      ``get_db``. Failures log but don't crash the app — preserves
#      backward compatibility with environments that pre-create
#      schema externally (Alembic, manual SQL, etc.).
#   4. PRD10 worker loop only starts when ``AGENTOS_PRD10_WORKER`` is
#      truthy (the ``is_worker_enabled`` predicate); failures degrade
#      to a warning instead of crashing the app.
#   5. ``stop_worker_loop`` runs on shutdown (or on lifespan exit) so
#      pytest fixtures and uvicorn ``--reload`` cycles don't leak the
#      background task between runs.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize app resources before serving and tear them down on exit.

    All imports stay lazy to avoid pulling DB / worker / logging modules
    into module-import time (which keeps ``import agent_os.server.app``
    fast for the test collector and OpenAPI generators).
    """

    import logging

    from agent_os.common import configure_logging
    from agent_os.db.base import get_engine, init_db
    from agent_os.jobs.worker_loop import (
        is_worker_enabled,
        start_worker_loop,
        stop_worker_loop,
    )

    configure_logging()
    _init_sentry()

    get_engine()
    logging.info("Database engine initialized")

    try:
        await init_db()
        logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Failed to create database tables: {e}")

    if is_worker_enabled():
        try:
            start_worker_loop()
        except Exception as exc:
            logging.warning(f"Failed to start PRD10 worker loop: {exc}")

    try:
        yield
    finally:
        try:
            await stop_worker_loop()
        except Exception as exc:
            logging.warning(f"Failed to stop PRD10 worker loop cleanly: {exc}")


app = FastAPI(
    title="Mydow API",
    description=(
        "Mydow / PRD10 backend — capture, knowledge base, AI chat, search, "
        "skills, notifications, and async jobs. All `/api/v1/*` responses use "
        "the PRD10 §6 envelope `{success, data, request_id}` (or paginated "
        "`{items, pagination}` / error `{error: {code, message, details}}`).\n\n"
        "**Quick start**:\n"
        "```bash\n"
        "curl -X POST http://localhost:8000/api/v1/auth/register \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\"username\":\"demo\",\"email\":\"demo@example.com\",\"password\":\"demo123\"}'\n"
        "curl -X POST http://localhost:8000/api/v1/auth/login \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\"username\":\"demo\",\"password\":\"demo123\"}'\n"
        "# capture text\n"
        "curl -X POST http://localhost:8000/api/v1/capture/text \\\n"
        "  -H 'Authorization: Bearer <token>' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\"content\":\"今天想到一个新点子\",\"tags\":[\"想法\"]}'\n"
        "```\n\n"
        "See the [architecture overview](/) and `docs/architecture.md`."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Authentication", "description": "Register / login / token refresh"},
        {"name": "User", "description": "PRD10 §5.1 `/api/v1/me`"},
        {"name": "Capture", "description": "PRD10 §8 `/api/v1/capture/*`"},
        {"name": "Knowledge Base", "description": "PRD10 §10 folders & documents"},
        {"name": "Feed", "description": "PRD10 §9 cards & feed"},
        {"name": "Mydow AI", "description": "PRD10 §11 conversations & SSE streaming"},
        {"name": "Skills", "description": "PRD10 §17 skill list & runs"},
        {"name": "Search", "description": "PRD10 §13 hybrid search"},
        {"name": "Tasks (PRD10)", "description": "PRD10 §14 task CRUD (UUID identity)"},
        {"name": "Notifications", "description": "PRD10 §15 notifications & SSE stream"},
        {"name": "Jobs", "description": "PRD10 §16 async job status"},
        {"name": "Insights & Reports", "description": "PRD10 §12 insights / daily-weekly reports"},
        {"name": "Demo", "description": "Demo auto-login & seeded data"},
    ],
    contact={"name": "Mydow Team"},
    license_info={"name": "Proprietary"},
    lifespan=lifespan,
)

# PRD10 envelope requires every response to carry a stable request id.
# Order matters: Starlette runs ``add_middleware`` in reverse insertion
# order (last added = outermost). Target call stack:
#
#     RequestIdMiddleware            (outermost — stamps request_id first)
#     RateLimitMiddleware            (PRD10 §29 — checks before work happens)
#     Prd10AccessLogMiddleware       (logs duration once everything below ran)
#     <app>
#
# So we ``add_middleware`` from innermost to outermost. The rate-limit
# middleware is mounted unconditionally and stays inert unless
# ``AGENTOS_RATE_LIMIT=on``; the inactive path is a single env check
# plus a policy lookup short-circuit.
app.add_middleware(Prd10AccessLogMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)

# PRD10 §11.4 CORS — strict by default, configurable via env vars.
# AGENTOS_CORS_ORIGINS: comma-separated allowed origins (e.g. "https://demo.mydow.app")
# AGENTOS_CORS_ALLOW_ALL=1 explicitly opens "*" for local development. The default
# falls back to common dev origins so `npm run dev` style workflows work without
# extra config but production deployments stay locked down.
import os as _os

from fastapi.middleware.cors import CORSMiddleware as _CORSMiddleware

_cors_origins_raw = _os.getenv("AGENTOS_CORS_ORIGINS", "").strip()
_cors_allow_all = _os.getenv("AGENTOS_CORS_ALLOW_ALL", "").strip().lower() in ("1", "on", "true", "yes")
if _cors_allow_all:
    _cors_origins: list[str] = ["*"]
elif _cors_origins_raw:
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
else:
    # Sensible local-dev defaults; production deployments should override
    # via AGENTOS_CORS_ORIGINS to a strict list.
    _cors_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8770",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8770",
    ]
app.add_middleware(
    _CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not _cors_allow_all,  # cannot use credentials with "*"
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

_PRD10_ENVELOPE_PREFIXES = (
    "/api/v1/capture",
    "/api/v1/uploads",
    "/api/v1/kb",
    "/api/v1/jobs",
    "/api/v1/notifications",
    "/api/v1/feed",
    "/api/v1/cards",
    "/api/v1/today",
    "/api/v1/inbox",
    # Agent 3 PRD10 intelligence surface.
    "/api/v1/search",
    "/api/v1/ai",
    "/api/v1/skills",
    "/api/v1/garden",
    "/api/v1/insights",
    "/api/v1/reports",
    # PRD10 §11.10 account compliance surface (export / delete / unsubscribe).
    "/api/v1/me",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Keep newly wired PRD10 APIs on the envelope without reshaping legacy APIs."""

    if request.url.path.startswith(_PRD10_ENVELOPE_PREFIXES):
        return http_exception_to_envelope(exc, request=request)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return PRD10 validation envelopes for newly wired APIs."""

    if request.url.path.startswith(_PRD10_ENVELOPE_PREFIXES):
        return error_json_response(
            ApiErrorCode.VALIDATION_ERROR,
            "Validation error",
            details={"errors": jsonable_encoder(exc.errors())},
            status_code=422,
            request=request,
        )

    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )

# Include API routers.
# Order matters: PRD10 routers ship the new envelope and must match BEFORE
# their legacy counterparts (today / search / garden) so the legacy view
# stays reachable only via legacy-shaped sub-paths (e.g. /api/v1/search/index).
app.include_router(auth_router)
app.include_router(me_router)
# PRD10 §11.10 account compliance: /api/v1/me/{export, unsubscribe} +
# DELETE /api/v1/me. Mounted right after ``me_router`` so the ``/me``
# tag stays grouped in /docs and the longer paths (``/me/export`` etc.)
# don't shadow the legacy ``GET /me``.
app.include_router(account_router)
app.include_router(demo_router)
app.include_router(workspaces_router)
app.include_router(billing_router)
app.include_router(marketplace_router)
app.include_router(inbox_router)
# PRD10 intelligence routers (Agent 3): registered before legacy stage4/garden
# so /api/v1/search and /api/v1/garden hit the PRD10 read-path first.
app.include_router(search_prd10_router)
app.include_router(ai_router)
app.include_router(skills_prd10_router)
app.include_router(garden_prd10_router)
app.include_router(insights_router)

app.include_router(today_router)
app.include_router(knowledge_router)
# PRD10 §14 task router (UUID identity); registered BEFORE legacy
# Integer-keyed tasks router so PRD10 envelopes apply to /api/v1/tasks
# and /api/v1/tasks/{uuid}. Legacy /today, /stats, /batch sub-paths
# remain reachable through ``tasks_router`` because typed UUID path
# params won't match int IDs and bare /tasks list/create are PRD10's
# canonical contract.
app.include_router(tasks_prd10_router)
app.include_router(tasks_router)
app.include_router(conversations_router)
app.include_router(stage3_router)
app.include_router(stage4_router)
app.include_router(garden_router)

# PRD10 product-data routers (Agent 2).
# ``today_prd10_router`` is included BEFORE ``today_router`` so the PRD10
# ``GET /api/v1/today`` matches first; the legacy view stays reachable at
# ``/api/v1/today/legacy``.
app.include_router(today_prd10_router)
app.include_router(capture_router)
app.include_router(uploads_router)
app.include_router(feed_router)
app.include_router(kb_router)
app.include_router(jobs_router)
app.include_router(notifications_router)

# PRD10 §11.5b — operator-only Sentry smoke endpoint. Mounted only when
# the env opt-in is on AND Sentry itself is initialized; safe to leave the
# import on every deploy because the registration is conditional.
try:
    from agent_os.common.sentry_test_router import (
        is_sentry_test_endpoint_enabled,
    )
    from agent_os.common.sentry_test_router import (
        router as sentry_test_router,
    )

    if is_sentry_test_endpoint_enabled():
        app.include_router(sentry_test_router)
except Exception:  # pragma: no cover - defensive, never block startup
    import logging as _logging
    _logging.getLogger("agent_os.prd10.sentry").warning(
        "sentry_test_router_mount_failed", exc_info=True
    )


# PRD10 §6.2 — startup / shutdown hooks moved to ``lifespan`` above.
# Keeping this comment here so future readers see the migration trail.


# Import and include agent router after app creation
# to avoid circular import issues with the agent package
try:
    from agent_os.agent.router import router as agent_router
    app.include_router(agent_router)
except Exception as e:
    # If agent router fails to import, log but don't crash
    import logging
    logging.warning(f"Failed to import agent router: {e}")

from agent_os.server.openapi_examples import install_openapi_examples

install_openapi_examples(app)


class SessionMetadata(BaseModel):
    """Metadata for a session."""
    id: str
    name: str
    created_at: float
    workspace: str
    last_accessed: float

class SessionManager:
    """Manages active sessions and their sandboxes."""

    def __init__(self) -> None:
        self._sessions: dict[str, ExecutionEnvironment] = {}
        self._agents: dict[str, Agent] = {}
        self._diff_services: dict[str, DiffService] = {}
        self._output_queues: dict[str, asyncio.Queue] = {}
        self._event_loops: dict[str, asyncio.AbstractEventLoop] = {}
        self._lock = asyncio.Lock()
        
        # Persistence
        self._metadata: dict[str, SessionMetadata] = {}
        self._storage_path = Path("data/sessions.json")
        self._load_metadata()

        # Default configuration
        self.sandbox_provider = "agent_os.sandbox.docker_impl.DockerSandbox"
        
        if os.environ.get("AGENTOS_SANDBOX") == "local":
            self.sandbox_provider = "agent_os.sandbox.local_impl.LocalSandbox"

    def _load_metadata(self) -> None:
        """Load session metadata from disk."""
        if self._storage_path.exists():
            try:
                import json
                data = json.loads(self._storage_path.read_text(encoding="utf-8"))
                for item in data:
                    meta = SessionMetadata(**item)
                    self._metadata[meta.id] = meta
            except Exception as e:
                print(f"Failed to load sessions: {e}")

    def _save_metadata(self) -> None:
        """Save session metadata to disk."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [m.dict() for m in self._metadata.values()]
            import json
            self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Failed to save sessions: {e}")

    async def list_sessions(self) -> list[SessionMetadata]:
        """List all sessions."""
        return list(self._metadata.values())

    async def get_or_create_sandbox(
        self,
        session_id: str,
        image: str = "agentos-ubuntu:latest",
        workspace: str = "/workspace",
    ) -> ExecutionEnvironment:
        """Get or create a sandbox for the given session."""
        async with self._lock:
            # Check metadata first to get correct workspace path
            if session_id in self._metadata:
                workspace = self._metadata[session_id].workspace

            if session_id not in self._sessions:
                try:
                    # Load sandbox configuration from config file
                    try:
                        config = load_config("config.yaml")
                        if config.sandbox:
                            image = config.sandbox.image
                            # Read additional config from YAML directly for extra parameters
                            import yaml
                            with open("config.yaml", encoding="utf-8") as f:
                                yaml_data = yaml.safe_load(f)
                            sandbox_yaml = yaml_data.get("sandbox", {})
                            memory_limit = sandbox_yaml.get("memory_limit", "512m")
                            cpu_quota = sandbox_yaml.get("cpu_quota", 50000)
                            network_disabled = sandbox_yaml.get("network_disabled", False)
                            read_only = sandbox_yaml.get("read_only", False)
                        else:
                            memory_limit = "512m"
                            cpu_quota = 50000
                            network_disabled = False
                            read_only = False
                    except Exception as e:
                        print(f"Failed to load sandbox config: {e}, using defaults")
                        memory_limit = "512m"
                        cpu_quota = 50000
                        network_disabled = False
                        read_only = False

                    # Instantiate dynamically with security parameters
                    if "DockerSandbox" in self.sandbox_provider:
                        sandbox = instantiate(
                            self.sandbox_provider,
                            image=image,
                            workspace=workspace,
                            memory_limit=memory_limit,
                            cpu_quota=cpu_quota,
                            network_disabled=network_disabled,
                            read_only=read_only
                        )
                    else:
                        # LocalSandbox doesn't support these parameters
                        sandbox = instantiate(
                            self.sandbox_provider,
                            workspace=workspace
                        )

                    await sandbox.start()
                    print(f"[INFO] Sandbox started for session {session_id}: {type(sandbox).__name__}")
                except Exception as e:
                    # Fallback to Local if Docker fails or not found (for DX)
                    print(f"Failed to load {self.sandbox_provider} (error: {e}), falling back to LocalSandbox")
                    from agent_os.sandbox.local_impl import LocalSandbox
                    sandbox = LocalSandbox(workspace=workspace)
                    await sandbox.start()

                self._sessions[session_id] = sandbox

                # Update last accessed
                if session_id in self._metadata:
                    import time
                    self._metadata[session_id].last_accessed = time.time()
                    self._save_metadata()

            return self._sessions[session_id]

    async def create_session_metadata(self, session_id: str, name: str, workspace: str) -> None:
        """Register a new session."""
        import time
        meta = SessionMetadata(
            id=session_id,
            name=name,
            created_at=time.time(),
            workspace=workspace,
            last_accessed=time.time()
        )
        self._metadata[session_id] = meta
        self._save_metadata()

    async def get_or_create_agent(self, session_id: str) -> Agent | AiderAgent:
        """Get or create an agent for the given session."""
        async with self._lock:
            # ALWAYS create a new AiderAgent for now (to avoid old Agent instances)
            # Get workspace for this session
            meta = self._metadata.get(session_id)
            if not meta:
                # Create default workspace
                workspace = f"data/workspaces/{session_id}"
                Path(workspace).mkdir(parents=True, exist_ok=True)
            else:
                workspace = meta.workspace

            # Load default config
            try:
                config = load_config("config.yaml")
            except FileNotFoundError:
                # Fallback if config is missing (e.g. tests)
                from agent_os.core.config import (
                    AgentConfig,
                    Config,
                    ContextConfig,
                    LLMConfig,
                    MemoryConfig,
                )
                config = Config(
                    agent=AgentConfig(name="AgentOS"),
                    llm=LLMConfig(
                        provider="agent_os.llm.litellm_impl.LiteLLMProvider",
                        config={}  # Empty config dict for LiteLLM
                    ),
                    memory=MemoryConfig(
                        provider="agent_os.memory.simple_memory.SimpleMemory",
                        config={}
                    ),
                    context=ContextConfig(
                        provider="agent_os.context.simple_context.SimpleContextManager",
                        config={}
                    )
                )

            # Create AiderAgent instead of regular Agent
            print(f"[DEBUG] Creating NEW AiderAgent for session {session_id} in workspace {workspace}")

            # Log to file
            with open("debug_agent_creation.log", "a", encoding="utf-8") as f:
                f.write(f"\nCreating AiderAgent: {session_id} in {workspace}\n")

            agent = AiderAgent(
                session_id=session_id,
                workspace_root=workspace,
                config=config
            )
            # No need to call initialize() - AiderAgent lazy-loads aider

            self._agents[session_id] = agent

            with open("debug_agent_creation.log", "a", encoding="utf-8") as f:
                f.write("AiderAgent created successfully\n")

            return self._agents[session_id]

    async def remove_session(self, session_id: str) -> None:
        """Remove a session and stop its sandbox."""
        async with self._lock:
            if session_id in self._sessions:
                # Stop if it has a stop method
                sandbox = self._sessions[session_id]
                if hasattr(sandbox, "stop"):
                    await sandbox.stop()
                del self._sessions[session_id]
            # Clean up diff service
            if session_id in self._diff_services:
                del self._diff_services[session_id]
            if session_id in self._output_queues:
                del self._output_queues[session_id]
            if session_id in self._event_loops:
                del self._event_loops[session_id]

    async def get_or_create_diff_service(
        self,
        session_id: str,
        output_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
    ) -> DiffService:
        """Get or create a diff service for the given session."""
        async with self._lock:
            if session_id not in self._diff_services:
                from agent_os.server.diff_service import DiffService
                self._diff_services[session_id] = DiffService(session_id, output_queue, loop)
                self._output_queues[session_id] = output_queue
                self._event_loops[session_id] = loop
            return self._diff_services[session_id]

    def get_diff_service(self, session_id: str) -> DiffService | None:
        """Get existing diff service for session without creating."""
        return self._diff_services.get(session_id)

    async def touch_session(self, session_id: str) -> None:
        """Update last_accessed timestamp for a session."""
        if session_id in self._metadata:
            import time
            self._metadata[session_id].last_accessed = time.time()
            self._save_metadata()


from agent_os.core.interfaces import ExecutionEnvironment

# Global session manager
_session_manager = SessionManager()


# Request/Response models
class FileContentRequest(BaseModel):
    """Request model for file content operations."""

    path: str
    content: str


class FileContentResponse(BaseModel):
    """Response model for file content operations."""

    path: str
    content: str


class FileTreeNode(BaseModel):
    """Node in the file tree."""

    name: str
    path: str
    type: str  # "file" or "directory"
    children: list[FileTreeNode] = []


class SessionCreateRequest(BaseModel):
    """Request model for creating a session."""

    user_id: str
    image: str = "agentos/aider-runtime:latest"
    name: str = "Untitled Project"
    workspace: str | None = None  # Optional, will be auto-generated if empty


class SessionResponse(BaseModel):
    """Response model for session operations."""

    session_id: str
    user_id: str
    sandbox_id: str | None
    name: str
    status: str


class WebSocketCallbackHandler(AgentCallbackHandler):
    """Callback handler that sends events over WebSocket conforming to PRD1 protocol."""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
    
    async def _send_event(self, action: str, data: Any = None, msg: str = "") -> None:
        payload = {
            "action": action,
            "status": "executing",
        }
        if data:
            payload["data"] = data
        if msg:
            payload["message"] = msg
            
        try:
            await self.websocket.send_json({
                "type": "event",
                "payload": payload
            })
        except (WebSocketDisconnect, RuntimeError):
            # Connection closed, stop trying to send
            pass
        except Exception as e:
            print(f"Error sending event: {e}")

    async def on_log(self, message: str) -> None:
        await self._send_event("log", msg=message)

    async def on_tool_start(self, tool_name: str, args: Any) -> None:
        await self._send_event("tool_start", data={"tool": tool_name, "args": args})

    async def on_tool_end(self, tool_name: str, result: str) -> None:
        await self._send_event("tool_end", data={"tool": tool_name, "result": result})

    async def on_agent_response(self, content: str) -> None:
        # We could stream here if we had token-level events
        pass


# WebSocket endpoint
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for real-time chat and updates."""
    msg = f"[DEBUG WS] WebSocket connection requested for session: {session_id}"
    print(msg, flush=True)
    with open("ws_debug.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

    await websocket.accept()
    msg2 = f"[DEBUG WS] WebSocket accepted for session: {session_id}"
    print(msg2, flush=True)
    with open("ws_debug.log", "a", encoding="utf-8") as f:
        f.write(msg2 + "\n")

    # Create output queue for this session
    debug_msg3 = "[DEBUG WS] Creating output queue..."
    print(debug_msg3, flush=True)
    with open("ws_debug.log", "a", encoding="utf-8") as f:
        f.write(debug_msg3 + "\n")

    output_queue = asyncio.Queue()

    debug_msg4 = "[DEBUG WS] Getting event loop..."
    print(debug_msg4, flush=True)
    with open("ws_debug.log", "a", encoding="utf-8") as f:
        f.write(debug_msg4 + "\n")

    loop = asyncio.get_running_loop()

    debug_msg = f"[DEBUG WS] About to enter try block for session: {session_id}"
    print(debug_msg, flush=True)
    with open("ws_debug.log", "a", encoding="utf-8") as f:
        f.write(debug_msg + "\n")

    # Get or create agent for this session
    try:
        print(f"[DEBUG WS] Getting or creating agent for session: {session_id}", flush=True)
        with open("ws_debug.log", "a", encoding="utf-8") as f:
            f.write(f"[DEBUG WS] Getting or creating agent for session: {session_id}\n")

        agent = await _session_manager.get_or_create_agent(session_id)

        # Set WebSocket communication for AiderAgent
        if hasattr(agent, '_output_queue'):
            agent._output_queue = output_queue
        if hasattr(agent, '_event_loop'):
            agent._event_loop = loop

        with open("ws_debug.log", "a", encoding="utf-8") as f:
            f.write("[DEBUG WS] Agent created/retrieved successfully\n")
        print("[DEBUG WS] Agent created/retrieved successfully", flush=True)

        # Ensure sandbox exists too (often needed by tools)
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        # Create diff service for this session
        diff_service = await _session_manager.get_or_create_diff_service(
            session_id, output_queue, loop
        )

        # Update last accessed
        await _session_manager.touch_session(session_id)

        # Notify client
        await websocket.send_json({
            "type": "event",
            "payload": {
                "action": "system",
                "message": "Connected to Agent. Ready to help."
            }
        })

        callbacks = [WebSocketCallbackHandler(websocket)]

        # Start background task to consume events from queue and send to WebSocket
        async def event_consumer():
            """Background task that consumes events from the queue."""
            while True:
                try:
                    event = await output_queue.get()
                    await websocket.send_json(event)
                except (WebSocketDisconnect, RuntimeError):
                    # Connection lost
                    break
                except Exception:
                    break

        consumer_task = asyncio.create_task(event_consumer())

        while True:
            try:
                # PRD1: Expect structural JSON input or plain text fallback
                raw_msg = await websocket.receive_text()
                print(f"[DEBUG] WebSocket received: {raw_msg[:100]}...")  # Debug log
                user_text = raw_msg

                # Parse JSON to check for diff responses and confirm_ask responses
                import json
                command = None
                try:
                    data = json.loads(raw_msg)
                    if isinstance(data, dict):
                        if data.get("type") == "input":
                            payload = data.get("payload", {})
                            user_text = payload.get("text", "")
                            command = payload.get("command", "")

                            # Handle diff approval/rejection
                            if command in ("yes", "no", "approve", "reject"):
                                diff_service.handle_user_response(
                                    "approve" if command in ("yes", "approve") else "reject",
                                    payload.get("diff_id")
                                )
                                continue  # Don't process as regular chat message

                            # Handle confirm_ask response
                            confirm_id = payload.get("confirm_id")
                            if confirm_id:
                                # Check if agent has a WebSocketIO instance
                                response = payload.get("response", command)
                                if response:
                                    # Try to find the WebSocketIO instance
                                    ws_io = None
                                    if hasattr(agent, '_ws_io'):
                                        ws_io = agent._ws_io
                                    elif hasattr(agent, '_aider_integration') and agent._aider_integration:
                                        if hasattr(agent._aider_integration, '_ws_io'):
                                            ws_io = agent._aider_integration._ws_io

                                    if ws_io and hasattr(ws_io, 'receive_confirm_response'):
                                        ws_io.receive_confirm_response(
                                            confirm_id,
                                            response.lower() in ("yes", "approve", "y", "true")
                                        )
                                continue  # Don't process as regular chat message
                except:
                    pass  # Treat as plain text

                if not user_text:
                    continue

                # Send acknowledgement
                await websocket.send_json({
                    "type": "event",
                    "payload": {
                        "action": "status_change",
                        "status": "thinking"
                    }
                })

                try:
                    # Run agent chat with callbacks
                    print(f"[DEBUG] Calling agent.chat() with message: {user_text[:50]}...")

                    # Log agent type
                    with open("debug_websocket.log", "a", encoding="utf-8") as f:
                        f.write(f"\nAgent type: {type(agent).__name__}\n")
                        f.write(f"Agent class: {agent.__class__.__module__}.{agent.__class__.__name__}\n")
                        f.write(f"Message: {user_text[:50]}...\n")

                    response = await agent.chat(
                        message=user_text,
                        session_id=session_id,
                        callbacks=callbacks
                    )
                    print(f"[DEBUG] Agent responded with: {list(response.keys())}")

                    with open("debug_websocket.log", "a", encoding="utf-8") as f:
                        f.write(f"Response keys: {list(response.keys())}\n")

                    final_content = response.get("content", "")

                    await websocket.send_json({
                        "type": "event",
                        "payload": {
                            "action": "chat_response",
                            "status": "waiting_for_user",
                            "data": {"content": final_content}
                        }
                    })

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "payload": {"message": str(e)}
                        })
                    except:
                        pass

            except (WebSocketDisconnect, RuntimeError):
                break

    except WebSocketDisconnect:
        print("[DEBUG WS] WebSocket disconnected by client")
    except Exception as exc:
        # Log ALL errors to file for debugging
        import traceback
        with open("websocket_errors.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{asyncio.get_event_loop().time()}] WebSocket Exception:\n")
            f.write(f"Type: {type(exc).__name__}\n")
            f.write(f"Message: {exc}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n")

        # Ignore "Cannot call 'send' once a close message has been sent"
        if "close message" not in str(exc) and "closed" not in str(exc):
            print(f"WebSocket error: {exc}")
        try:
             await websocket.close(code=1011)
        except:
            pass
    finally:
        # Clean up consumer task
        if 'consumer_task' in locals():
            consumer_task.cancel()


class FileWriteRequest(BaseModel):
    path: str
    content: str


@app.get("/api/sessions/{session_id}/files", tags=["files"])
async def list_files(session_id: str, path: str = ".") -> dict[str, Any]:
    """List files in the session workspace."""
    sandbox = await _session_manager.get_or_create_sandbox(session_id)
    files = await sandbox.list_files(path)
    return {"files": files}


@app.get("/api/sessions/{session_id}/files/content", tags=["files"])
async def get_file_content(session_id: str, path: str) -> dict[str, str]:
    """Get file content."""
    sandbox = await _session_manager.get_or_create_sandbox(session_id)
    try:
        content = await sandbox.read_file(path)
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/sessions/{session_id}/files", tags=["files"])
async def write_file(session_id: str, request: FileWriteRequest) -> dict[str, str]:
    """Write content to a file."""
    sandbox = await _session_manager.get_or_create_sandbox(session_id)
    await sandbox.write_file(request.path, request.content)
    return {"status": "ok"}


# Session management endpoints
@app.get("/api/sessions", response_model=list[dict])
async def list_sessions() -> list[dict]:
    """List all available sessions."""
    sessions = await _session_manager.list_sessions()
    return [s.dict() for s in sessions]


@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest) -> SessionResponse:
    """Create a new session with a sandbox."""
    import re
    import uuid
    
    session_id = str(uuid.uuid4())
    
    # Determine workspace path
    if request.workspace:
        workspace = request.workspace
    else:
        # Create a workspace based on name (sanitized)
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', request.name).lower()
        workspace = f"./data/workspaces/{safe_name}_{session_id[:8]}"

    # Register session
    await _session_manager.create_session_metadata(session_id, request.name, workspace)

    try:
        sandbox = await _session_manager.get_or_create_sandbox(
            session_id=session_id,
            image=request.image,
            workspace=workspace,
        )

        sandbox_id = None
        if hasattr(sandbox, "_container") and sandbox._container:
            sandbox_id = sandbox._container.id
        elif hasattr(sandbox, "workspace_root"):
             sandbox_id = "local"

        return SessionResponse(
            session_id=session_id,
            user_id=request.user_id,
            sandbox_id=sandbox_id,
            name=request.name,
            status="active",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get session information."""
    sandbox = await _session_manager.get_or_create_sandbox(session_id)
    
    # Get metadata
    sessions = await _session_manager.list_sessions()
    meta = next((s for s in sessions if s.id == session_id), None)
    name = meta.name if meta else "Unknown Session"
    
    sandbox_id = None
    if hasattr(sandbox, "_container") and sandbox._container:
        sandbox_id = sandbox._container.id
    elif hasattr(sandbox, "workspace_root"):
            sandbox_id = "local"

    return SessionResponse(
        session_id=session_id,
        user_id="unknown",  # Would be stored in session
        sandbox_id=sandbox_id,
        name=name,
        status="active",
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a session and stop its sandbox."""
    await _session_manager.remove_session(session_id)
    return {"message": f"Session {session_id} deleted"}


from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# Get the directory where this file is located - more robust
# This works whether app is imported or run directly
_CURRENT_FILE = Path(__file__).resolve()
STATIC_DIR = _CURRENT_FILE.parent / "static"

# Also ensure we can find the static directory by checking common locations
if not STATIC_DIR.exists():
    # Try relative to current working directory (for development)
    _alt_static = Path("src/agent_os/server/static").resolve()
    if _alt_static.exists():
        STATIC_DIR = _alt_static
    else:
        # Try one more relative path
        _alt_static2 = Path("agent_os/server/static").resolve()
        if _alt_static2.exists():
            STATIC_DIR = _alt_static2

# File system endpoints
@app.get("/api/sessions/{session_id}/files/tree")
async def get_file_tree(session_id: str, path: str = "") -> FileTreeNode:
    """Get the file tree for a session's sandbox."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        print(f"[DEBUG] File tree for session {session_id}")
        print(f"[DEBUG] Sandbox type: {type(sandbox).__name__}")
        print(f"[DEBUG] Has workspace_root: {hasattr(sandbox, 'workspace_root')}")

        # For LocalSandbox
        if hasattr(sandbox, "workspace_root"):
            import os
            root = sandbox.workspace_root
            print(f"[DEBUG] Workspace root: {root}")
            print(f"[DEBUG] Root exists: {os.path.exists(root) if root else False}")

            if root and os.path.exists(root):
                try:
                    items = os.listdir(root)
                    print(f"[DEBUG] Found {len(items)} items: {items[:5]}")

                    children = []
                    for item in items:
                        if item.startswith("."):
                            continue

                        item_path = os.path.join(root, item)
                        is_dir = os.path.isdir(item_path)

                        children.append(FileTreeNode(
                            name=item,
                            path=item,
                            type="directory" if is_dir else "file"
                        ))

                    print(f"[DEBUG] Returning {len(children)} children")
                    return FileTreeNode(
                        name="workspace",
                        path="/",
                        type="directory",
                        children=children
                    )
                except Exception as e:
                    print(f"[ERROR] Failed to list files: {e}")
                    import traceback
                    traceback.print_exc()

        return FileTreeNode(name="workspace", path="/", type="directory", children=[])
    except Exception as e:
        import traceback
        print(f"[ERROR] File tree error: {e}")
        traceback.print_exc()
        return FileTreeNode(name="workspace", path="/", type="directory", children=[])


@app.get("/")
async def get_index(go: str | None = None):
    """Serve the V1 investor-friendly hero landing page at the site root.

    PRD10 §10.5 default-entry switch (replaces the old §15.20 redirect).
    When ``static/landing/index.html`` is deployed we render it as the
    public homepage so first-time visitors (investors / customers / press)
    see a value-prop landing instead of being teleported into the demo
    workspace. A prominent **"开始体验"** CTA on the landing page links
    to ``/mydow/biz/``; press users / Chrome-MCP smoke / docker healthcheck
    can also short-circuit by passing ``?go=demo`` which 307-redirects
    straight to the business prototype (preserving the old §15.20
    behaviour as an opt-in).

    Fallback chain when the landing bundle is missing (e.g. running tests
    against a barebones tree): land on the business prototype if present,
    else the SPA, else the legacy AgentOS index.
    """

    v14_index = _MYDOW_DIR / "biz_v14" / "index.html" if _MYDOW_DIR.exists() else None
    biz_v10 = _MYDOW_DIR / "biz" / "index.html" if _MYDOW_DIR.exists() else None
    has_v14 = v14_index is not None and v14_index.exists()
    has_v10 = biz_v10 is not None and biz_v10.exists()

    if go == "demo":
        if has_v14:
            return RedirectResponse(url="/mydow/biz_v14/", status_code=307)
        if has_v10:
            return RedirectResponse(url="/mydow/biz/", status_code=307)

    landing_index = _LANDING_DIR / "index.html"
    if _LANDING_DIR.exists() and landing_index.exists():
        with open(landing_index, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    if has_v14:
        return RedirectResponse(url="/mydow/biz_v14/", status_code=307)
    if has_v10:
        return RedirectResponse(url="/mydow/biz/", status_code=307)

    if _MYDOW_DIR.exists():
        return RedirectResponse(url="/mydow/", status_code=307)

    return await get_legacy_index()


@app.get("/mydow/")
async def get_mydow_default_entry():
    """PRD10 §15.20 / §15.34 — ``/mydow/`` redirects to the business prototype.

    Priority chain (top-to-bottom): v1.4 (`biz_v14/`, business owner's
    canonical drop) → v1.0 (`biz/`, legacy bridge.js host) → SPA shell.

    §15.34 (2026-05-07) flipped the default to v1.4 so investor-facing
    visits land on the latest business-owner-approved visual. Earlier
    revisions sent users to v1.0 which the user judged a "严重错误" on
    2026-05-07 17:25 because the `/mydow/` page no longer matched the
    business owner's zip drop.

    Defined **before** ``app.mount("/mydow", StaticFiles(html=True))`` so
    Starlette's first-match wins. The mount continues to serve every
    other path under ``/mydow/...`` (including ``/mydow/spa/index.html``,
    ``/mydow/biz/...``, ``/mydow/biz_v14/...``, ``/mydow/style.css``)
    directly from disk.
    """

    v14_path = _MYDOW_DIR / "biz_v14" / "index.html"
    if v14_path.exists():
        return RedirectResponse(url="/mydow/biz_v14/", status_code=307)
    biz_path = _MYDOW_DIR / "biz" / "index.html"
    if biz_path.exists():
        return RedirectResponse(url="/mydow/biz/", status_code=307)
    return RedirectResponse(url="/mydow/spa/", status_code=307)


@app.get("/mydow/biz_v14/")
async def get_mydow_biz_v14() -> HTMLResponse:
    """PRD10 §15.30 / §15.32 — serve the v1.4 business prototype with
    Dark Reader + bridge_v14.js auto-injected before ``</body>``.

    The v1.4 prototype (``static/mydow/biz_v14/index.html``, 461 KB) ships
    as a high-fidelity static page with ``simulateAction`` placeholders.
    We do **not** modify the original HTML — instead we inject a single
    Dark Reader and ``<script defer src="/mydow/biz_v14/bridge_v14.js">`` immediately before
    ``</body>`` so the bridge can run after the page's IIFE registers
    its own listeners (capture-phase + bubble-phase coexistence).

    Falls through to the static mount when the v1.4 bundle is missing
    so dev branches without the asset don't 500.
    """

    v14_index = _MYDOW_DIR / "biz_v14" / "index.html"
    if not v14_index.exists():
        return HTMLResponse(
            content="<h1>Error</h1><p>v1.4 bundle not found at static/mydow/biz_v14/</p>",
            status_code=404,
        )
    with open(v14_index, encoding="utf-8") as f:
        html = f.read()
    bridge_tag = (
        '<script defer src="/mydow/biz_v14/vendor/darkreader.min.js" '
        'data-mydow-darkreader="true"></script>\n'
        '<script defer src="/mydow/biz_v14/vendor/markdown-it.min.js" '
        'data-mydow-markdown-it="true"></script>\n'
        '<script defer src="/mydow/biz_v14/bridge_v14.js" '
        'data-mydow-bridge-v14="true"></script>\n'
        '  <script defer src="/mydow/biz_v14/bridge_v14_ext.js" '
        'data-mydow-bridge-v14-ext="true"></script>\n  </body>'
    )
    if 'data-mydow-bridge-v14' not in html:
        # Inject just before the closing body so the prototype IIFE runs
        # first; bridge_v14.js attaches capture-phase listeners after,
        # then bridge_v14_ext.js (this commit) wires the long tail of
        # data-toast / data-inline-menu / data-notice-action / data-account-action
        # buttons to real PRD10 endpoints.
        html = html.replace("</body>", bridge_tag, 1)
    return HTMLResponse(content=html)


@app.get("/mydow/spa/")
async def get_mydow_spa_alias() -> HTMLResponse:
    """PRD10 §15.20 — ``/mydow/spa/`` resolves to the legacy SPA index.

    Serves ``static/mydow/index.html`` (the JS-rendered SPA shell) so the
    old prototype remains reachable for regression comparison while the
    biz prototype takes over the default ``/mydow/`` entry. Defined
    explicitly because StaticFiles only auto-resolves ``index.html`` at
    the directory root, not for the ``spa/`` alias.

    The SPA index uses **relative** paths (``./style.css``, ``./app.js``,
    ``./mydow-api.js``); when served from ``/mydow/spa/`` those would
    resolve to ``/mydow/spa/style.css`` (404). We inject a
    ``<base href="/mydow/">`` so every relative URL resolves against the
    real bundle directory under ``/mydow/`` regardless of the alias path.
    """

    spa_index = _MYDOW_DIR / "index.html"
    if not spa_index.exists():
        return HTMLResponse(
            content="<h1>Error</h1><p>SPA bundle not found</p>",
            status_code=404,
        )
    with open(spa_index, encoding="utf-8") as f:
        html = f.read()
    if "<base " not in html:
        # Inject right after <head> so it precedes every relative href/src.
        html = html.replace("<head>", "<head>\n    <base href=\"/mydow/\">", 1)
    return HTMLResponse(content=html)


@app.get("/legacy")
async def get_legacy_index() -> HTMLResponse:
    """Serve the legacy AgentOS static index page."""

    index_file = STATIC_DIR / "index.html"

    # Debug: print the path we're trying to load
    print(f"[DEBUG] Loading index.html from: {index_file}")
    print(f"[DEBUG] Index file exists: {index_file.exists()}")

    if not index_file.exists():
        # Fallback: try to find the file anywhere
        matches = list(Path(".").rglob("index.html"))
        if matches:
            index_file = matches[0]
            print(f"[DEBUG] Found index.html at: {index_file}")
        else:
            return HTMLResponse(
                content=f"<h1>Error</h1><p>Could not find index.html</p><p>Looked in: {STATIC_DIR}</p>",
                status_code=500
            )

    with open(index_file, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/login.html")
async def get_login() -> HTMLResponse:
    """Serve the login page."""
    login_file = STATIC_DIR / "login.html"

    if not login_file.exists():
        return HTMLResponse(
            content="<h1>Error</h1><p>Could not find login.html</p>",
            status_code=404
        )

    with open(login_file, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/project-wizard.html")
async def get_project_wizard() -> HTMLResponse:
    """Serve the project wizard page."""
    wizard_file = STATIC_DIR / "project-wizard.html"

    if not wizard_file.exists():
        return HTMLResponse(
            content="<h1>Error</h1><p>Could not find project-wizard.html</p>",
            status_code=404
        )

    with open(wizard_file, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# Mount static files (optional, for css/js if split)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Mount the Mydow Web frontend bundle delivered in
# ``Mydow_Web_Frontend_Complete_Package.zip``. The package ships as a single
# HTML prototype under ``static/mydow/index.html`` plus a sibling
# ``mydow-api.js`` that wires the static prototype's DOM hooks
# (``data-nav-target``, the global search input, etc.) to the real PRD10
# backend. ``static/`` is the project-root static folder, which is distinct
# from ``src/agent_os/server/static`` mounted above.
_MYDOW_DIR = Path("static/mydow").resolve()
if not _MYDOW_DIR.exists():
    # When running from the repo root the path above is correct; when
    # running from inside ``src/`` we fall back one level.
    _alt_mydow = (Path(__file__).resolve().parents[3] / "static" / "mydow")
    if _alt_mydow.exists():
        _MYDOW_DIR = _alt_mydow

if _MYDOW_DIR.exists():
    app.mount(
        "/mydow",
        StaticFiles(directory=str(_MYDOW_DIR), html=True),
        name="mydow",
    )


# PRD10 §11.10 compliance: serve Privacy / Terms HTML pages from
# ``static/legal/{privacy,terms,index}.html`` so the frontend can deep-link
# (`/legal/privacy.html` / `/legal/terms.html`) and we have an investor-
# facing surface for the right-to-erasure / right-to-portability story.
_LEGAL_DIR = Path("static/legal").resolve()
if not _LEGAL_DIR.exists():
    _alt_legal = (Path(__file__).resolve().parents[3] / "static" / "legal")
    if _alt_legal.exists():
        _LEGAL_DIR = _alt_legal

if _LEGAL_DIR.exists():
    app.mount(
        "/legal",
        StaticFiles(directory=str(_LEGAL_DIR), html=True),
        name="legal",
    )


# PRD10 §10.5 — investor-friendly hero landing bundle. Lives at
# ``static/landing/index.html`` and is rendered by the root `/` handler
# (``get_index`` above). Mount it under ``/landing/`` as well so deep
# links (favicon variants / og-image / future split css/js) resolve
# without needing a per-file route. The hero page itself is fully
# self-contained (inline CSS, inline SVG icon) so the mount is mostly
# for forward-compatibility with future asset splits.
_LANDING_DIR = Path("static/landing").resolve()
if not _LANDING_DIR.exists():
    _alt_landing = (Path(__file__).resolve().parents[3] / "static" / "landing")
    if _alt_landing.exists():
        _LANDING_DIR = _alt_landing

if _LANDING_DIR.exists():
    app.mount(
        "/landing",
        StaticFiles(directory=str(_LANDING_DIR), html=True),
        name="landing",
    )


@app.post("/api/sessions/{session_id}/files/save")
async def save_file_content(session_id: str, request: FileContentRequest) -> dict[str, str]:
    """Save content to a file in the sandbox."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        # Get workspace root for sanitization
        if hasattr(sandbox, "workspace_root") and sandbox.workspace_root:
            workspace = sandbox.workspace_root
        else:
            workspace = sandbox.workspace

        # Sanitize path to prevent traversal attacks
        safe_path = sanitize_path(request.path, workspace)

        await sandbox.write_file(safe_path, request.content)
        return {"status": "success", "path": safe_path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/files/content")
async def get_file_content(session_id: str, path: str) -> FileContentResponse:
    """Get the content of a file."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        # Ensure sandbox is ready (LocalSandbox might need start to create dir)
        if not hasattr(sandbox, "workspace_root") and not hasattr(sandbox, "_container"):
             await sandbox.start()

        # Get workspace root for sanitization
        if hasattr(sandbox, "workspace_root") and sandbox.workspace_root:
            workspace = sandbox.workspace_root
        else:
            workspace = sandbox.workspace

        # Sanitize path to prevent traversal attacks
        safe_path = sanitize_path(path, workspace)

        content = await sandbox.read_file(safe_path)

        return FileContentResponse(path=safe_path, content=content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.delete("/api/sessions/{session_id}/files")
async def delete_file(session_id: str, path: str) -> dict[str, str]:
    """Delete a file in the sandbox."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        # Get workspace root for sanitization
        if hasattr(sandbox, "workspace_root") and sandbox.workspace_root:
            workspace = sandbox.workspace_root
        else:
            workspace = sandbox.workspace

        # Sanitize path to prevent traversal attacks
        safe_path = sanitize_path(path, workspace)

        await sandbox.run_command(f"rm -rf {safe_path}")

        return {"message": f"File {safe_path} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Toolkit API =====

@app.get("/api/sessions/{session_id}/toolkit/skills")
async def list_skills(session_id: str) -> dict[str, Any]:
    """List all skills in the session's toolkit."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import json
            import os

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            registry_path = os.path.join(toolkit_dir, "registry.json")

            if os.path.exists(registry_path):
                with open(registry_path, encoding="utf-8") as f:
                    registry = json.load(f)
                    return {"skills": registry.get("skills", [])}
            else:
                return {"skills": []}

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/toolkit/skills/{skill_name}")
async def get_skill(session_id: str, skill_name: str) -> dict[str, Any]:
    """Get a specific skill's code."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import os

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            skill_path = os.path.join(toolkit_dir, "bins", f"{skill_name}.py")

            if os.path.exists(skill_path):
                with open(skill_path, encoding="utf-8") as f:
                    code = f.read()
                    return {"name": skill_name, "code": code, "path": f"bins/{skill_name}.py"}
            else:
                raise HTTPException(status_code=404, detail=f"Skill {skill_name} not found")

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/toolkit/skills")
async def create_skill(session_id: str, skill_data: dict[str, Any]) -> dict[str, Any]:
    """Create a new skill."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import os
            import subprocess
            import sys

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            manager_path = os.path.join(toolkit_dir, "manager.py")

            skill_name = skill_data.get("name")
            if not skill_name:
                raise HTTPException(status_code=400, detail="Skill name is required")

            # Create skill using manager
            result = subprocess.run(
                [sys.executable, manager_path, "new", skill_name],
                cwd=toolkit_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Refresh registry
                subprocess.run(
                    [sys.executable, manager_path, "refresh"],
                    cwd=toolkit_dir,
                    capture_output=True,
                    text=True
                )
                return {"message": f"Skill {skill_name} created successfully", "name": skill_name}
            else:
                raise HTTPException(status_code=500, detail=result.stderr)

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sessions/{session_id}/toolkit/skills/{skill_name}")
async def update_skill(session_id: str, skill_name: str, skill_data: dict[str, Any]) -> dict[str, Any]:
    """Update a skill's code."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import os
            import subprocess
            import sys

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            skill_path = os.path.join(toolkit_dir, "bins", f"{skill_name}.py")

            code = skill_data.get("code")
            if code is None:
                raise HTTPException(status_code=400, detail="Code is required")

            # Write the updated code
            with open(skill_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Refresh registry
            manager_path = os.path.join(toolkit_dir, "manager.py")
            subprocess.run(
                [sys.executable, manager_path, "refresh"],
                cwd=toolkit_dir,
                capture_output=True,
                text=True
            )

            return {"message": f"Skill {skill_name} updated successfully", "name": skill_name}

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}/toolkit/skills/{skill_name}")
async def delete_skill(session_id: str, skill_name: str) -> dict[str, Any]:
    """Delete a skill."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import os
            import subprocess
            import sys

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            skill_path = os.path.join(toolkit_dir, "bins", f"{skill_name}.py")

            if os.path.exists(skill_path):
                os.remove(skill_path)

                # Refresh registry
                manager_path = os.path.join(toolkit_dir, "manager.py")
                subprocess.run(
                    [sys.executable, manager_path, "refresh"],
                    cwd=toolkit_dir,
                    capture_output=True,
                    text=True
                )

                return {"message": f"Skill {skill_name} deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail=f"Skill {skill_name} not found")

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/toolkit/mcp-servers")
async def list_mcp_servers(session_id: str) -> dict[str, Any]:
    """List all MCP servers in the session's toolkit."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import json
            import os

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            registry_path = os.path.join(toolkit_dir, "registry.json")

            if os.path.exists(registry_path):
                with open(registry_path, encoding="utf-8") as f:
                    registry = json.load(f)
                    return {"mcp_servers": registry.get("mcp_servers", [])}
            else:
                return {"mcp_servers": []}

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/toolkit/mcp-servers")
async def add_mcp_server(session_id: str, server_data: dict[str, Any]) -> dict[str, Any]:
    """Add a new MCP server."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import os
            import subprocess
            import sys

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            manager_path = os.path.join(toolkit_dir, "manager.py")

            server_name = server_data.get("name")
            command = server_data.get("command")

            if not server_name or not command:
                raise HTTPException(status_code=400, detail="Server name and command are required")

            # Add MCP server using manager
            result = subprocess.run(
                [sys.executable, manager_path, "add-mcp", server_name, command],
                cwd=toolkit_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Refresh registry
                subprocess.run(
                    [sys.executable, manager_path, "refresh"],
                    cwd=toolkit_dir,
                    capture_output=True,
                    text=True
                )
                return {"message": f"MCP server {server_name} added successfully", "name": server_name}
            else:
                raise HTTPException(status_code=500, detail=result.stderr)

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sessions/{session_id}/toolkit/mcp-servers/{server_name}")
async def update_mcp_server(session_id: str, server_name: str, server_data: dict[str, Any]) -> dict[str, Any]:
    """Update an existing MCP server."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import json
            import os

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            mcp_servers_dir = os.path.join(toolkit_dir, "mcp_servers")
            config_path = os.path.join(mcp_servers_dir, f"{server_name}.json")

            if not os.path.exists(config_path):
                raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

            # Read existing config
            with open(config_path) as f:
                config = json.load(f)

            # Update with new data
            new_name = server_data.get("name", server_name)
            new_command = server_data.get("command", config.get("command"))

            config["name"] = new_name
            config["command"] = new_command

            # If name changed, rename the file
            if new_name != server_name:
                new_config_path = os.path.join(mcp_servers_dir, f"{new_name}.json")
                if os.path.exists(new_config_path):
                    raise HTTPException(status_code=400, detail=f"MCP server '{new_name}' already exists")
                os.rename(config_path, new_config_path)
                config_path = new_config_path

            # Write updated config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            return {"message": "MCP server updated successfully", "name": new_name}

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}/toolkit/mcp-servers/{server_name}")
async def delete_mcp_server(session_id: str, server_name: str) -> dict[str, Any]:
    """Delete an MCP server."""
    try:
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        if hasattr(sandbox, "workspace_root"):
            import json
            import os

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            registry_path = os.path.join(toolkit_dir, "registry.json")

            if os.path.exists(registry_path):
                with open(registry_path, encoding="utf-8") as f:
                    registry = json.load(f)

                # Remove the server from registry
                mcp_servers = registry.get("mcp_servers", [])
                mcp_servers = [s for s in mcp_servers if s.get("name") != server_name]
                registry["mcp_servers"] = mcp_servers

                # Save registry
                with open(registry_path, "w", encoding="utf-8") as f:
                    json.dump(registry, f, indent=2, ensure_ascii=False)

                # Remove config file
                config_path = os.path.join(toolkit_dir, "mcp_servers", f"{server_name}.json")
                if os.path.exists(config_path):
                    os.remove(config_path)

                return {"message": f"MCP server {server_name} deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Registry not found")

        raise HTTPException(status_code=500, detail="Sandbox does not support toolkit")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health & readiness checks (PRD10 §11.8 / Acceptance Gate 14.9)
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe — process is up and HTTP stack is responsive."""
    return {"status": "healthy"}


@app.get("/ready")
async def ready_check() -> dict:
    """Readiness probe — checks dependencies (DB) and reports service info.

    Returns 200 with status=``ready`` when DB is reachable, 503 when not.
    Optional Redis/object-storage checks can be added behind feature flags
    once those services are wired in production deployments.
    """

    from sqlalchemy import text as _text

    from agent_os.common.sentry_setup import get_sentry_state
    from agent_os.db.base import get_engine

    deps: dict = {"db": "unknown"}
    overall_ok = True

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(_text("SELECT 1"))
        deps["db"] = "ok"
    except Exception as exc:  # pragma: no cover - defensive
        deps["db"] = f"down: {exc.__class__.__name__}"
        overall_ok = False

    sentry_state = get_sentry_state()
    deps["sentry"] = "active" if sentry_state.get("enabled") else "disabled"

    payload = {
        "status": "ready" if overall_ok else "not_ready",
        "service": "agent-os",
        "version": "v1",
        "dependencies": deps,
        "observability": {
            "sentry": {
                "enabled": bool(sentry_state.get("enabled")),
                "environment": sentry_state.get("environment"),
                "release": sentry_state.get("release"),
            },
        },
    }
    if not overall_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


# ---------------------------------------------------------------------------
# PRD10 §12.1 — API metrics & P95 monitoring
# ---------------------------------------------------------------------------
#
# Two endpoints expose request latency / throughput data without pulling in
# ``prometheus_client`` as a hard dep:
#
#   * ``GET /metrics``                       — Prometheus exposition text,
#     scraped by Prometheus / Grafana / Victoria-Metrics in production.
#   * ``GET /api/v1/__metrics__/json``       — Human-readable JSON
#     summary with §25.2 latency targets baked in. Useful for ops consoles
#     and the investor demo readout.
#
# Both endpoints are *not* themselves recorded into the registry (recording
# them would create unbounded self-traffic when scrapes run every 10s).
# They also bypass the rate limiter via ``_RATE_LIMIT_BYPASS_PATHS``.
@app.get("/metrics", include_in_schema=False)
async def metrics_prometheus() -> Response:
    """Prometheus exposition text endpoint (PRD10 §12.1)."""

    from agent_os.common.metrics import get_default_metrics

    body = get_default_metrics().to_prometheus_text()
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/v1/__metrics__/json", include_in_schema=False)
async def metrics_json_summary() -> JSONResponse:
    """Operator-facing JSON view of route latency vs §25.2 targets.

    The endpoint is intentionally namespaced under ``__metrics__`` so it
    cannot be confused with a public PRD10 surface. It does not require
    auth on purpose: the per-bucket data is non-sensitive (no user IDs,
    no payload contents, just latency aggregates) and operators on a
    bastion host need to be able to ``curl`` it without minting tokens.
    """

    from agent_os.common.metrics import get_default_metrics

    summary = get_default_metrics().to_json_summary()
    return JSONResponse(content=summary)


# ===== Authentication API =====

# Pydantic models for auth
class UserRegister(BaseModel):
    """User registration request."""
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    """User login request."""
    username: str
    password: str


class AuthResponse(BaseModel):
    """Authentication response."""
    token: str
    user: dict


# Import auth module
try:
    from agent_os.server.auth import UserCreate, UserManager, get_current_user, get_user_manager
    AUTH_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Auth module not available: {e}")
    AUTH_AVAILABLE = False


if AUTH_AVAILABLE:
    @app.post("/api/auth/register", response_model=AuthResponse)
    async def register(user_data: UserRegister):
        """Register a new user."""
        try:
            user_manager = get_user_manager()

            # Create user
            user_create = UserCreate(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password
            )

            user = user_manager.create_user(user_create)

            # Create token
            token = user_manager.create_access_token(user)

            return AuthResponse(
                token=token,
                user={
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "created_at": user.created_at
                }
            )
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


    @app.post("/api/auth/login", response_model=AuthResponse)
    async def login(user_data: UserLogin):
        """Login user."""
        try:
            user_manager = get_user_manager()

            # Authenticate
            user = user_manager.authenticate_user(user_data.username, user_data.password)
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Incorrect username or password"
                )

            # Create token
            token = user_manager.create_access_token(user)

            return AuthResponse(
                token=token,
                user={
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "created_at": user.created_at
                }
            )
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


    @app.get("/api/auth/me")
    async def get_current_user_info(current_user = get_current_user):
        """Get current user info."""
        return {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_guest": current_user.is_guest
        }


# ===== Project Management API =====

class CreateProjectRequest(BaseModel):
    """Create project request."""
    name: str
    description: str = ""
    template: str = "blank"
    features: list[str] = []
    user_id: str = "guest"


@app.post("/api/projects")
async def create_project(project: CreateProjectRequest):
    """Create a new project with template and features."""
    try:
        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())

        # Create session with project name
        session_metadata = SessionMetadata(
            id=session_id,
            name=project.name,
            created_at=asyncio.get_event_loop().time(),
            workspace=f"./data/workspaces/{project.name}",
            last_accessed=asyncio.get_event_loop().time()
        )

        # Store session
        _session_manager._metadata[session_id] = session_metadata
        _session_manager._save_metadata()

        # Initialize sandbox
        sandbox = await _session_manager.get_or_create_sandbox(session_id)

        # Apply template features
        await apply_template(sandbox, project.template, project.features)

        # Add README if description provided
        if project.description:
            readme_content = f"# {project.name}\n\n{project.description}\n\n"
            await sandbox.write_file("README.md", readme_content)

        return {
            "session_id": session_id,
            "name": project.name,
            "message": "Project created successfully"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


async def apply_template(sandbox, template: str, features: list[str]):
    """Apply project template and features."""
    # Apply template
    if template == "python":
        # Create Python project structure
        template_name = "Python"
        structure = {
            "src": "",
            "tests": "",
            ".gitignore": "*.pyc\n__pycache__/\n.venv/\n",
            "main.py": f"# Main entry point\n\ndef main():\n    print('Hello from {template_name} project!')\n\nif __name__ == '__main__':\n    main()\n"
        }

        for path, content in structure.items():
            if path.endswith('/'):
                await sandbox.run_command(f"mkdir -p {path}")
            else:
                await sandbox.write_file(path, content)

    elif template == "webapp":
        # Web app structure
        structure = {
            "backend": "",
            "frontend": "",
            "README.md": "# Web Application\n\nFull-stack web application template.",
            ".gitignore": "node_modules/\n__pycache__/\n*.pyc\nvenv/\n"
        }

        for path, content in structure.items():
            if path.endswith('/'):
                await sandbox.run_command(f"mkdir -p {path}")
            else:
                await sandbox.write_file(path, content)

    # Apply features
    if "git" in features:
        await sandbox.run_command("git init")
        await sandbox.write_file(".gitignore", "*.pyc\n__pycache__/\n.venv/\nnode_modules/\n")

    if "docker" in features:
        dockerfile = """FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
"""
        await sandbox.write_file("Dockerfile", dockerfile)
        await sandbox.write_file("docker-compose.yml", "version: '3'\nservices:\n  app:\n    build: .\n    ports:\n      - '8000:8000'\n")

    if "env" in features:
        await sandbox.write_file(".env", "# Environment variables\nDEBUG=True\n")
        await sandbox.write_file(".env.example", "# Environment variables example\nDEBUG=True\n")

    if "readme" in features:
        readme = f"# {template.capitalize()} Project\n\n## Features\n\n"
        if features:
            readme += "\n".join([f"- {f}" for f in features])
        await sandbox.write_file("README.md", readme)

    if "requirements" in features:
        requirements = "# Project dependencies\nfastapi>=0.100.0\nuvicorn>=0.23.0\n"
        await sandbox.write_file("requirements.txt", requirements)

    if "tests" in features:
        await sandbox.run_command("mkdir -p tests")
        test_file = """import pytest


def test_example():
    assert True
"""
        await sandbox.write_file("tests/test_example.py", test_file)
        await sandbox.write_file("pytest.ini", "[tool:pytest]\ntestpaths = tests\n")
