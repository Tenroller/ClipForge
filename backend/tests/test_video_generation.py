"""
Tests for video generation submission endpoints.
"""

from unittest.mock import MagicMock, patch
import uuid


class TestMoneyPrinterGenerate:
    """Tests for POST /api/moneyprinter/generate."""

    def test_submit_moneyprinter_job(self, client, auth_headers, mock_job_store):
        with patch("backend.api.routes.video_generation.get_video_orchestrator") as mock_orch:
            mock_orch.return_value.submit_job.return_value = {
                "job_id": "test-mp-job",
                "status": "queued",
            }
            response = client.post("/api/moneyprinter/generate", headers=auth_headers, json={
                "videoSubject": "Test subject for video generation",
                "aiModel": "gemini-2.0-flash",
                "paragraphNumber": 1,
                "voice": "en_us_001",
            })
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data

    def test_submit_moneyprinter_unauthenticated(self, client):
        response = client.post("/api/moneyprinter/generate", json={
            "videoSubject": "Test subject",
        })
        assert response.status_code in (401, 403)


class TestBrainrotGenerate:
    """Tests for POST /api/brainrot/generate."""

    def test_submit_brainrot_job(self, client, auth_headers, mock_job_store):
        with patch("backend.api.routes.video_generation.get_video_orchestrator") as mock_orch:
            mock_orch.return_value.submit_job.return_value = {
                "job_id": "test-br-job",
                "status": "queued",
            }
            response = client.post("/api/brainrot/generate", headers=auth_headers, json={
                "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "numCompilations": 1,
                "minDuration": 30,
                "maxDuration": 60,
            })
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data

    def test_submit_brainrot_unauthenticated(self, client):
        response = client.post("/api/brainrot/generate", json={
            "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        })
        assert response.status_code in (401, 403)


class TestPodcastClipsGenerate:
    """Tests for POST /api/podcastclips/generate."""

    def test_submit_podcastclips_job(self, client, auth_headers, mock_job_store):
        with patch("backend.api.routes.video_generation.get_video_orchestrator") as mock_orch:
            mock_orch.return_value.submit_job.return_value = {
                "job_id": "test-pc-job",
                "status": "queued",
            }
            response = client.post("/api/podcastclips/generate", headers=auth_headers, json={
                "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "aiModel": "gemini-2.0-flash",
            })
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data

    def test_submit_podcastclips_unauthenticated(self, client):
        response = client.post("/api/podcastclips/generate", json={
            "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        })
        assert response.status_code in (401, 403)


class TestVoices:
    """Tests for GET /api/voices."""

    def test_list_voices(self, client, auth_headers):
        response = client.get("/api/voices", headers=auth_headers)
        # Voices endpoint may or may not require auth
        assert response.status_code in (200, 403)
