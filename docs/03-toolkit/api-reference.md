# AgentOS Backend API - Complete Reference

**Version**: v1.0.0
**Last Updated**: 2026-01-26
**Target Audience**: Frontend Developers

---

## 📋 Table of Contents

1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Session Management](#session-management)
4. [File Operations](#file-operations)
5. [Toolkit Management](#toolkit-management)
6. [WebSocket Communication](#websocket-communication)
7. [Project Management](#project-management)
8. [Error Handling](#error-handling)
9. [Rate Limiting](#rate-limiting)
10. [Examples](#examples)

---

## API Overview

### Base URL
```
http://localhost:8003
```

### API Architecture
- **Protocol**: HTTP/1.1
- **Data Format**: JSON
- **Character Encoding**: UTF-8
- **Transport**: REST + WebSocket

### Response Format

All API responses follow this structure:

**Success Response** (2xx):
```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

**Error Response** (4xx/5xx):
```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required |
| 404 | Not Found | Resource not found |
| 500 | Internal Server Error | Server error |

---

## Authentication

**Status**: ✅ Implemented (Optional)

### Register User

```http
POST /api/auth/register
Content-Type: application/json
```

**Request Body**:
```json
{
  "username": "string (required, min 3 chars)",
  "email": "string (required, valid email)",
  "password": "string (required, min 6 chars)"
}
```

**Response** (200):
```json
{
  "token": "jwt_token_string",
  "user": {
    "id": "user_id",
    "username": "username",
    "email": "user@example.com",
    "created_at": 1706227200.0
  }
}
```

**Error Response** (400/500):
```json
{
  "detail": "Registration failed: Username already exists"
}
```

**Example**:
```javascript
const res = await fetch('http://localhost:8003/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'alice',
    email: 'alice@example.com',
    password: 'securepass123'
  })
});
const data = await res.json();
console.log(data.token); // Use for authenticated requests
```

---

### Login User

```http
POST /api/auth/login
Content-Type: application/json
```

**Request Body**:
```json
{
  "username": "string (required)",
  "password": "string (required)"
}
```

**Response** (200):
```json
{
  "token": "jwt_token_string",
  "user": {
    "id": "user_id",
    "username": "username",
    "email": "user@example.com",
    "created_at": 1706227200.0
  }
}
```

**Error Response** (401):
```json
{
  "detail": "Incorrect username or password"
}
```

**Example**:
```javascript
const res = await fetch('http://localhost:8003/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'alice',
    password: 'securepass123'
  })
});
const data = await res.json();
localStorage.setItem('token', data.token); // Store token
```

---

### Get Current User

```http
GET /api/auth/me
Authorization: Bearer {token}
```

**Response** (200):
```json
{
  "id": "user_id",
  "username": "username",
  "email": "user@example.com",
  "is_guest": false
}
```

---

## Session Management

### List All Sessions

```http
GET /api/sessions
```

**Response** (200):
```json
[
  {
    "id": "session_uuid",
    "name": "My Project",
    "created_at": 1706227200.0,
    "workspace": "./data/workspaces/my_project_session",
    "last_accessed": 1706230800.0
  }
]
```

**Example**:
```javascript
const res = await fetch('http://localhost:8003/api/sessions');
const sessions = await res.json();
sessions.forEach(session => {
  console.log(`${session.name}: ${session.id}`);
});
```

---

### Create Session

```http
POST /api/sessions
Content-Type: application/json
```

**Request Body**:
```json
{
  "user_id": "string (optional, default: 'default_user')",
  "image": "string (optional, default: 'agentos/aider-runtime:latest')",
  "name": "string (optional, default: 'Untitled Project')",
  "workspace": "string (optional, auto-generated if empty)"
}
```

**Response** (200):
```json
{
  "session_id": "session_uuid",
  "user_id": "default_user",
  "sandbox_id": "container_id_or_local",
  "name": "My Project",
  "status": "active"
}
```

**Example**:
```javascript
const res = await fetch('http://localhost:8003/api/sessions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'My AI Project',
    user_id: 'user123'
  })
});
const data = await res.json();
console.log('Created session:', data.session_id);
```

---

### Get Session Info

```http
GET /api/sessions/{session_id}
```

**Response** (200):
```json
{
  "session_id": "session_uuid",
  "user_id": "default_user",
  "sandbox_id": "container_id_or_local",
  "name": "My Project",
  "status": "active"
}
```

**Error Response** (500):
```json
{
  "detail": "Session not found or failed to initialize"
}
```

---

### Delete Session

```http
DELETE /api/sessions/{session_id}
```

**Response** (200):
```json
{
  "message": "Session {session_id} deleted"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}`, {
  method: 'DELETE'
});
const data = await res.json();
console.log(data.message);
```

---

## File Operations

### List Files

```http
GET /api/sessions/{session_id}/files
```

**Query Parameters**:
- `path` (optional): Directory path to list (default: ".")

**Response** (200):
```json
{
  "files": [
    {
      "name": "main.py",
      "path": "main.py",
      "type": "file"
    },
    {
      "name": "src",
      "path": "src",
      "type": "directory"
    }
  ]
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/files?path=src`);
const data = await res.json();
console.log('Files in src:', data.files);
```

---

### Get File Tree

```http
GET /api/sessions/{session_id}/files/tree
```

**Query Parameters**:
- `path` (optional): Root path for tree (default: "")

**Response** (200):
```json
{
  "name": "workspace",
  "path": "/",
  "type": "directory",
  "children": [
    {
      "name": "src",
      "path": "src",
      "type": "directory",
      "children": []
    },
    {
      "name": "main.py",
      "path": "main.py",
      "type": "file"
    }
  ]
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/files/tree`);
const tree = await res.json();
renderFileTree(tree); // Custom function to render tree
```

---

### Get File Content

```http
GET /api/sessions/{session_id}/files/content?path={file_path}
```

**Query Parameters**:
- `path` (required): Path to file

**Response** (200):
```json
{
  "path": "main.py",
  "content": "#!/usr/bin/env python3\nprint('Hello World')\n"
}
```

**Error Response** (404):
```json
{
  "detail": "File not found: main.py"
}
```

**Security**: Path is sanitized to prevent traversal attacks.

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/files/content?path=main.py`);
const data = await res.json();
monacoEditor.setValue(data.content); // Load into Monaco Editor
```

---

### Write File

```http
POST /api/sessions/{session_id}/files
Content-Type: application/json
```

**Request Body**:
```json
{
  "path": "main.py",
  "content": "#!/usr/bin/env python3\nprint('Hello World')\n"
}
```

**Response** (200):
```json
{
  "status": "ok"
}
```

**Security**: Path is sanitized to prevent traversal attacks.

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/files`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: 'src/utils.py',
    content: 'def helper():\n    pass\n'
  })
});
console.log('File saved');
```

---

### Save File Content

```http
POST /api/sessions/{session_id}/files/save
Content-Type: application/json
```

**Request Body**:
```json
{
  "path": "main.py",
  "content": "#!/usr/bin/env python3\nprint('Updated')\n"
}
```

**Response** (200):
```json
{
  "status": "success",
  "path": "main.py"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/files/save`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: 'config.yaml',
    content: monacoEditor.getValue()
  })
});
const data = await res.json();
if (data.status === 'success') {
  console.log('Saved successfully');
}
```

---

### Delete File

```http
DELETE /api/sessions/{session_id}/files?path={file_path}
```

**Query Parameters**:
- `path` (required): Path to file or directory

**Response** (200):
```json
{
  "message": "File main.py deleted"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/files?path=old_file.py`, {
  method: 'DELETE'
});
const data = await res.json();
console.log(data.message);
```

---

## Toolkit Management

### Skills API

#### List All Skills

```http
GET /api/sessions/{session_id}/toolkit/skills
```

**Response** (200):
```json
{
  "skills": [
    {
      "name": "calculator",
      "description": "Calculator Skill - 安全的数学计算器",
      "file": "toolkit/bins/calculator.py",
      "enabled": true
    },
    {
      "name": "weather",
      "description": "Weather Skill - 获取天气信息",
      "file": "toolkit/bins/weather.py",
      "enabled": true
    }
  ]
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills`);
const data = await res.json();
data.skills.forEach(skill => {
  console.log(`${skill.name}: ${skill.description}`);
});
```

---

#### Get Skill Code

```http
GET /api/sessions/{session_id}/toolkit/skills/{skill_name}
```

**Response** (200):
```json
{
  "name": "calculator",
  "code": "#!/usr/bin/env python3\n\"\"\"Calculator Skill\"\"\"\n\ndef add(a, b):\n    return a + b\n",
  "path": "bins/calculator.py"
}
```

**Error Response** (404):
```json
{
  "detail": "Skill calculator not found"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills/calculator`);
const data = await res.json();
// Load skill code into editor
monacoEditor.setValue(data.code);
```

---

#### Create Skill

```http
POST /api/sessions/{session_id}/toolkit/skills
Content-Type: application/json
```

**Request Body**:
```json
{
  "name": "my_skill"
}
```

**Response** (200):
```json
{
  "message": "Skill my_skill created successfully",
  "name": "my_skill"
}
```

**Error Response** (400):
```json
{
  "detail": "Skill name is required"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'translator' })
});
const data = await res.json();
console.log(data.message);
```

---

#### Update Skill Code

```http
PUT /api/sessions/{session_id}/toolkit/skills/{skill_name}
Content-Type: application/json
```

**Request Body**:
```json
{
  "code": "#!/usr/bin/env python3\n\"\"\"Updated skill\"\"\"\n\ndef new_function():\n    pass\n"
}
```

**Response** (200):
```json
{
  "message": "Skill translator updated successfully",
  "name": "translator"
}
```

**Error Response** (400):
```json
{
  "detail": "Code is required"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills/translator`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code: monacoEditor.getValue()
  })
});
const data = await res.json();
if (data.message.includes('successfully')) {
  console.log('Skill saved');
}
```

---

#### Delete Skill

```http
DELETE /api/sessions/{session_id}/toolkit/skills/{skill_name}
```

**Response** (200):
```json
{
  "message": "Skill translator deleted successfully"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills/translator`, {
  method: 'DELETE'
});
const data = await res.json();
console.log(data.message);
```

---

### MCP Servers API

#### List All MCP Servers

```http
GET /api/sessions/{session_id}/toolkit/mcp-servers
```

**Response** (200):
```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx -y @modelcontextprotocol/server-filesystem /tmp",
      "description": "MCP Server: filesystem",
      "tools": []
    }
  ]
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/mcp-servers`);
const data = await res.json();
data.mcp_servers.forEach(server => {
  console.log(`${server.name}: ${server.command}`);
});
```

