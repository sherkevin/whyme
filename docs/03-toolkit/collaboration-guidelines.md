# Frontend/Backend Collaboration Guidelines

**Version**: v1.0.0
**Last Updated**: 2026-01-26
**Target Audience**: Frontend and Backend Developers

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [Separation of Concerns](#separation-of-concerns)
4. [API Contract](#api-contract)
5. [Development Workflow](#development-workflow)
6. [Communication Protocol](#communication-protocol)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Process](#deployment-process)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Overview

### System Architecture

AgentOS Studio follows a **client-server architecture** with clear separation between frontend and backend:

```
┌─────────────────────────────────────────────────┐
│              Frontend (Browser)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Monaco   │  │ File     │  │ Toolkit      │  │
│  │ Editor   │  │ Browser  │  │ Manager      │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│         │              │              │          │
└─────────┼──────────────┼──────────────┼─────────┘
          │              │              │
          ▼              ▼              ▼
┌─────────┴──────────────┴──────────────┴─────────┐
│           Backend (FastAPI Server)               │
│  ┌──────────────┐  ┌──────────┐  ┌────────────┐ │
│  │ REST API     │  │ WebSocket│  │ Session    │ │
│  │ Endpoints    │  │ Handler  │  │ Manager    │ │
│  └──────────────┘  └──────────┘  └────────────┘ │
│         │                 │              │        │
│         ▼                 ▼              ▼        │
│  ┌──────────────┐  ┌──────────┐  ┌────────────┐ │
│  │ File System  │  │ Agent    │  │ Toolkit    │ │
│  │ Operations   │  │ Engine   │  │ Manager    │ │
│  └──────────────┘  └──────────┘  └────────────┘ │
└──────────────────────────────────────────────────┘
```

### Technology Stack

**Frontend**:
- Pure JavaScript (ES6+)
- Monaco Editor (code editing)
- CSS3 with CSS Variables
- WebSocket API (real-time communication)
- Fetch API (HTTP requests)

**Backend**:
- Python 3.11+
- FastAPI (web framework)
- WebSocket (real-time communication)
- Docker/Local Sandbox (code execution)
- Aider (AI-powered coding)

---

## Architecture Principles

### 1. Stateless Backend

- **Principle**: Backend should not maintain UI state
- **Implementation**: All state managed by frontend
- **Benefit**: Easy scaling, simpler debugging

**Example**:
```javascript
// ❌ BAD: Backend stores UI state
POST /api/state { "selectedFile": "main.py" }

// ✅ GOOD: Frontend manages state
const state = { selectedFile: "main.py" };
```

---

### 2. RESTful API Design

- **Principle**: Use appropriate HTTP methods
- **Implementation**:
  - GET: Retrieve data
  - POST: Create resources
  - PUT: Update resources
  - DELETE: Remove resources

**Example**:
```
GET    /api/sessions/{id}/toolkit/skills      → List skills
POST   /api/sessions/{id}/toolkit/skills      → Create skill
PUT    /api/sessions/{id}/toolkit/skills/{n}  → Update skill
DELETE /api/sessions/{id}/toolkit/skills/{n}  → Delete skill
```

---

### 3. WebSocket for Real-Time Updates

- **Principle**: Use WebSocket for AI chat and progress updates
- **Implementation**: Single WebSocket connection per session
- **Protocol**: JSON-based message format

**Example**:
```javascript
const ws = new WebSocket('ws://localhost:8003/ws/chat/{session_id}');

// Send user message
ws.send(JSON.stringify({
  type: 'input',
  payload: { text: 'Create a Python app' }
}));

// Receive AI response
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.payload.action === 'chat_response') {
    displayMessage(data.payload.data.content);
  }
};
```

---

### 4. Secure by Default

- **Principle**: Validate and sanitize all inputs
- **Implementation**:
  - Path traversal protection
  - File type validation
  - Command injection prevention
  - Size limits

**Example**:
```python
# Backend: sanitize_path function
def sanitize_path(user_path: str, workspace_root: str) -> str:
    """Prevent path traversal attacks"""
    full_path = os.path.abspath(os.path.join(workspace_root, user_path))
    if not full_path.startswith(os.path.abspath(workspace_root)):
        raise ValueError("Path traversal detected")
    return full_path
```

---

## Separation of Concerns

### Frontend Responsibilities

**UI/UX**:
- ✅ Display file tree and code editor
- ✅ Handle user interactions (clicks, edits, uploads)
- ✅ Show progress indicators and loading states
- ✅ Display AI chat messages
- ✅ Manage modals and dialogs

**State Management**:
- ✅ Track current session
- ✅ Track open files and editors
- ✅ Track selected toolkit items
- ✅ Manage UI state (modals, panels, etc.)

**Data Fetching**:
- ✅ Call REST API endpoints
- ✅ Handle WebSocket messages
- ✅ Cache responses when appropriate
- ✅ Display errors to users

**Security**:
- ✅ Validate user input before sending
- ✅ Sanitize file paths
- ✅ Check file types on upload
- ❌ **NOT**: Trust backend responses blindly

---

### Backend Responsibilities

**Business Logic**:
- ✅ Execute AI agent logic
- ✅ Manage file operations
- ✅ Handle toolkit registration
- ✅ Execute code in sandbox

**Data Persistence**:
- ✅ Store session metadata
- ✅ Save files to disk
- ✅ Maintain toolkit registry
- ✅ Manage sandbox lifecycle

**Security**:
- ✅ Validate all inputs
- ✅ Sanitize file paths
- ✅ Isolate code execution
- ✅ Prevent resource abuse

**API Contract**:
- ✅ Return consistent JSON responses
- ✅ Use appropriate HTTP status codes
- ✅ Provide meaningful error messages
- ❌ **NOT**: Generate UI or HTML

---

### What Frontend Should NOT Do

❌ **Execute code directly**
```javascript
// BAD: Frontend tries to execute Python
eval(pythonCode);

// GOOD: Let backend handle it
ws.send(JSON.stringify({ type: 'input', payload: { text: pythonCode } }));
```

❌ **Access file system directly**
```javascript
// BAD: Frontend tries to read files
fs.readFile('/path/to/file');

// GOOD: Use API
fetch(`/api/sessions/${id}/files/content?path=${filePath}`);
```

❌ **Store business logic**
```javascript
// BAD: Frontend validates business rules
function isSkillValid(skill) { /* complex validation */ }

// GOOD: Backend validates
POST /api/sessions/${id}/toolkit/skills → Backend validates
```

---

### What Backend Should NOT Do

❌ **Generate UI**
```python
# BAD: Backend returns HTML
return HTMLResponse(content="<div>Hello</div>")

# GOOD: Backend returns JSON
return {"message": "Hello"}
```

❌ **Store UI state**
```python
# BAD: Backend tracks which file is selected
sessions[session_id].selected_file = "main.py"

# GOOD: Frontend tracks this
const selectedFile = "main.py";
```

❌ **Make UI decisions**
```python
# BAD: Backend says "show modal"
return {"action": "show_modal", "modal_type": "edit"}

# GOOD: Frontend decides when to show modals
if (userClicksEditButton) { showModal('edit'); }
```

---

## API Contract

### API Versioning

**Current Version**: v1.0.0

**Versioning Strategy**:
- URL path versioning: `/api/v1/...`
- Backward compatibility maintained for minor versions
- Breaking changes only in major versions

**Current URLs** (no version prefix):
```
/api/sessions
/api/sessions/{id}/files
/api/sessions/{id}/toolkit
```

**Future URLs** (with version prefix):
```
/api/v1/sessions
/api/v1/sessions/{id}/files
/api/v1/sessions/{id}/toolkit
```

---

### Request Format

**REST API**:
```http
POST /api/sessions/{id}/toolkit/skills
Content-Type: application/json

{
  "name": "my_skill"
}
```

**WebSocket**:
```json
{
  "type": "input",
  "payload": {
    "text": "Create a Python app",
    "command": "execute"
  }
}
```

---

### Response Format

**Success Response** (2xx):
```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed"
}
```

**Error Response** (4xx/5xx):
```json
{
  "detail": "Human-readable error message"
}
```

**WebSocket Event**:
```json
{
  "type": "event",
  "payload": {
    "action": "log",
    "status": "executing",
    "message": "Creating file..."
  }
}
```

---

### HTTP Status Codes

| Code | Meaning | Frontend Action |
|------|---------|-----------------|
| 200 | OK | Display success, use data |
| 201 | Created | Show confirmation, update UI |
| 400 | Bad Request | Show error to user, check input |
| 401 | Unauthorized | Redirect to login |
| 404 | Not Found | Show "not found" message |
| 500 | Server Error | Show generic error, log details |

---

### Error Handling

**Backend**:
```python
@app.post("/api/sessions/{id}/toolkit/skills")
async def create_skill(id: str, skill_data: dict):
    try:
        # Validate input
        if not skill_data.get("name"):
            raise HTTPException(
                status_code=400,
                detail="Skill name is required"
            )

        # Create skill
        manager.create_skill(skill_data["name"])
        return {"message": "Skill created", "name": skill_data["name"]}

    except Exception as e:
        # Log error
        logger.error(f"Failed to create skill: {e}")
        # Return user-friendly message
        raise HTTPException(
            status_code=500,
            detail="Failed to create skill. Please try again."
        )
```

**Frontend**:
```javascript
async function createSkill(sessionId, skillName) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}/toolkit/skills`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: skillName })
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail);
    }

    const data = await res.json();
    showSuccess(data.message);
    return data;

  } catch (err) {
    console.error('Failed to create skill:', err);
    showError(err.message);
    throw err;
  }
}
```

---

## Development Workflow

### 1. Feature Development

**Step 1: API Contract Definition**
- Backend defines API endpoints
- Document request/response formats
- Specify error cases

**Example Contract**:
```
Endpoint: POST /api/sessions/{id}/toolkit/skills
Request: { "name": "string" }
Response (200): { "message": "string", "name": "string" }
Error (400): { "detail": "Skill name is required" }
```

---

**Step 2: Parallel Development**

**Backend Team**:
1. Implement API endpoint
2. Add input validation
3. Write unit tests
4. Update API documentation

**Frontend Team**:
1. Create UI components
2. Implement API client functions
3. Add loading states
4. Handle errors
5. Use mock data for testing

---

**Step 3: Integration**

1. Frontend uses real API instead of mocks
2. Both teams test integration
3. Fix bugs and edge cases
4. Update documentation

---

### 2. API Changes

**Breaking Changes** (requires coordination):
1. Backend team proposes change
2. Discuss with frontend team
3. Agree on timeline
4. Backend implements new version
5. Frontend migrates to new version
6. Old version deprecated

**Non-Breaking Changes**:
- Backend implements independently
- Update documentation
- Frontend adopts when ready

---

### 3. Testing Workflow

**Unit Testing**:
- Backend: Test each endpoint independently
- Frontend: Test UI components with mock API

**Integration Testing**:
- Test real API calls
- Verify request/response formats
- Test error cases

**End-to-End Testing**:
- Test complete user flows
- Verify frontend-backend communication

---

## Communication Protocol

### 1. Channel Selection

**Use REST API for**:
- File operations (read, write, delete)
- Session management
- Toolkit management (CRUD operations)

**Use WebSocket for**:
- AI chat messages
- Real-time progress updates
- Tool execution status
- Streaming responses

---

### 2. Message Flow

**REST API Flow**:
```
Frontend → HTTP Request → Backend → Process → HTTP Response → Frontend
```

**WebSocket Flow**:
```
Frontend → WebSocket Message → Backend → Process → WebSocket Event → Frontend
                                  ↓
                            (Async Processing)
                                  ↓
                            WebSocket Event → Frontend
