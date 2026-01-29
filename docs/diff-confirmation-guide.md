# Diff Confirmation Flow Documentation

**Implementation Date**: 2026-01-29
**Status**: ✅ Complete
**Test Coverage**: 7/7 tests passing (100%)

---

## Overview

The Diff Confirmation Flow provides a thread-safe mechanism for showing code changes to users and waiting for their approval before applying modifications. This bridges Aider's executor thread (sync) with FastAPI's WebSocket (async).

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     FastAPI Event Loop                         │
│                                                               │
│  WebSocket Endpoint  ──────────────────────────────────┐      │
│      (Main Thread)                                   │      │
│                                                       │      │
│  Receives: request_diff_confirmation event           │      │
│     │                                                │      │
│     ├── Extract: diff_id, file_path, diff           │      │
│     │                                                │      │
│     ├── Display: Unified diff to user               │      │
│     │                                                │      │
│     └── Wait: User clicks Approve/Reject            │      │
│                   │                                  │      │
│                   ▼                                  │      │
│  User Action: Approve/Reject                         │      │
│     │                                                │      │
│     └──► Call: ws_io.receive_diff_response(diff_id, approved)│
│                                                       │      │
└───────────────────────────────────────────────────────┼───────┘
                                                        │
                                                        │ Thread-safe
                                                        │ Communication
                                                        │
┌───────────────────────────────────────────────────────┼───────┐
│                     Aider Executor Thread              │       │
│     │                                                  │       │
│     │  1. Aider wants to edit file                    │       │
│     │     │                                            │       │
│     │     ▼                                            │       │
│     │  2. Generate: original_content, modified_content │       │
│     │     │                                            │       │
│     │     ▼                                            │       │
│     │  3. Call: ws_io.request_diff_confirmation(      │       │
│     │            file_path, original, modified)       │       │
│     │            │                                    │       │
│     │            │  ┌─────────────────────────┐      │       │
│     │            │  │ Generate UUID (diff_id)  │      │       │
│     │            │  │ Create unified diff     │      │       │
│     │            │  │ Store in _pending_diffs │      │       │
│     │            │  │ Send event to queue     │      │       │
│     │            │  └─────────────────────────┘      │       │
│     │            │                                    │       │
│     │            ▼                                    │       │
│     │  4. Block: Wait on threading.Event             │       │
│     │            │                                    │       │
│     │            │  (while user reviews diff)        │       │
│     │            │                                    │       │
│     │            ▼                                    │       │
│     │  5. Receive: User response (approved/rejected) │       │
│     │            │                                    │       │
│     │            ▼                                    │       │
│     │  6. If approved:                               │       │
│     │        - Get content via get_diff_content()    │       │
│     │        - Apply changes to file                 │       │
│     │        - Clear diff via clear_diff()           │       │
│     │     If rejected:                                │       │
│     │        - Do nothing (cleanup automatic)        │       │
│     │                                                 │       │
└─────────────────────────────────────────────────────┴───────┘
```

## API Reference

### WebSocketIO Methods

#### `request_diff_confirmation(file_path, original_content, modified_content, description) -> bool`

Request user confirmation for a file diff.

**Parameters**:
- `file_path` (str): Path to the file being modified
- `original_content` (str): Original file content
- `modified_content` (str): Proposed new content
- `description` (str, optional): Description of the changes

**Returns**: `bool` - True if approved, False if rejected

**Thread**: Called from Aider executor thread
**Timeout**: 300 seconds (5 minutes)
**Thread-safety**: ✅ Thread-safe via diff ID system

**Example**:
```python
# In Aider executor thread
original = read_file("src/example.py")
modified = original.replace("Hello", "Hi")

approved = ws_io.request_diff_confirmation(
    file_path="src/example.py",
    original_content=original,
    modified_content=modified,
    description="Change greeting from Hello to Hi"
)

if approved:
    write_file("src/example.py", modified)