---

#### Add MCP Server

```http
POST /api/sessions/{session_id}/toolkit/mcp-servers
Content-Type: application/json
```

**Request Body**:
```json
{
  "name": "filesystem",
  "command": "npx -y @modelcontextprotocol/server-filesystem /tmp"
}
```

**Response** (200):
```json
{
  "message": "MCP server filesystem added successfully",
  "name": "filesystem"
}
```

**Error Response** (400):
```json
{
  "detail": "Server name and command are required"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/mcp-servers`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'database',
    command: 'npx -y @modelcontextprotocol/server-postgres postgres://localhost/db'
  })
});
const data = await res.json();
console.log(data.message);
```

---

#### Update MCP Server

```http
PUT /api/sessions/{session_id}/toolkit/mcp-servers/{server_name}
Content-Type: application/json
```

**Request Body**:
```json
{
  "name": "filesystem",
  "command": "npx -y @modelcontextprotocol/server-filesystem /data"
}
```

**Response** (200):
```json
{
  "message": "MCP server updated successfully",
  "name": "filesystem"
}
```

**Error Responses**:
- 404: `{"detail": "MCP server 'filesystem' not found"}`
- 400: `{"detail": "MCP server 'new_name' already exists"}` (if renaming to existing name)

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/mcp-servers/filesystem`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'filesystem',
    command: 'npx -y @modelcontextprotocol/server-filesystem /new/path'
  })
});
const data = await res.json();
console.log(data.message);
```

---

#### Delete MCP Server

```http
DELETE /api/sessions/{session_id}/toolkit/mcp-servers/{server_name}
```

**Response** (200):
```json
{
  "message": "MCP server filesystem deleted successfully"
}
```

**Example**:
```javascript
const res = await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/mcp-servers/filesystem`, {
  method: 'DELETE'
});
const data = await res.json();
console.log(data.message);
```

