"""
Tests for job management endpoints.
"""

from unittest.mock import MagicMock


class TestListJobs:
    """Tests for GET /api/jobs."""

    def test_list_jobs_authenticated(self, client, auth_headers, mock_job_store):
        mock_job_store.list_jobs.return_value = []
        response = client.get("/api/jobs", headers=auth_headers)
        assert response.status_code == 200

    def test_list_jobs_unauthenticated(self, client):
        response = client.get("/api/jobs")
        assert response.status_code in (401, 403)


class TestGetJob:
    """Tests for GET /api/jobs/{job_id}."""

    def test_get_existing_job(self, client, auth_headers, mock_job_store):
        mock_job_store.get_job.return_value = {
            "id": "test-123",
            "status": "running",
            "workflow": "moneyprinter",
            "step": "script_generation",
            "progress": 25.0,
            "created_at": "2024-01-01T00:00:00",
        }
        mock_job_store.is_purged.return_value = None
        response = client.get("/api/jobs/test-123", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-123"
        assert data["status"] == "running"

    def test_get_nonexistent_job(self, client, auth_headers, mock_job_store):
        mock_job_store.get_job.return_value = None
        mock_job_store.is_purged.return_value = None
        response = client.get("/api/jobs/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_get_job_unauthenticated(self, client):
        response = client.get("/api/jobs/test-123")
        assert response.status_code in (401, 403)


class TestCancelJob:
    """Tests for POST /api/jobs/{job_id}/cancel."""

    def test_cancel_running_job(self, client, auth_headers, mock_job_store, mock_job_queue):
        mock_job_store.get_job.return_value = {
            "id": "test-123",
            "status": "running",
            "workflow": "moneyprinter",
        }
        mock_job_queue.cancel_job.return_value = True
        response = client.post("/api/jobs/test-123/cancel", headers=auth_headers)
        assert response.status_code == 200

    def test_cancel_nonexistent_job(self, client, auth_headers, mock_job_store):
        mock_job_store.get_job.return_value = None
        response = client.post("/api/jobs/nonexistent/cancel", headers=auth_headers)
        assert response.status_code == 404


class TestDeleteJob:
    """Tests for DELETE /api/jobs/{job_id}."""

    def test_delete_job(self, client, auth_headers, mock_job_store):
        mock_job_store.get_job.return_value = {
            "id": "test-123",
            "status": "done",
            "workflow": "moneyprinter",
        }
        mock_job_store.delete_job.return_value = True
        response = client.delete("/api/jobs/test-123", headers=auth_headers)
        assert response.status_code == 200

    def test_delete_nonexistent_job(self, client, auth_headers, mock_job_store):
        mock_job_store.get_job.return_value = None
        mock_job_store.delete_job.return_value = False
        response = client.delete("/api/jobs/nonexistent", headers=auth_headers)
        assert response.status_code == 404
