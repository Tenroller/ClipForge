"""
Tests for authentication endpoints.
"""


class TestLogin:
    """Tests for POST /api/auth/login (CSRF-exempt)."""

    def test_login_valid_credentials(self, client):
        response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "testpassword123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["user"]["username"] == "admin"

    def test_login_wrong_password(self, client):
        response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong-password",
        })
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_wrong_username(self, client):
        response = client.post("/api/auth/login", json={
            "username": "nonexistent-user",
            "password": "testpassword123",
        })
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 422  # Validation error


class TestVerify:
    """Tests for GET /api/auth/verify."""

    def test_verify_valid_token(self, client, auth_headers):
        response = client.get("/api/auth/verify", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user"]["username"] == "admin"

    def test_verify_invalid_token(self, client):
        response = client.get("/api/auth/verify", headers={
            "Authorization": "Bearer invalid-token-here",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_verify_no_token(self, client):
        response = client.get("/api/auth/verify")
        assert response.status_code == 403


class TestMe:
    """Tests for GET /api/auth/me."""

    def test_me_authenticated(self, client, auth_headers):
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "role" in data

    def test_me_unauthenticated(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 403

    def test_me_invalid_token(self, client):
        response = client.get("/api/auth/me", headers={
            "Authorization": "Bearer garbage-token",
        })
        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/auth/logout (requires CSRF token)."""

    def test_logout_authenticated(self, client, auth_headers):
        # First get a CSRF token by making any request
        csrf_response = client.get("/api/auth/me", headers=auth_headers)
        csrf_token = csrf_response.cookies.get("csrf_token", "")
        headers = {**auth_headers, "X-CSRF-Token": csrf_token}
        response = client.post("/api/auth/logout", headers=headers, cookies={"csrf_token": csrf_token})
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()

    def test_logout_unauthenticated(self, client):
        # Without auth headers, should fail with 403 (CSRF or auth)
        response = client.post("/api/auth/logout")
        assert response.status_code == 403