---

## WebSocket Communication

### WebSocket Endpoint

```http
WS /ws/chat/{session_id}
```

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8003/ws/chat/${sessionId}');

ws.onopen = () => {
  console.log('WebSocket connected');
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket disconnected');
};
```

---

### Message Protocol

All WebSocket messages follow this JSON structure:

```json
{
  "type": "event|input|error",
  "payload": { ... }
}
```

---

### Client → Server Messages

#### Plain Text Chat (Simple)

```json
"Create a Python web application"
```

#### Structured Input

```json
{
  "type": "input",
  "payload": {
    "text": "Create a web app",
    "command": "execute"
  }
}
```

#### Diff Approval/Rejection

```json
{
  "type": "input",
  "payload": {
    "command": "approve",
    "diff_id": "diff_123"
  }
}
```

or

```json
{
  "type": "input",
  "payload": {
    "command": "reject",
    "diff_id": "diff_123"
  }
}
```

---

### Server → Client Messages

#### System Message

```json
{
  "type": "event",
  "payload": {
    "action": "system",
    "message": "Connected to Agent. Ready to help."
  }
}
```

#### Log Message

```json
{
  "type": "event",
  "payload": {
    "action": "log",
    "status": "executing",
    "message": "Creating file main.py..."
  }
}
```

#### Tool Start

```json
{
  "type": "event",
  "payload": {
    "action": "tool_start",
    "status": "executing",
    "data": {
      "tool": "write_file",
      "args": {
        "path": "main.py",
        "content": "..."
      }
    }
  }
}
```

#### Tool End

```json
{
  "type": "event",
  "payload": {
    "action": "tool_end",
    "status": "executing",
    "data": {
      "tool": "write_file",
      "result": "File created successfully"
    }
  }
}
```

#### Chat Response

```json
{
  "type": "event",
  "payload": {
    "action": "chat_response",
    "status": "waiting_for_user",
    "data": {
      "content": "I've created the Python application for you..."
    }
  }
}
```

#### Status Change

```json
{
  "type": "event",
  "payload": {
    "action": "status_change",
    "status": "thinking"
  }
}
```

#### Error

```json
{
  "type": "error",
  "payload": {
    "message": "Failed to create file: Permission denied"
  }
}
```

---

### Complete WebSocket Example

```javascript
const sessionId = 'your_session_id';
const ws = new WebSocket(`ws://localhost:8003/ws/chat/${sessionId}`);

