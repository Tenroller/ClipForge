import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import contextlib
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

import importlib


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    # Ensure a clean import for app
    with contextlib.ExitStack() as stack:
        if "app" in globals():
            importlib.reload(globals()["app"])  # type: ignore
        from app import app  # type: ignore
        yield TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"


def test_ping_auth_disabled_allows(client: TestClient) -> None:
    # No API_KEY is set by default; should allow access
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_ping_auth_enabled_requires_key() -> None:
    os.environ["API_KEY"] = "secret"
    try:
        import importlib
        # Re-import app after setting env so dependency reads it
        app_module = importlib.import_module("app")
        importlib.reload(app_module)
        client = TestClient(app_module.app)  # type: ignore
        # Missing header should 401
        r1 = client.get("/api/ping")
        assert r1.status_code == 401
        # With correct header should 200
        r2 = client.get("/api/ping", headers={"X-API-Key": "secret"})
        assert r2.status_code == 200
        assert r2.json().get("ok") is True
    finally:
        del os.environ["API_KEY"]