```

---

### 3. Error Communication

**Backend → Frontend**:
```json
{
  "detail": "Specific error message",
  "code": "ERROR_CODE",
  "timestamp": 1706227200.0
}
```

**Frontend → User**:
```javascript
function showError(error) {
  // Map error codes to user-friendly messages
  const messages = {
    'FILE_NOT_FOUND': 'The file you requested does not exist.',
    'INVALID_INPUT': 'Please check your input and try again.',
    'SERVER_ERROR': 'Something went wrong. Please try again later.'
  };

  const userMessage = messages[error.code] || error.detail;
  alert(userMessage);
}
```

---

## Testing Strategy

### Backend Testing

**Unit Tests** (pytest):
```python
def test_create_skill():
    manager = ToolkitManager(workspace)
    manager.add_skill("test", "# Test code")
    assert "test" in manager.list_skills()

def test_create_skill_duplicate():
    manager = ToolkitManager(workspace)
    manager.add_skill("test", "# Code")
    with pytest.raises(FileExistsError):
        manager.add_skill("test", "# New code")
```

**Integration Tests**:
```python
def test_api_create_skill(client):
    res = client.post("/api/sessions/123/toolkit/skills", json={
        "name": "test_skill"
    })
    assert res.status_code == 200
    assert res.json()["name"] == "test_skill"