// Handle incoming messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'event':
      handleEvent(data.payload);
      break;
    case 'error':
      handleError(data.payload);
      break;
  }
};

function handleEvent(payload) {
  switch(payload.action) {
    case 'system':
      console.log('System:', payload.message);
      break;
    case 'log':
      appendLog(payload.message);
      break;
    case 'tool_start':
      showToolProgress(payload.data.tool, 'running');
      break;
    case 'tool_end':
      showToolProgress(payload.data.tool, 'completed');
      break;
    case 'chat_response':
      displayResponse(payload.data.content);
      break;
  }
}

function handleError(payload) {
  console.error('Error:', payload.message);
  showUserMessage('error', payload.message);
}

// Send message to server
function sendMessage(text) {
  ws.send(JSON.stringify({
    type: 'input',
    payload: {
      text: text,
      command: 'execute'
    }
  }));
}

// Approve a diff
function approveDiff(diffId) {
  ws.send(JSON.stringify({
    type: 'input',
    payload: {
      command: 'approve',
      diff_id: diffId
    }
  }));
}

// Reject a diff
function rejectDiff(diffId) {
  ws.send(JSON.stringify({
    type: 'input',
    payload: {
      command: 'reject',
      diff_id: diffId
    }
  }));
}
```

---

## Project Management

### Create Project

```http
POST /api/projects
Content-Type: application/json
```

**Request Body**:
```json
{
  "name": "My Web App",
  "description": "A full-stack web application",
  "template": "webapp",
  "features": ["git", "docker", "env", "readme"],
  "user_id": "user123"
}
```

**Available Templates**:
- `blank` - Empty project
- `python` - Python project structure
- `webapp` - Full-stack web application

**Available Features**:
- `git` - Initialize Git repository
- `docker` - Add Dockerfile and docker-compose.yml
- `env` - Add .env and .env.example files
- `readme` - Add README.md
- `requirements` - Add requirements.txt
- `tests` - Add test structure with pytest

**Response** (200):
```json
{
  "session_id": "project_session_uuid",
  "name": "My Web App",
  "message": "Project created successfully"
}
```

**Example**:
```javascript
const res = await fetch('http://localhost:8003/api/projects', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'Python API',
    description: 'REST API with FastAPI',
    template: 'python',
    features: ['git', 'docker', 'requirements', 'tests'],
    user_id: 'user123'
  })
});
const data = await res.json();
console.log('Project created:', data.session_id);
```

---

## Health Check

```http
GET /health
```

**Response** (200):
```json
{
  "status": "healthy"
}
```

---

## Error Handling

### Error Response Format

All errors return JSON with a `detail` field:

```json
{
  "detail": "Human-readable error message"
}
```

### Common Errors

#### 400 Bad Request
```json
{
  "detail": "Skill name is required"
}
```

#### 404 Not Found
```json
{
  "detail": "Skill calculator not found"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Sandbox does not support toolkit"
}
```

### Handling Errors in JavaScript

```javascript
async function apiCall(url, options) {
  try {
    const res = await fetch(url, options);

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Request failed');
    }

    return await res.json();
  } catch (err) {
    console.error('API Error:', err.message);
    showUserMessage('error', err.message);
    throw err;
  }
}

