# AgentOS Studio - Test Suite

**Last Updated**: 2026-01-26

---

## 📁 Test Structure

This directory contains all test files organized by test type:

```
tests/
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for component interactions
├── e2e/              # End-to-end tests for complete workflows
├── temp/             # Temporary/miscellaneous test files
└── README.md         # This file
```

---

## 🧪 Test Categories

### 1. Unit Tests (`unit/`)

**Purpose**: Test individual components in isolation

**Tests**:
- `test_config.py` - Configuration system tests
- `test_context_manager.py` - Context management tests
- `test_llm_provider.py` - LLM provider integration tests
- `test_memory_provider.py` - Memory storage tests
- `test_tool_registry.py` - Tool registration tests

**Running Unit Tests**:
```bash
# Run all unit tests
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_config.py

# Run with coverage
pytest tests/unit/ --cov=src/agent_os --cov-report=html
```

---

### 2. Integration Tests (`integration/`)

**Purpose**: Test interactions between multiple components

**Tests**:
- `test_aider_adapter.py` - Aider coding adapter tests
- `test_diff_service.py` - Diff service tests
- `test_server_api.py` - REST API integration tests
- `test_websocket_io.py` - WebSocket communication tests
- `test_full_aider_adapter.py` - Complete Aider workflow tests

**Running Integration Tests**:
```bash
# Run all integration tests
pytest tests/integration/

# Run specific test
pytest tests/integration/test_server_api.py

# Run with verbose output
pytest tests/integration/ -v
```

---

### 3. End-to-End Tests (`e2e/`)

**Purpose**: Test complete user workflows

**Tests**:
- `test_e2e_flow.py` - Complete session creation and chat flow
- `test_advanced_strategies.py` - Complex multi-step scenarios
- `test_final_verification.py` - Final system verification
- `test_simple_parity.py` - Simple parity tests

**Running E2E Tests**:
```bash
# Run all e2e tests
pytest tests/e2e/

# Run with live server
pytest tests/e2e/ --live-server

# Run with browser automation
pytest tests/e2e/ --headed
```

---

### 4. Temporary Tests (`temp/`)

**Purpose**: Miscellaneous and temporary test files

**Tests**:
- `test_import.py` - Import validation tests
- `test_delete.py` - Delete operation tests
- `test_guess_modify.py` - Modification detection tests

**Note**: These tests are kept for reference and may be moved to appropriate categories or removed in future updates.

**Running Temp Tests**:
```bash
# Run temp tests
pytest tests/temp/
```

---

## 🚀 Running All Tests

### Run All Tests
```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=src/agent_os --cov-report=html

# Run with verbose output
pytest tests/ -v

# Run with detailed output
pytest tests/ -vv
```

### Run by Category
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# E2E tests only
pytest tests/e2e/

# Temp tests only
pytest tests/temp/

# Exclude temp tests
pytest tests/ --ignore=tests/temp/
```

### Run Specific Tests
```bash
# By file name
pytest tests/unit/test_config.py

# By test function name
pytest tests/unit/test_config.py::test_load_config

# By class name
pytest tests/integration/test_server_api.py::TestServerAPI

# By keyword/markers
pytest tests/ -m "not slow"
```

---

## 📊 Test Coverage

Generate coverage report:

```bash
# HTML coverage report
pytest tests/ --cov=src/agent_os --cov-report=html
open htmlcov/index.html

# Terminal coverage report
pytest tests/ --cov=src/agent_os --cov-report=term-missing

# Combined coverage
pytest tests/ --cov=src/agent_os --cov-report=html --cov-report=term-missing
```

---

## 🔧 Test Configuration

### pytest.ini

Create `pytest.ini` in project root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow-running tests
    requires_network: Tests requiring network access
```

---

## 📝 Writing New Tests

### Unit Test Example

```python
# tests/unit/test_my_component.py
import pytest
from agent_os.core.component import MyComponent

def test_component_initialization():
    """Test that component initializes correctly"""
    component = MyComponent(config={"key": "value"})
    assert component.config["key"] == "value"

def test_component_method():
    """Test component method"""
    component = MyComponent()
    result = component.method("input")
    assert result == "expected_output"
```

### Integration Test Example

```python
# tests/integration/test_workflow.py
import pytest
from agent_os.server.app import app
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)

def test_create_session(client):
    """Test session creation workflow"""
    response = client.post("/api/sessions", json={
        "name": "Test Project",
        "user_id": "test_user"
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
```

### E2E Test Example

```python
# tests/e2e/test_complete_workflow.py
import pytest
from playwright.sync_api import Page

def test_full_workflow(page: Page):
    """Test complete user workflow"""
    # Navigate to application
    page.goto("http://localhost:8003")

    # Create project
    page.click('button:has-text("New Project")')
    page.fill('input[name="name"]', 'E2E Test Project')
    page.click('button:has-text("Create")')

    # Chat with AI
    page.fill('textarea[placeholder="Message AI"]', 'Create a hello world script')
    page.click('button:has-text("Send")')

    # Verify response
    page.wait_for_selector('text=hello_world.py')
    assert page.locator('text=hello_world.py').is_visible()
```

---

## 🐛 Debugging Tests

### Run with PDB Debugger
```bash
# Drop into debugger on failure
pytest tests/unit/test_config.py --pdb

# Drop into debugger on error
pytest tests/unit/test_config.py --pdb -e
```

### Print Debugging
```bash
# Show print statements
pytest tests/unit/test_config.py -s

# Show local variables on failure
pytest tests/unit/test_config.py -l
```

### Stop on First Failure
```bash
pytest tests/ -x
```

---

## ⚠️ Test Markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_component():
    pass

@pytest.mark.integration
def test_api():
    pass

@pytest.mark.e2e
@pytest.mark.slow
def test_full_workflow():
    pass

@pytest.mark.requires_network
def test_external_api():
    pass
```

Run tests by marker:
```bash
# Run only unit tests
pytest tests/ -m unit

# Run only fast tests
pytest tests/ -m "not slow"

# Run tests requiring network
pytest tests/ -m requires_network
```

---

## 📋 Pre-Commit Checklist

Before committing code, ensure:

- [ ] All unit tests pass: `pytest tests/unit/`
- [ ] All integration tests pass: `pytest tests/integration/`
- [ ] Coverage is above 80%: `pytest tests/ --cov`
- [ ] No test is skipped without reason
- [ ] New code has corresponding tests

---

## 🔄 Continuous Integration

Tests run automatically on:
- Every pull request
- Every commit to main branch
- Daily scheduled runs

View results at: [CI/CD Pipeline](https://github.com/your-org/agent-os/actions)

---

## 📞 Getting Help

**Test Failures?**
1. Check error output carefully
2. Run with `-vv` for detailed output
3. Use `--pdb` to debug interactively
4. Check logs in `tests/fixtures/logs/`

**Need Examples?**
- See existing test files in each category
- Check `tests/fixtures/` for test data
- Review [API Documentation](../docs/03-toolkit/api-reference.md)

---

**Last Updated**: 2026-01-26
**Test Framework**: pytest 7.0+
**Python Version**: 3.11+