```

---

### Frontend Testing

**Component Tests** (with mocks):
```javascript
describe('ToolkitPanel', () => {
  it('displays skills list', async () => {
    // Mock API response
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          skills: [
            { name: 'calculator', description: 'Math tool' }
          ]
        })
      })
    );

    // Render component
    const panel = new ToolkitPanel();
    await panel.loadSkills();

    // Assert
    expect(panel.skills).toHaveLength(1);
    expect(panel.skills[0].name).toBe('calculator');
  });
});
```

---

### Integration Tests

**End-to-End** (Playwright/Cypress):
```javascript
test('create and edit skill', async ({ page }) => {
  // Navigate to toolkit
  await page.goto(`http://localhost:8003/?session=${sessionId}`);
  await page.click('[data-testid="toolkit-panel"]');

  // Create skill
  await page.click('button:has-text("New Skill")');
  await page.fill('input[name="skill-name"]', 'my_skill');
  await page.press('input[name="skill-name"]', 'Enter');

  // Verify created
  await expect(page.locator('text=my_skill')).toBeVisible();

  // Edit skill
  await page.click('button:has-text("Edit")');
  await page.fill('.monaco-editor', 'print("hello")');
  await page.press('body', 'Control+S');

  // Verify saved
  await expect(page.locator('text=Skill saved')).toBeVisible();
});
```

---

## Deployment Process

### 1. Development Environment

**Backend**:
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your settings

# Run development server
uvicorn src.agent_os.server.app:app --reload --port 8003
```