// Usage
apiCall(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'my_skill' })
})
.then(data => console.log('Success:', data))
.catch(err => console.error('Failed:', err));
```

---

## Rate Limiting

**Current Status**: Not implemented (planned for future)

When implemented, rate limits will be communicated via HTTP headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1706230800
```

---

## Examples

### Complete File Operations Workflow

```javascript
const sessionId = 'your_session_id';

// 1. List files
const files = await fetch(`http://localhost:8003/api/sessions/${sessionId}/files/tree`)
  .then(res => res.json());

// 2. Read file content
const fileContent = await fetch(
  `http://localhost:8003/api/sessions/${sessionId}/files/content?path=main.py`
).then(res => res.json());

// 3. Edit in Monaco Editor
monaco.editor.create(document.getElementById('editor'), {
  value: fileContent.content,
  language: 'python'
});

// 4. Save changes
await fetch(`http://localhost:8003/api/sessions/${sessionId}/files/save`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: 'main.py',
    content: monacoEditor.getValue()
  })
});

// 5. Delete file
await fetch(
  `http://localhost:8003/api/sessions/${sessionId}/files?path=old.py`,
  { method: 'DELETE' }
);
```

---

### Complete Toolkit Workflow

```javascript
const sessionId = 'your_session_id';

// 1. Create a new skill
await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'my_calculator' })
});

