"""
Pytest configuration and shared fixtures for backend tests.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Set test environment variables BEFORE any app imports
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["AUTH_PASSWORD"] = "testpassword123"
os.environ["AUTH_USERNAME"] = "admin"
os.environ["PEXELS_API_KEY"] = "test-pexels-key"
os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
os.environ["TESTING"] = "1"


def _make_mock_user_store():
    """Create a mock user store that doesn't need a real database."""
    store = MagicMock()
    store.verify_credentials = MagicMock(
        side_effect=lambda u, p: u == "admin" and p == "testpassword123"
    )
    store.get_user_info = MagicMock(
        side_effect=lambda u: {"username": "admin", "role": "admin", "id": "test-id"} if u == "admin" else None
    )
    store.create_user = MagicMock(return_value={"username": "newuser", "role": "user", "id": "new-id"})
    store.list_users = MagicMock(return_value=[{"username": "admin", "role": "admin", "id": "test-id"}])
    return store


@pytest.fixture(scope="session")
def mock_job_store():
    """Create a mock job store that doesn't need a real database."""
    store = MagicMock()
    store.create_job = MagicMock(return_value=None)
    store.get_job = MagicMock(return_value=None)
    store.list_jobs = MagicMock(return_value=[])
    store.update_job = MagicMock(return_value=None)
    store.delete_job = MagicMock(return_value=True)
    store.get_stats = MagicMock(return_value={"total": 0})
    store.is_purged = MagicMock(return_value=None)
    store.search_videos = MagicMock(return_value={"videos": [], "total": 0, "offset": 0, "limit": 20})
    return store


@pytest.fixture(scope="session")
def mock_job_queue():
    """Create a mock job queue."""
    queue = MagicMock()
    queue.running = False
    queue.start_worker = MagicMock()
    queue.submit_job = MagicMock(return_value="test-job-id")
    queue.cancel_job = MagicMock(return_value=True)
    queue.get_queue_status = MagicMock(return_value={"queued": 0, "running": 0})
    return queue


@pytest.fixture()
def app(mock_job_store, mock_job_queue):
    """Create a test FastAPI application with mocked dependencies."""
    mock_user = _make_mock_user_store()

    with patch("backend.database.get_job_store", return_value=mock_job_store), \
         patch("backend.job_queue_unified.get_job_queue", return_value=mock_job_queue), \
         patch.dict(os.environ, {"RATE_LIMIT_PER_MINUTE": "0"}):

        # Import and patch user_store before creating the app
        import backend.utils.auth as auth_module
        original_store = auth_module.user_store
        auth_module.user_store = mock_user

        from backend.core.app_factory import create_app
        from backend.core.config import AppConfig

        # Also patch in routes module after it's imported
        import backend.api.routes.auth as auth_routes
        auth_routes.user_store = mock_user

        config = AppConfig.from_env()
        test_app = create_app(config=config)

        yield test_app

        # Restore
        auth_module.user_store = original_store
        auth_routes.user_store = original_store


@pytest.fixture()
def client(app):
    """Create a test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture()
def auth_token(client):
    """Get a valid authentication token."""
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "testpassword123",
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def auth_headers(auth_token):
    """Get authorization headers with a valid token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture()
def mock_user_store():
    """Expose mock user store for test assertions."""
    return _make_mock_user_store()
