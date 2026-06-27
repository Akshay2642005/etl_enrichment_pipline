"""Integration tests for the full NL-to-SQL pipeline — Task 10."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlglot
from fastapi import FastAPI
from fastapi.testclient import TestClient

from etl_enrichment_pipeline.agents.nl2sql_generator import GenerationResult
from etl_enrichment_pipeline.api.nl2sql_service import router
from etl_enrichment_pipeline.core.context_builder import SchemaContext
from etl_enrichment_pipeline.core.sql_validator import ValidationResult

_PREDEFINED_SQL: dict[str, str] = {
    "hr_employees": "SELECT e.* FROM employee e JOIN departmentsss d ON e.department_id = d.department_id WHERE d.department_name = 'HR';",
    "delayed_flights": "SELECT f.flight_number, f.status FROM flight f WHERE f.status = 'Delayed';",
    "baggage_count": "SELECT f.flight_number, COUNT(b.baggage_id) AS baggage_count FROM flight f LEFT JOIN baggage b ON f.flight_id = b.flight_id GROUP BY f.flight_number;",
    "equipment_maintenance": "SELECT e.equipment_name, mh.maintenance_date FROM equipment e JOIN maintenance_history mh ON e.equipment_id = mh.equipment_id WHERE mh.maintenance_date <= CURRENT_DATE - INTERVAL '30 days';",
    "turnaround_tasks": "SELECT t.* FROM turnaround_operation t JOIN flight f ON t.flight_id = f.flight_id WHERE f.flight_number = 'AA123';",
}

_QUESTIONS: dict[str, str] = {
    "hr_employees": "Show employees in HR department",
    "delayed_flights": "List flights with delayed status",
    "baggage_count": "Count baggage per flight",
    "equipment_maintenance": "Find equipment needing maintenance",
    "turnaround_tasks": "Show turnaround tasks for flight AA123",
}

_TABLE_DEFS: list[dict[str, Any]] = [
    {"table_name": "employee", "columns": [{"column_name": "employee_id"}, {"column_name": "department_id"}]},
    {"table_name": "departmentsss", "columns": [{"column_name": "department_id"}, {"column_name": "department_name"}]},
    {"table_name": "flight", "columns": [{"column_name": "flight_id"}, {"column_name": "flight_number"}, {"column_name": "status"}]},
    {"table_name": "baggage", "columns": [{"column_name": "baggage_id"}, {"column_name": "flight_id"}]},
    {"table_name": "equipment", "columns": [{"column_name": "equipment_id"}, {"column_name": "equipment_name"}]},
    {"table_name": "maintenance_history", "columns": [{"column_name": "maintenance_history_id"}, {"column_name": "equipment_id"}, {"column_name": "maintenance_date"}]},
    {"table_name": "turnaround_operation", "columns": [{"column_name": "turnaround_id"}, {"column_name": "flight_id"}, {"column_name": "status"}]},
]

_FK_RELS: list[dict[str, str]] = [
    {"from_table": "employee", "from_column": "department_id", "to_table": "departmentsss", "to_column": "department_id"},
    {"from_table": "baggage", "from_column": "flight_id", "to_table": "flight", "to_column": "flight_id"},
    {"from_table": "maintenance_history", "from_column": "equipment_id", "to_table": "equipment", "to_column": "equipment_id"},
    {"from_table": "turnaround_operation", "from_column": "flight_id", "to_table": "flight", "to_column": "flight_id"},
]


@pytest.fixture
def sample_context() -> SchemaContext:
    return SchemaContext(tables=_TABLE_DEFS, columns=[], relationships=_FK_RELS)


@pytest.fixture(autouse=True)
def _mock_all_services(monkeypatch: pytest.MonkeyPatch, sample_context: SchemaContext) -> dict[str, MagicMock]:
    mocks: dict[str, MagicMock] = {}
    mock_emb = MagicMock()
    mock_emb.generate_embeddings.return_value = [[0.1] * 384]
    monkeypatch.setattr("etl_enrichment_pipeline.api.shared_state.get_embedding_service", lambda: mock_emb)
    mocks["embedding"] = mock_emb
    mock_vs = MagicMock()
    mock_vs.search_similar.return_value = []
    monkeypatch.setattr("etl_enrichment_pipeline.api.shared_state.get_vector_store", lambda: mock_vs)
    mocks["vector_store"] = mock_vs
    mock_gs = MagicMock()
    mock_gs.find_join_paths.return_value = []
    monkeypatch.setattr("etl_enrichment_pipeline.api.shared_state.get_graph_store", lambda: mock_gs)
    mocks["graph_store"] = mock_gs
    mock_cb = MagicMock()
    mock_cb.build_context = AsyncMock(return_value=sample_context)
    monkeypatch.setattr("etl_enrichment_pipeline.api.nl2sql_service._get_context_builder", lambda: mock_cb)
    mocks["context_builder"] = mock_cb
    mock_gen = MagicMock()
    mock_gen.generate.return_value = GenerationResult(sql="", confidence=0.0)
    monkeypatch.setattr("etl_enrichment_pipeline.api.nl2sql_service._get_nl2sql_generator", lambda: mock_gen)
    mocks["generator"] = mock_gen
    mock_val = MagicMock()
    mock_val.validate.return_value = ValidationResult(is_valid=True, errors=[], warnings=[], confidence=1.0)
    monkeypatch.setattr("etl_enrichment_pipeline.api.nl2sql_service._get_sql_validator", lambda: mock_val)
    mocks["validator"] = mock_val

    async def _noop() -> None:
        return None

    monkeypatch.setattr("etl_enrichment_pipeline.api.shared_state.ensure_stores_initialized", _noop)
    return mocks


@pytest.fixture
def client(_mock_all_services: dict[str, MagicMock]) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _set_generator_sql(mocks: dict[str, MagicMock], sql: str, confidence: float = 0.95) -> None:
    import etl_enrichment_pipeline.api.nl2sql_service as svc

    mock_gen = MagicMock()
    mock_gen.generate.return_value = GenerationResult(sql=sql, confidence=confidence)
    svc._get_nl2sql_generator = lambda: mock_gen
    mocks["generator"] = mock_gen


def assert_sql_is_valid(sql: str) -> None:
    parsed = sqlglot.parse(sql, dialect="postgres")
    assert parsed is not None
    assert all(p is not None for p in parsed), f"sqlglot failed to parse: {sql}"


def assert_response_structure(data: dict[str, Any]) -> None:
    assert {"sql", "confidence", "context_used", "explanation"}.issubset(data.keys())
    assert isinstance(data["sql"], str)
    assert isinstance(data["confidence"], float)
    assert isinstance(data["context_used"], list)


def assert_sql_contains(sql: str, *keywords: str) -> None:
    upper = sql.upper()
    for kw in keywords:
        assert kw.upper() in upper, f"Expected '{kw}' in SQL:\n{sql}"


class TestNl2SqlPipeline:
    def test_hr_employees(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _set_generator_sql(_mock_all_services, _PREDEFINED_SQL["hr_employees"])
        resp = client.post("/api/v1/nl2sql", json={"question": _QUESTIONS["hr_employees"]})
        assert resp.status_code == 200
        data = resp.json()
        assert_response_structure(data)
        assert_sql_is_valid(data["sql"])
        assert_sql_contains(data["sql"], "employee", "departmentsss", "JOIN", "WHERE", "department_name", "HR")

    def test_delayed_flights(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _set_generator_sql(_mock_all_services, _PREDEFINED_SQL["delayed_flights"])
        resp = client.post("/api/v1/nl2sql", json={"question": _QUESTIONS["delayed_flights"]})
        assert resp.status_code == 200
        data = resp.json()
        assert_response_structure(data)
        assert_sql_is_valid(data["sql"])
        assert_sql_contains(data["sql"], "flight", "WHERE", "Delayed")
        assert data["confidence"] > 0.0

    def test_baggage_count(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _set_generator_sql(_mock_all_services, _PREDEFINED_SQL["baggage_count"])
        resp = client.post("/api/v1/nl2sql", json={"question": _QUESTIONS["baggage_count"]})
        assert resp.status_code == 200
        data = resp.json()
        assert_response_structure(data)
        assert_sql_is_valid(data["sql"])
        assert_sql_contains(data["sql"], "flight", "baggage", "COUNT", "GROUP BY")

    def test_equipment_maintenance(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _set_generator_sql(_mock_all_services, _PREDEFINED_SQL["equipment_maintenance"])
        resp = client.post("/api/v1/nl2sql", json={"question": _QUESTIONS["equipment_maintenance"]})
        assert resp.status_code == 200
        data = resp.json()
        assert_response_structure(data)
        assert_sql_is_valid(data["sql"])
        assert_sql_contains(data["sql"], "equipment", "maintenance_history", "maintenance_date")

    def test_turnaround_tasks(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _set_generator_sql(_mock_all_services, _PREDEFINED_SQL["turnaround_tasks"])
        resp = client.post("/api/v1/nl2sql", json={"question": _QUESTIONS["turnaround_tasks"]})
        assert resp.status_code == 200
        data = resp.json()
        assert_response_structure(data)
        assert_sql_is_valid(data["sql"])
        assert_sql_contains(data["sql"], "turnaround_operation", "flight", "flight_number", "AA123")


class TestNl2SqlErrors:
    def test_missing_question_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/nl2sql", json={})
        assert resp.status_code == 422

    def test_empty_question_returns_ok(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _set_generator_sql(_mock_all_services, "", confidence=0.0)
        resp = client.post("/api/v1/nl2sql", json={"question": ""})
        assert resp.status_code == 200
        assert resp.json()["sql"] == ""

    def test_service_failure_returns_500(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _mock_all_services["context_builder"].build_context = AsyncMock(side_effect=RuntimeError("fail"))
        resp = client.post("/api/v1/nl2sql", json={"question": "show me employees"})
        assert resp.status_code == 500

    def test_generator_returns_empty_sql(self, client: TestClient, _mock_all_services: dict[str, MagicMock]) -> None:
        _set_generator_sql(_mock_all_services, "", confidence=0.0)
        resp = client.post("/api/v1/nl2sql", json={"question": "some question"})
        data = resp.json()
        assert data["sql"] == ""
        assert data["confidence"] == 0.0

    def test_health_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/v1/nl2sql/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "nl2sql"
