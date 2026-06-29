"""Tests for FastAPI skeleton and connection endpoints."""""""  # noqa: D200
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from etl_enrichment_pipeline.api.main import app

client = TestClient(app)

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(autouse=True)
def _mock_connection_db(monkeypatch):
    """Mock all connection service DB functions so tests don't need PostgreSQL."""
    now = datetime.now(timezone.utc)
    fake_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    fake_creds = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "username": "test_user",
        "password": "test_pass",
    }
    fake_schema = {
        "tables": [{"table_name": "users", "columns": []}],
        "relationships": [],
    }
    fake_insights = {
        "kpis": [],
        "insights": [],
        "opportunities": [],
        "art_of_the_possible": [],
    }

    # Mock the connection pool
    def mock_get_pool():
        return AsyncMock()

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service._get_pool",
        mock_get_pool,
    )

    from etl_enrichment_pipeline.models.connection_schema import (
        ConnectionCredentials,
        SavedConnection,
        SavedConnectionSummary,
    )

    # Mock save_connection
    async def mock_save(**kwargs):
        return SavedConnection(
            id=fake_id,
            name=kwargs.get("name", "test"),
            description=kwargs.get("description"),
            database_type=kwargs.get("database_type", "postgres"),
            credentials=ConnectionCredentials(**fake_creds),
            enriched_schema=kwargs.get("enriched_schema", {}),
            insights=kwargs.get("insights", {}),
            status=kwargs.get("status", "active"),
            error_message=kwargs.get("error_message"),
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.save_connection",
        mock_save,
    )

    # Mock list_connections
    async def mock_list(**kwargs):
        return [
            SavedConnectionSummary(
                id=fake_id,
                name="test-connection",
                description="A test connection",
                database_type="postgres",
                status="active",
                table_count=1,
                view_count=0,
                created_at=now,
                updated_at=now,
            )
        ]

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.list_connections",
        mock_list,
    )

    # Mock search_connections
    async def mock_search(**kwargs):
        return [
            SavedConnectionSummary(
                id=fake_id,
                name="test-connection",
                description="A test connection",
                database_type="postgres",
                status="active",
                table_count=1,
                view_count=0,
                created_at=now,
                updated_at=now,
            )
        ]

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.search_connections",
        mock_search,
    )

    # Mock get_connection
    async def mock_get(connection_id: str):
        return SavedConnection(
            id=connection_id,
            name="test-connection",
            description="A test connection",
            database_type="postgres",
            credentials=ConnectionCredentials(**fake_creds),
            enriched_schema=fake_schema,
            insights=fake_insights,
            status="active",
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.get_connection",
        mock_get,
    )

    # Mock delete_connection
    async def mock_delete(connection_id: str):
        return True

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.delete_connection",
        mock_delete,
    )

    # Mock update_connection
    async def mock_update(connection_id: str, **kwargs):
        return SavedConnection(
            id=connection_id,
            name=kwargs.get("name", "test-connection"),
            description=kwargs.get("description"),
            database_type="postgres",
            credentials=ConnectionCredentials(**fake_creds),
            enriched_schema=fake_schema,
            insights=fake_insights,
            status=kwargs.get("status", "active"),
            error_message=kwargs.get("error_message"),
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.update_connection",
        mock_update,
    )

    # Mock update_connection_schema
    async def mock_update_schema(connection_id: str, enriched_schema: dict):
        return SavedConnection(
            id=connection_id,
            name="test-connection",
            description="A test connection",
            database_type="postgres",
            credentials=ConnectionCredentials(**fake_creds),
            enriched_schema=enriched_schema,
            insights=fake_insights,
            status="active",
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.update_connection_schema",
        mock_update_schema,
    )

    # Mock update_connection_insights
    async def mock_update_insights(connection_id: str, insights: dict):
        return SavedConnection(
            id=connection_id,
            name="test-connection",
            description="A test connection",
            database_type="postgres",
            credentials=ConnectionCredentials(**fake_creds),
            enriched_schema=fake_schema,
            insights=insights,
            status="active",
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "etl_enrichment_pipeline.api.connection_service.update_connection_insights",
        mock_update_insights,
    )

    return fake_id


# ===================================================================
# Health endpoints
# ===================================================================


