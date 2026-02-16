"""AgentOS FastAPI application with WebSocket and REST API endpoints."""

from __future__ import annotations

import asyncio
from typing import Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from agent_os.core.types import RuntimeContext
from agent_os.sandbox.docker_impl import DockerSandbox
from agent_os.core.config import instantiate, load_class, Config, load_config
from agent_os.agent_legacy import Agent
from agent_os.agent_aider import AiderAgent
from agent_os.core.interfaces import AgentCallbackHandler
from agent_os.server.security import sanitize_path, validate_filename
from agent_os.auth.router import router as auth_router
from agent_os.inbox.router import router as inbox_router
from agent_os.today.router import router as today_router
from agent_os.knowledge.router import router as knowledge_router
from agent_os.tasks.router import router as tasks_router
from agent_os.aggregation.router import router as aggregation_router
from agent_os.conversations.router import router as conversations_router
from agent_os.stage3.router import router as stage3_router
from agent_os.search_engine.router import router as stage4_router
from agent_os.connections.router import router as connections_router
# Import agent_router later to avoid circular import issues

app = FastAPI(
    title="AgentOS API",
    description="AgentOS - AI-powered development environment with knowledge management",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    from agent_os.db.base import get_engine, init_db
    get_engine()  # Initialize engine and session factory
    await init_db()  # Create tables

# Include API routers
app.include_router(auth_router)
app.include_router(inbox_router)
app.include_router(today_router)
app.include_router(knowledge_router)
app.include_router(tasks_router)
app.include_router(aggregation_router)
app.include_router(conversations_router)
app.include_router(stage3_router)
app.include_router(stage4_router)
app.include_router(connections_router)


# Startup event to initialize database
@app.on_event("startup")
async def startup_event():
    """Initialize database engine on startup."""
    from agent_os.db.base import get_engine, init_db
    import logging

    # Initialize database engine
    get_engine()
    logging.info("Database engine initialized")

    # Create database tables
    try:
        await init_db()
        logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Failed to create database tables: {e}")
        # Don't fail startup if table creation fails


# Import and include agent router after app creation
# to avoid circular import issues with the agent package
try:
    from agent_os.agent.router import router as agent_router
    app.include_router(agent_router)
except Exception as e:
    # If agent router fails to import, log but don't crash
    import logging
    logging.warning(f"Failed to import agent router: {e}")


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
        self._diff_services: dict[str, "DiffService"] = {}
        self._output_queues: dict[str, asyncio.Queue] = {}
        self._event_loops: dict[str, asyncio.AbstractEventLoop] = {}
        self._lock = asyncio.Lock()
        
        # Persistence
        self._metadata: dict[str, SessionMetadata] = {}
        self._storage_path = Path("data/sessions.json")
        self._load_metadata()

        # Default configuration
        self.sandbox_provider = "agent_os.sandbox.docker_impl.DockerSandbox"
        
        import os
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
                from agent_os.core.config import Config, LLMConfig, AgentConfig, MemoryConfig, ContextConfig
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
                f.write(f"AiderAgent created successfully\n")

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
    ) -> "DiffService":
        """Get or create a diff service for the given session."""
        async with self._lock:
            if session_id not in self._diff_services:
                from agent_os.server.diff_service import DiffService
                self._diff_services[session_id] = DiffService(session_id, output_queue, loop)
                self._output_queues[session_id] = output_queue
                self._event_loops[session_id] = loop
            return self._diff_services[session_id]

    def get_diff_service(self, session_id: str) -> "DiffService | None":
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
    import sys
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
    debug_msg3 = f"[DEBUG WS] Creating output queue..."
    print(debug_msg3, flush=True)
    with open("ws_debug.log", "a", encoding="utf-8") as f:
        f.write(debug_msg3 + "\n")

    output_queue = asyncio.Queue()

    debug_msg4 = f"[DEBUG WS] Getting event loop..."
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
            f.write(f"[DEBUG WS] Agent created/retrieved successfully\n")
        print(f"[DEBUG WS] Agent created/retrieved successfully", flush=True)

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
    import uuid
    import re
    
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


from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import os

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
async def get_index() -> HTMLResponse:
    """Serve the index page."""
    index_file = STATIC_DIR / "index.html"

    # Debug: print the path we're trying to load
    print(f"[DEBUG] Loading index.html from: {index_file}")
    print(f"[DEBUG] Index file exists: {index_file.exists()}")

    if not index_file.exists():
        # Fallback: try to find the file anywhere
        import glob
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
            import os
            import json

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            registry_path = os.path.join(toolkit_dir, "registry.json")

            if os.path.exists(registry_path):
                with open(registry_path, "r", encoding="utf-8") as f:
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
                with open(skill_path, "r", encoding="utf-8") as f:
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
            import os
            import json

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            registry_path = os.path.join(toolkit_dir, "registry.json")

            if os.path.exists(registry_path):
                with open(registry_path, "r", encoding="utf-8") as f:
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
            import os
            import json

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            mcp_servers_dir = os.path.join(toolkit_dir, "mcp_servers")
            config_path = os.path.join(mcp_servers_dir, f"{server_name}.json")

            if not os.path.exists(config_path):
                raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

            # Read existing config
            with open(config_path, 'r') as f:
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

            return {"message": f"MCP server updated successfully", "name": new_name}

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
            import os
            import json

            toolkit_dir = os.path.join(sandbox.workspace_root, "toolkit")
            registry_path = os.path.join(toolkit_dir, "registry.json")

            if os.path.exists(registry_path):
                with open(registry_path, "r", encoding="utf-8") as f:
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


# Health check
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


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
    from agent_os.server.auth import (
        get_user_manager,
        UserCreate,
        UserManager,
        get_current_user
    )
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
