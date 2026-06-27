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


def test_nl2sql_health_endpoint():
    """GET /api/v1/nl2sql/health returns 200 with correct response body."""
    response = client.get("/api/v1/nl2sql/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "nl2sql"


def test_quality_health_endpoint():
    """GET /api/v1/quality/health returns 200 with correct response body."""
    response = client.get("/api/v1/quality/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "quality"


def test_insights_health_endpoint():
    """GET /api/v1/insights/health returns 200 with correct response body."""
    response = client.get("/api/v1/insights/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "insights"
