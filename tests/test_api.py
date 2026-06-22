"""Tests for FastAPI skeleton."""
from fastapi.testclient import TestClient

from etl_enrichment_pipeline.api.main import app

client = TestClient(app)


def test_health_endpoint():
    """GET /health returns 200 with correct response body."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "etl-enrichment-pipeline"
    assert data["version"] == "0.1.0"