// 2. Update skill code
await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/skills/my_calculator`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code: `#!/usr/bin/env python3
"""Calculator Skill"""

def calculate(expression):
    try:
        return eval(expression)
    except:
        return "Error"

if __name__ == "__main__":
    import sys
    print(calculate(" ".join(sys.argv[1:])))
`
  })
});

// 3. List all skills
const skills = await fetch(
  `http://localhost:8003/api/sessions/${sessionId}/toolkit/skills`
).then(res => res.json());

// 4. Add MCP server
await fetch(`http://localhost:8003/api/sessions/${sessionId}/toolkit/mcp-servers`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'filesystem',
    command: 'npx -y @modelcontextprotocol/server-filesystem /tmp'
  })
});

// 5. List MCP servers
const mcpServers = await fetch(
  `http://localhost:8003/api/sessions/${sessionId}/toolkit/mcp-servers`
).then(res => res.json());

// 6. Delete skill
await fetch(
  `http://localhost:8003/api/sessions/${sessionId}/toolkit/skills/my_calculator`,
  { method: 'DELETE' }
);
```

---

### WebSocket Chat Integration

```javascript
class AgentOSClient {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.ws = null;
    this.messageHandlers = [];
  }

  connect() {
    this.ws = new WebSocket(`ws://localhost:8003/ws/chat/${this.sessionId}`);

    this.ws.onopen = () => {
      console.log('Connected to AgentOS');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.messageHandlers.forEach(handler => handler(data));
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Disconnected from AgentOS');
    };
  }

  onMessage(handler) {
    this.messageHandlers.push(handler);
  }

  sendChat(text) {
    this.ws.send(JSON.stringify({
      type: 'input',
      payload: {
        text: text,
        command: 'execute'
      }
    }));
  }

  approveDiff(diffId) {
    this.ws.send(JSON.stringify({
      type: 'input',
      payload: {
        command: 'approve',
        diff_id: diffId
      }
    }));
  }

  disconnect() {
    this.ws.close();
  }
}

// Usage
const client = new AgentOSClient('session_id');
client.connect();

client.onMessage((data) => {
  if (data.type === 'event') {
    switch(data.payload.action) {
      case 'log':
        console.log('[LOG]', data.payload.message);
        break;
      case 'chat_response':
        console.log('[AI]', data.payload.data.content);
        break;
    }
  }
});

client.sendChat('Create a Python Flask app');
```

---

## Best Practices

### 1. Always Use HTTPS in Production

```javascript
const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.agentos.com'
  : 'http://localhost:8003';
```

### 2. Handle All Errors

```javascript
async function safeApiCall(url, options) {
  try {
    const res = await fetch(url, options);
    if (!res.ok) throw await res.json();
    return await res.json();
  } catch (error) {
    reportError(error);
    return null;
  }
}
```

### 3. Use Request Timeouts

```javascript
async function fetchWithTimeout(url, options, timeout = 30000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
}
```

### 4. Retry Failed Requests

```javascript
async function fetchWithRetry(url, options, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, options);
      if (res.ok) return await res.json();
    } catch (error) {
      if (i === retries - 1) throw error;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}
```

### 5. Sanitize User Input

```javascript
function sanitizePath(path) {
  // Remove any ../ or similar patterns
  return path.replace(/\.\./g, '').replace(/^\//, '');
}
```

---

## Support

For questions or issues:
- **GitHub Issues**: [AgentOS/Issues](https://github.com/your-org/agent-os/issues)
- **Documentation**: [Full Docs](https://docs.agentos.com)
- **Email**: support@agentos.com

---

**Last Updated**: 2026-01-26
**API Version**: v1.0.0
**Maintained By**: AgentOS Backend Team