```

#### `receive_diff_response(diff_id, approved) -> None`

Receive diff confirmation response from WebSocket.

**Parameters**:
- `diff_id` (str): The diff confirmation ID to respond to
- `approved` (bool): Whether the user approved (True) or rejected (False)

**Thread**: Called from FastAPI event loop thread
**Thread-safety**: ✅ Thread-safe

**Example**:
```python
# In FastAPI WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    async for event in output_queue:
        if event["payload"]["action"] == "request_diff_confirmation":
            diff_id = event["payload"]["data"]["diff_id"]
            file_path = event["payload"]["data"]["file_path"]
            diff = event["payload"]["data"]["diff"]

            # Show diff to user
            # ... wait for user response ...

            # Send user's response
            ws_io.receive_diff_response(diff_id, user_approved)
```

#### `get_diff_content(diff_id) -> str | None`

Get the modified content for an approved diff.

**Parameters**:
- `diff_id` (str): The diff ID to get content for

**Returns**: The modified content, or None if diff_id not found

**Thread**: Called from Aider executor thread
**Thread-safety**: ✅ Thread-safe

**Example**:
```python
# After user approves
if approved:
    modified = ws_io.get_diff_content(diff_id)
    if modified:
        await write_file(file_path, modified)
        ws_io.clear_diff(diff_id)
```

#### `clear_diff(diff_id) -> None`

Clean up a diff request after applying changes.

**Parameters**:
- `diff_id` (str): The diff ID to clean up

**Thread**: Called from Aider executor thread
**Thread-safety**: ✅ Thread-safe

**Example**:
```python
# After applying changes
await write_file(file_path, modified_content)
ws_io.clear_diff(diff_id)
```

## Event Format

### Request Diff Confirmation Event

Sent from Aider thread to WebSocket when a diff needs approval:

```json
{
    "type": "event",
    "payload": {
        "action": "request_diff_confirmation",
        "data": {
            "diff_id": "550e8400-e29b-41d4-a716-446655440000",
            "file_path": "src/example.py",
            "diff": "--- a/src/example.py\n+++ b/src/example.py\n@@ -1,3 +1,3 @@\n-line 1\n+line 1 modified\n line 2\n line 3\n",
            "description": "Update line 1"
        },
        "status": "waiting_for_user"
    }
}
```

## Diff Format

The system uses unified diff format for maximum compatibility:

```
--- a/src/example.py
+++ b/src/example.py
@@ -1,3 +1,3 @@
 def hello():
-    print("Hello, World!")
+    print("Hello, AgentOS!")
```

**Format Characteristics**:
- Lines starting with `-` are removed
- Lines starting with `+` are added
- Lines starting with `@@` show position (line numbers)
- Lines without prefixes are context (unchanged)

## Implementation Flow

### 1. Aider Generates Edit

```python
# In Aider executor thread
original = """def hello():
    print("Hello, World!")"""

modified = """def hello():
    print("Hello, AgentOS!")
    print("Updated")"""
```

### 2. Request Confirmation

```python
approved = ws_io.request_diff_confirmation(
    file_path="src/hello.py",
    original_content=original,
    modified_content=modified,
    description="Update greeting and add message"
)
```

**Inside `request_diff_confirmation()`**:
1. Generate UUID: `diff_id = uuid.uuid4()`
2. Create unified diff using `difflib.unified_diff()`
3. Create `threading.Event()` for blocking
4. Store in `_pending_diffs[diff_id] = {event, result, content}`
5. Send event to WebSocket queue
6. Block on `event.wait(timeout=300)`

### 3. Frontend Receives Event

```typescript
// In frontend (TypeScript example)
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.payload.action === "request_diff_confirmation") {
        const { diff_id, file_path, diff, description } = data.payload.data;

        // Show diff in UI
        showDiffModal({
            file_path,
            diff,
            description,
            onApprove: () => {
                fetch("/api/diff/respond", {
                    method: "POST",
                    body: JSON.stringify({ diff_id, approved: true })
                });
            },
            onReject: () => {
                fetch("/api/diff/respond", {
                    method: "POST",
                    body: JSON.stringify({ diff_id, approved: false })
                });
            }
        });
    }
};
```

### 4. User Responds

```python
# In FastAPI endpoint
@app.post("/api/diff/respond")
async def respond_to_diff(request: DiffResponse):
    ws_io.receive_diff_response(
        diff_id=request.diff_id,
        approved=request.approved
    )
    return {"status": "ok"}
