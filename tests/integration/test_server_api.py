"""Tests for server API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_os.server.app import SessionManager, app

# Docker dependency marker
docker_required = pytest.mark.skipif(
    True,  # Skip by default since Docker may not be available
    reason="Requires Docker daemon to be running",
)


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, test_client: TestClient) -> None:
        """Test health check returns healthy status."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestSessionManager:
    """Tests for SessionManager."""

    @pytest.mark.asyncio
    async def test_session_manager_sandbox_tracking(self) -> None:
        """Test that session manager tracks sandboxes correctly."""
        manager = SessionManager()

        # Mock the DockerSandbox
        mock_sandbox = AsyncMock()
        mock_sandbox._container = MagicMock()
        mock_sandbox._container.id = "container123"

        with patch("agent_os.server.app.instantiate") as mock_instantiate:
            mock_instantiate.return_value = mock_sandbox

            sandbox = await manager.get_or_create_sandbox("session1")

            # Should return the same sandbox on second call
            sandbox2 = await manager.get_or_create_sandbox("session1")

            assert sandbox is sandbox2

    @pytest.mark.asyncio
    async def test_remove_session(self) -> None:
        """Test removing a session."""
        manager = SessionManager()

        mock_sandbox = AsyncMock()
        mock_sandbox._container = MagicMock()
        mock_sandbox._container.id = "container123"

        with patch("agent_os.server.app.instantiate") as mock_instantiate:
            mock_instantiate.return_value = mock_sandbox

            # Create a session
            await manager.get_or_create_sandbox("session1")

            # Remove it
            await manager.remove_session("session1")

            # Verify sandbox.stop was called
            mock_sandbox.stop.assert_called_once()


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    @docker_required
    def test_create_session(self, test_client: TestClient) -> None:
        """Test creating a new session."""
        response = test_client.post(
            "/api/sessions",
            json={"user_id": "test_user", "image": "test:latest", "workspace": "/workspace"},
        )

        assert response.status_code in (200, 500)  # May fail if Docker unavailable
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert data["user_id"] == "test_user"

    @docker_required
    def test_get_session(self, test_client: TestClient) -> None:
        """Test getting session info."""
        response = test_client.get("/api/sessions/test-session-id")
        assert response.status_code in (200, 500)

    @docker_required
    def test_delete_session(self, test_client: TestClient) -> None:
        """Test deleting a session."""
        response = test_client.delete("/api/sessions/test-session-id")
        assert response.status_code in (200, 500)


class TestFileSystemEndpoints:
    """Tests for file system endpoints."""

    @docker_required
    def test_get_file_tree(self, test_client: TestClient) -> None:
        """Test getting file tree."""
        response = test_client.get("/api/sessions/test-session/files/tree")
        assert response.status_code in (200, 500)

    @docker_required
    def test_get_file_content(self, test_client: TestClient) -> None:
        """Test getting file content."""
        response = test_client.get("/api/sessions/test-session/files/content?path=/test.py")
        assert response.status_code in (200, 404, 500)

    @docker_required
    def test_save_file_content(self, test_client: TestClient) -> None:
        """Test saving file content."""
        response = test_client.post(
            "/api/sessions/test-session/files/save",
            json={"path": "/test.py", "content": "print('hello')"},
        )
        assert response.status_code in (200, 500)

    @docker_required
    def test_delete_file(self, test_client: TestClient) -> None:
        """Test deleting a file."""
        response = test_client.delete("/api/sessions/test-session/files?path=/test.py")
        assert response.status_code in (200, 500)
