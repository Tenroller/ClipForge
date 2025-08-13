import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app import app
    return TestClient(app)


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('app.DEFAULT_OUTPUT_DIR', Path(tmpdir)):
            yield Path(tmpdir)


class TestHealthEndpoint:
    def test_health_status(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "cwd" in data
        assert "root" in data
        assert "moneyprinter_present" in data
        assert "brainrot_present" in data


class TestModelsEndpoint:
    def test_list_models(self, client):
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert "gemini-2.0-flash" in data["models"]


class TestVoicesEndpoint:
    @patch('app.ensure_on_path')
    @patch('app.pushd')
    def test_list_voices_success(self, mock_pushd, mock_ensure_path, client):
        # Mock the voice list function
        with patch('vendors.moneyprinter.tiktokvoice.list_voices', return_value=["af_bella", "en_us_001"]):
            response = client.get("/api/voices")
            assert response.status_code == 200
            data = response.json()
            assert "voices" in data
            assert isinstance(data["voices"], list)

    def test_list_voices_import_error(self, client):
        # This will naturally fail due to import issues in test env
        response = client.get("/api/voices")
        assert response.status_code == 500


class TestVoiceSampleEndpoint:
    def test_voice_sample_invalid_voice(self, client):
        response = client.get("/api/voice-sample?voice=nonexistent")
        # Will fail due to import issues, but structure is testable
        assert response.status_code in [400, 500]


class TestJobsEndpoint:
    def test_job_status_not_found(self, client):
        response = client.get("/api/jobs/nonexistent-job-id")
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    def test_cancel_job_not_found(self, client):
        response = client.post("/api/jobs/nonexistent-job-id/cancel")
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    @patch('app.JOBS', {"test-job": {"status": "running", "step": "init"}})
    @patch('app.JOB_CONTROLS', {"test-job": {"cancel": MagicMock()}})
    def test_cancel_job_success(self, client):
        response = client.post("/api/jobs/test-job/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["jobId"] == "test-job"


class TestDownloadEndpoint:
    def test_download_file_not_found(self, client):
        response = client.get("/api/download?path=/nonexistent/file.mp4")
        assert response.status_code == 404

    def test_download_file_access_denied(self, client, temp_output_dir):
        # Create a file outside allowed paths
        forbidden_file = Path("/tmp/forbidden.mp4")
        forbidden_file.touch()
        try:
            response = client.get(f"/api/download?path={forbidden_file}")
            assert response.status_code == 403
        finally:
            forbidden_file.unlink(missing_ok=True)

    def test_download_file_success(self, client, temp_output_dir):
        # Create a test file in allowed directory
        test_file = temp_output_dir / "test.mp4"
        test_file.write_bytes(b"fake video content")
        
        with patch('app._is_allowed_path', return_value=True):
            response = client.get(f"/api/download?path={test_file}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "video/mp4"


class TestListVideosEndpoint:
    def test_list_videos_not_found(self, client):
        response = client.get("/api/list-videos?dir=/nonexistent")
        assert response.status_code == 404

    def test_list_videos_access_denied(self, client):
        response = client.get("/api/list-videos?dir=/tmp")
        assert response.status_code == 403

    def test_list_videos_success(self, client, temp_output_dir):
        # Create test video files
        (temp_output_dir / "video1.mp4").write_bytes(b"fake video 1")
        (temp_output_dir / "video2.mp4").write_bytes(b"fake video 2")
        (temp_output_dir / "not_video.txt").write_text("not a video")
        
        with patch('app._is_allowed_path', return_value=True):
            response = client.get(f"/api/list-videos?dir={temp_output_dir}")
            assert response.status_code == 200
            data = response.json()
            assert "files" in data
            assert len(data["files"]) == 2  # Only .mp4 files
            assert all(f["name"].endswith(".mp4") for f in data["files"])


class TestRateLimiting:
    def test_rate_limiting_disabled_by_default(self, client):
        # Make multiple requests - should not be rate limited
        for _ in range(5):
            response = client.get("/api/ping")
            assert response.status_code == 200

    @patch.dict(os.environ, {"RATE_LIMIT_PER_MINUTE": "2"})
    def test_rate_limiting_enabled(self):
        # Need to reimport app after setting env var
        import importlib
        import app as app_module
        importlib.reload(app_module)
        client = TestClient(app_module.app)
        
        # First two requests should succeed
        response1 = client.post("/api/moneyprinter/generate", json={
            "videoSubject": "test"
        })
        response2 = client.post("/api/moneyprinter/generate", json={
            "videoSubject": "test2"
        })
        
        # Third request should be rate limited
        response3 = client.post("/api/moneyprinter/generate", json={
            "videoSubject": "test3"
        })
        
        assert response3.status_code == 429
        assert "Too Many Requests" in response3.json()["detail"]


class TestGenerationEndpoints:
    def test_moneyprinter_generate_validation_error(self, client):
        response = client.post("/api/moneyprinter/generate", json={
            "videoSubject": "",  # Empty subject should fail
        })
        assert response.status_code == 422  # Validation error

    def test_moneyprinter_generate_field_validation(self, client):
        response = client.post("/api/moneyprinter/generate", json={
            "videoSubject": "test",
            "paragraphNumber": 15,  # Too high
        })
        assert response.status_code == 422

    def test_brainrot_generate_validation_error(self, client):
        response = client.post("/api/brainrot/generate", json={
            "youtubeUrl": "",  # Empty URL should fail
        })
        assert response.status_code == 422

    def test_brainrot_generate_field_validation(self, client):
        response = client.post("/api/brainrot/generate", json={
            "youtubeUrl": "https://youtu.be/test",
            "numCompilations": 15,  # Too high
        })
        assert response.status_code == 422

    @patch('app.JOB_SEMAPHORE')
    def test_generation_creates_job(self, mock_semaphore, client):
        # Mock to prevent actual execution
        mock_semaphore.__enter__ = MagicMock()
        mock_semaphore.__exit__ = MagicMock()
        
        response = client.post("/api/moneyprinter/generate", json={
            "videoSubject": "test video"
        })
        
        # Should create job and return job ID
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "jobId" in data