**Frontend**:
```bash
# Backend serves static files from src/agent_os/server/static/
# No separate frontend build needed

# For development with hot reload:
# 1. Run backend server
# 2. Open http://localhost:8003 in browser
# 3. Browser will auto-refresh on file changes
```

---

### 2. Staging Environment

**Backend**:
```bash
# Build Docker image
docker build -t agentos:staging .

# Run staging container
docker run -d \
  -p 8003:8003 \
  -e API_KEY=staging_key \
  -e SANDBOX_MODE=docker \
  --name agentos-staging \
  agentos:staging
```

**Frontend**:
- Same as production (static files served by backend)

---

### 3. Production Environment

**Backend**:
```bash
# Using Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Or Kubernetes
kubectl apply -f k8s/
```

**Frontend**:
- Static files served by FastAPI
- CDN for static assets (optional)

---

### 4. Deployment Checklist

**Before Deploy**:
- [ ] All tests pass
- [ ] API documentation updated
- [ ] Error handling tested
- [ ] Performance optimized
- [ ] Security reviewed

**After Deploy**:
- [ ] Smoke tests pass
- [ ] Monitoring configured
- [ ] Error tracking enabled
- [ ] Backup plan ready

---

## Troubleshooting

### Common Issues

#### 1. CORS Errors

**Symptom**: Browser blocks API requests

**Solution**: Backend must allow frontend origin
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

#### 2. WebSocket Connection Drops

**Symptom**: WebSocket disconnects randomly

**Backend Check**:
```python
# Check for unhandled exceptions
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket, session_id):
    try:
        await websocket.accept()
        # ... handle connection
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011)
```

**Frontend Check**:
```javascript
ws.onclose = (event) => {
  console.log('WebSocket closed:', event.code, event.reason);
  // Implement reconnection logic
  setTimeout(() => reconnect(), 3000);
};
```

---

#### 3. File Upload Fails

**Symptom**: Large file uploads fail

**Backend Check**:
```python
# Increase upload size limit
app = FastAPI(max_upload_size=10_000_000)  # 10MB
```

**Frontend Check**:
```javascript
// Check file size before upload
function validateFileSize(file, maxSizeMB = 10) {
  if (file.size > maxSizeMB * 1024 * 1024) {
    alert('File too large. Max size: 10MB');
    return false;
  }
  return true;
}
```

