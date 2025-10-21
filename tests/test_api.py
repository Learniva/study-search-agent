"""API endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from api.app import app


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "Multi-Agent Study & Grading System API" in response.json()["message"]


def test_health_endpoint(client):
    """Test the health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