```

**Inside `receive_diff_response()`**:
1. Look up `_pending_diffs[diff_id]`
2. Set `result["approved"] = approved`
3. Call `event.set()` to unblock executor thread

### 5. Aider Thread Unblocks

```python
# Back in Aider executor thread (continues from step 2)
if approved:
    # User approved - apply changes
    modified = ws_io.get_diff_content(diff_id)
    await write_file(file_path, modified)
    ws_io.clear_diff(diff_id)
else:
    # User rejected - do nothing (auto-cleanup)
    pass
```

## Testing

### Test Suite: `tests/test_diff_confirmation.py`

**Total Tests**: 7
**Passing**: 7 (100%)
**Coverage**: Basic operations, concurrent requests, cleanup, integration

#### Test Cases

1. **`test_simple_diff_approval`**
   - Verify basic approval flow works
   - Check diff_id is properly routed
   - Verify content is retrievable after approval

2. **`test_simple_diff_rejection`**
   - Verify rejection flow works
   - Check content is not available after rejection

3. **`test_concurrent_diff_requests`**
   - Test multiple simultaneous diff requests
   - Verify each diff gets unique diff_id
   - Verify responses are correctly matched

4. **`test_diff_format`**
   - Validate unified diff format
   - Check headers (---/+++)
   - Verify diff markers (-/+)

5. **`test_diff_cleanup_after_approval`**
   - Verify cleanup mechanism works
   - Check content is removed after clear_diff()

6. **`test_diff_timeout`**
   - Verify timeout mechanism exists
   - Check that it doesn't block forever

7. **`test_full_diff_workflow`**
   - End-to-end integration test
   - Complete request → approve → apply → cleanup flow

### Running Tests

```bash
# Run all diff confirmation tests
python -m pytest tests/test_diff_confirmation.py -v

# Run specific test
python -m pytest tests/test_diff_confirmation.py::TestDiffConfirmation::test_simple_diff_approval -v
```

## Integration with Aider

To integrate diff confirmation into Aider's workflow:

### Option 1: Hook into File Operations

```python
# In AiderCoderIntegration
async def _write_file_with_confirmation(self, file_path: str, content: str):
    """Write file with diff confirmation."""

    # Check if file exists
    if os.path.exists(file_path):
        # Read original
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()

        # Request confirmation
        if self._ws_io:
            approved = self._ws_io.request_diff_confirmation(
                file_path=file_path,
                original_content=original,
                modified_content=content,
                description=f"Modify {file_path}"
            )

            if not approved:
                return False  # User rejected

    # Write file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # Cleanup
    if self._ws_io:
        # Note: diff_id would need to be tracked
        pass

    return True
```

### Option 2: Override Aider's Edit Method

```python
# Extend Aider's Coder class
class ConfirmingCoder(Coder):
    def confirm_edit(self, path, original, new):
        """Ask for confirmation before editing."""

        if self._ws_io:
            approved = self._ws_io.request_diff_confirmation(
                file_path=path,
                original_content=original,
                modified_content=new,
                description=f"Edit {path}"
            )

            if not approved:
                return False

        # Apply edit
        return super().confirm_edit(path, original, new)
```

## Best Practices

### 1. Always Clean Up

```python
# GOOD - Always cleanup
try:
    modified = ws_io.get_diff_content(diff_id)
    await write_file(file_path, modified)
