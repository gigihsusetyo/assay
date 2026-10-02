"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from assay.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    """Health endpoint returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