class TestHealthEndpoints:
    """Health check endpoints for all services."""

    def test_health_endpoint(self):
        """GET /health returns 200 with correct response body."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "etl-enrichment-pipeline"
        assert data["version"] == "0.1.0"

    def test_nl2sql_health_endpoint(self):
        """GET /api/v1/nl2sql/health returns 200 with correct response body."""
        response = client.get("/api/v1/nl2sql/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "nl2sql"

    def test_quality_health_endpoint(self):
        """GET /api/v1/quality/health returns 200 with correct response body."""
        response = client.get("/api/v1/quality/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "quality"

    def test_insights_health_endpoint(self):
        """GET /api/v1/insights/health returns 200 with correct response body."""
        response = client.get("/api/v1/insights/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "insights"


# ===================================================================
# Connection endpoint tests
# ===================================================================


class TestConnectionsAPI:
    """Test CRUD and power endpoints for /connections."""

    def test_create_connection(self, _mock_connection_db):
        """POST /connections with valid body returns 200."""
        payload = {
            "name": "My Database",
            "database_type": "postgres",
            "credentials": {
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "username": "admin",
                "password": "secret",
            },
            "enriched_schema": {"tables": []},
        }
        response = client.post("/connections", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Database"
        assert data["database_type"] == "postgres"
        assert "id" in data
        assert data["status"] == "active"

    def test_create_connection_missing_name(self, _mock_connection_db):
        """POST /connections without name returns 422."""
        payload = {
            "database_type": "postgres",
            "credentials": {"host": "localhost", "database": "mydb"},
        }
        response = client.post("/connections", json=payload)
        assert response.status_code == 422

    def test_create_connection_missing_credentials(self, _mock_connection_db):
        """POST /connections without credentials returns 422."""
        payload = {
            "name": "test",
            "database_type": "postgres",
        }
        response = client.post("/connections", json=payload)
        assert response.status_code == 422

    def test_create_connection_missing_database_field(self, _mock_connection_db):
        """POST /connections with credentials missing 'database' returns 422."""
        payload = {
            "name": "test",
            "database_type": "postgres",
            "credentials": {"host": "localhost"},
        }
        response = client.post("/connections", json=payload)
        assert response.status_code == 422

    def test_list_connections(self, _mock_connection_db):
        """GET /connections returns a list of summaries."""
        response = client.get("/connections")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_connections_with_filters(self, _mock_connection_db):
        """GET /connections supports status and database_type filters."""
        response = client.get(
            "/connections?status=active&database_type=postgres"
        )
        assert response.status_code == 200

    def test_search_connections(self, _mock_connection_db):
        """GET /connections/search returns results for a valid query."""
        response = client.get("/connections/search?q=test")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_connections_missing_query(self, _mock_connection_db):
        """GET /connections/search without q returns 422."""
        response = client.get("/connections/search")
        assert response.status_code == 422

    def test_get_connection(self, _mock_connection_db):
        """GET /connections/{id} returns full connection data."""
        cid = _mock_connection_db
        response = client.get(f"/connections/{cid}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cid
        assert "credentials" in data
        assert "enriched_schema" in data
        assert "insights" in data

    def test_get_connection_details_alias(self, _mock_connection_db):
        """GET /connections/{id}/details works as an alias."""
        cid = _mock_connection_db
        response = client.get(f"/connections/{cid}/details")
        assert response.status_code == 200

    def test_delete_connection(self, _mock_connection_db):
        """DELETE /connections/{id} returns 200 on success."""
        cid = _mock_connection_db
        response = client.delete(f"/connections/{cid}")
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"]

    def test_patch_connection(self, _mock_connection_db):
        """PATCH /connections/{id} updates metadata fields."""
        cid = _mock_connection_db
        response = client.patch(
            f"/connections/{cid}",
            json={"name": "updated-name", "status": "archived"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["status"] == "archived"

    def test_patch_connection_empty_body(self, _mock_connection_db):
        """PATCH with empty body still returns 200 (no-op)."""
        cid = _mock_connection_db
        response = client.patch(f"/connections/{cid}", json={})
        assert response.status_code == 200

    def test_put_schema(self, _mock_connection_db):
        """PUT /connections/{id}/schema updates enriched schema."""
        cid = _mock_connection_db
        new_schema = {
            "tables": [
                {
                    "table_name": "orders",
                    "columns": [{"column_name": "id", "data_type": "integer"}],
                }
            ]
        }
        response = client.put(f"/connections/{cid}/schema", json=new_schema)
        assert response.status_code == 200
        data = response.json()
        assert data["enriched_schema"]["tables"][0]["table_name"] == "orders"

    def test_put_insights(self, _mock_connection_db):
        """PUT /connections/{id}/insights updates insights."""
        cid = _mock_connection_db
        new_insights = {
            "kpis": [{"name": "test_kpi", "description": "Test"}],
            "insights": [],
            "opportunities": [],
            "art_of_the_possible": [],
        }
        response = client.put(f"/connections/{cid}/insights", json=new_insights)
        assert response.status_code == 200
        data = response.json()
        assert data["insights"]["kpis"][0]["name"] == "test_kpi"

    def test_connection_routes_registered(self):
        """All expected connection routes are registered."""
        routes = [r.path for r in app.routes if "connection" in r.path.lower()]
        expected = {
            "/connections",
            "/connections/search",
            "/connections/{connection_id}",
            "/connections/{connection_id}/details",
            "/connections/{connection_id}/schema",
            "/connections/{connection_id}/insights",
        }
        for path in expected:
            assert path in routes, f"Expected {path} in registered routes {routes}"