---

#### 4. State Inconsistency

**Symptom**: Frontend shows stale data

**Solution**: Implement refresh mechanism
```javascript
// After updates, refresh data
async function updateSkill(sessionId, skillName, code) {
  await fetch(`/api/sessions/${sessionId}/toolkit/skills/${skillName}`, {
    method: 'PUT',
    body: JSON.stringify({ code })
  });

  // Refresh to get latest state
  await refreshSkills(sessionId);
}
```

---

## Best Practices

### Backend Best Practices

1. **Return Consistent Response Format**
```python
# Always return JSON
return {"message": "Success", "data": {...}}

# Never return HTML
return HTMLResponse(...)  # ❌ Avoid
```

2. **Use HTTP Status Codes Correctly**
```python
# 200: Success
return {"message": "Success"}

# 201: Created
return {"message": "Created"}, 201

# 400: Bad Request
raise HTTPException(status_code=400, detail="Invalid input")

# 404: Not Found
raise HTTPException(status_code=404, detail="Resource not found")

# 500: Server Error
raise HTTPException(status_code=500, detail="Internal error")
```

3. **Validate All Inputs**
```python
@app.post("/api/sessions/{id}/toolkit/skills")
async def create_skill(id: str, skill_data: dict):
    # Validate required fields
    if not skill_data.get("name"):
        raise HTTPException(status_code=400, detail="Name required")

    # Sanitize input
    name = sanitize_skill_name(skill_data["name"])

    # Process
    create_skill_safe(name)
```

4. **Log Everything**
```python
import logging

logger = logging.getLogger(__name__)

@app.post("/api/endpoint")
async def endpoint():
    logger.info("Processing request")
    try:
        # ... process
        logger.info("Request completed successfully")
    except Exception as e:
        logger.error(f"Request failed: {e}", exc_info=True)
        raise
```

---

### Frontend Best Practices

1. **Handle All Errors**
```javascript
async function apiCall(url, options) {
  try {
    const res = await fetch(url, options);
    if (!res.ok) throw await res.json();
    return await res.json();
  } catch (err) {
    showError(err.detail || 'Request failed');
    throw err;
  }
}
```

2. **Show Loading States**
```javascript
async function loadSkills() {
  setLoading(true);
  try {
    const skills = await fetchSkills();
    displaySkills(skills);
  } finally {
    setLoading(false);
  }
}
```

3. **Debounce User Input**
```javascript
function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

const searchSkills = debounce(async (query) => {
  const results = await fetch(`/api/skills?search=${query}`);
  displayResults(results);
}, 300);
```

4. **Cache Responses**
```javascript
const cache = new Map();

async function getFile(path) {
  if (cache.has(path)) {
    return cache.get(path);
  }

  const content = await fetch(`/api/files?path=${path}`)
    .then(res => res.json());

  cache.set(path, content);
  return content;
}
```

---

### Communication Best Practices

1. **Daily Standup** (15 min)
   - Backend: What APIs are ready?
   - Frontend: What UI needs backend support?
   - Blockers and dependencies

2. **API Review** (weekly)
   - Review new API endpoints
   - Discuss breaking changes
   - Update documentation

3. **Integration Testing** (before release)
   - Test all user flows
   - Verify error handling
   - Performance testing

---

## Support

### Contact Points

**Backend Team**:
- **Lead**: backend-lead@agentos.com
- **Slack**: #backend-dev
- **Office Hours**: Mon/Wed 2-4 PM

**Frontend Team**:
- **Lead**: frontend-lead@agentos.com
- **Slack**: #frontend-dev
- **Office Hours**: Tue/Thu 2-4 PM

**API Documentation**:
- **URL**: http://localhost:8003/docs
- **Reference**: `/docs/03-toolkit/api-reference.md`

---

## Conclusion

Following these collaboration guidelines ensures:

✅ **Clear separation of concerns**
✅ **Maintainable codebase**
✅ **Smooth development workflow**
✅ **Reliable deployments**
✅ **Happy teams!**

Remember: Communication is key. When in doubt, ask!

---

**Last Updated**: 2026-01-26
**Version**: 1.0
**Maintained By**: AgentOS Development Team
