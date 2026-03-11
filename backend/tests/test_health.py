"""
Tests for health and system endpoints.
"""


class TestHealth:
    """Tests for health check endpoints."""

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