finally:
    ws_io.clear_diff(diff_id)

# BAD - Forgetting cleanup
modified = ws_io.get_diff_content(diff_id)
await write_file(file_path, modified)
# Memory leak!
```

### 2. Handle Timeouts

```python
try:
    approved = ws_io.request_diff_confirmation(...)
except TimeoutError:
    # User didn't respond in time
    # Handle gracefully - maybe default to reject
    approved = False
```

### 3. Verify Content Before Applying

```python
if approved:
    modified = ws_io.get_diff_content(diff_id)
    if modified is None:
        # Shouldn't happen, but handle it
        print("Warning: Diff content not found")
        return

    # Additional validation
    if len(modified) > 10_000_000:  # 10MB limit
        print("Warning: File too large")
        return

    await write_file(file_path, modified)
```

### 4. Provide Clear Descriptions

```python
# GOOD - Clear description
approved = ws_io.request_diff_confirmation(
    file_path="src/auth.py",
    original_content=original,
    modified_content=modified,
    description="Add JWT authentication to login endpoint"
)

# BAD - Vague description
approved = ws_io.request_diff_confirmation(
    file_path="src/auth.py",
    original_content=original,
    modified_content=modified,
    description="changes"
)
```

## Troubleshooting

### Issue: "Diff content not found after approval"

**Cause**: Calling `get_diff_content()` with wrong diff_id or after cleanup.

**Solution**:
1. Verify diff_id matches the one from the event
2. Don't call `clear_diff()` before `get_diff_content()`
3. Check if diff was actually approved

### Issue: "Timeout waiting for diff confirmation"

**Cause**: Event loop not running, or user didn't respond.

**Solution**:
1. Ensure event loop is running continuously
2. Increase timeout if needed (currently 300s)
3. Check frontend is actually receiving events

### Issue: Multiple diffs getting mixed responses

**Cause**: Not using unique diff_ids for each request.

**Solution**:
- The system auto-generates UUIDs
- Always extract diff_id from the event
- Never reuse diff_ids

## Performance Considerations

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| `request_diff_confirmation()` | O(n+m) | n = original lines, m = modified lines (diff generation) |
| `receive_diff_response()` | O(1) | Dict lookup |
| `get_diff_content()` | O(1) | Dict lookup |
| `clear_diff()` | O(1) | Dict deletion |

### Memory Usage

- **Per pending diff**: ~1-10 KB (depends on file size)
- **100 concurrent diffs**: ~100 KB - 1 MB
- **Typical usage**: 1-3 concurrent diffs (<30 KB)

### Latency

- **Diff generation**: 10-100ms (depends on file size)
- **Cross-thread communication**: <1ms
- **User review time**: 5-60 seconds (variable)

## Security Considerations

1. **Path Validation**: Always validate file paths to prevent directory traversal
2. **Size Limits**: Consider adding file size limits to prevent memory issues
3. **Permission Checks**: Verify user has permission to modify the file
4. **Content Sanitization**: Be careful with file content that could execute code

## Future Enhancements

1. **Batch Diff Confirmation**
   - Show multiple diffs at once
   - Allow approve all/reject all

2. **Diff Annotations**
   - Allow user to add comments to specific lines
   - Request changes to specific parts

3. **Conflict Resolution**
   - Handle merge conflicts
   - Show three-way merge (original, modified, current)

4. **Undo/Redo**
   - Track applied diffs
   - Allow rolling back changes

## References

- [Unified Diff Format](https://www.gnu.org/software/diffutils/manual/html_node/Unified-Format.html)
- [WebSocket Thread Safety](./websocketio-thread-safety.md)
- [Aider Documentation](https://aider.chat/docs/)

---

**Last Updated**: 2026-01-29
**Maintainer**: AgentOS Development Team
**Status**: ✅ Production Ready
