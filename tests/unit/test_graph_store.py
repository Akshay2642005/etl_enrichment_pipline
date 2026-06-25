"""Unit tests for GraphStore."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etl_enrichment_pipeline.core.graph_store import GraphStore, JoinPath


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def mock_driver(mock_session):
    driver = MagicMock()
    driver.session.return_value.__aenter__.return_value = mock_session
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def store(mock_driver):
    with patch(
        "etl_enrichment_pipeline.core.graph_store.AsyncGraphDatabase.driver",
        return_value=mock_driver,
    ):
        s = GraphStore(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="test",
        )
        s._driver = mock_driver
        yield s


@pytest.fixture
def sample_metadata():
    return {
        "tables": [
            {
                "table_name": "employee",
                "description": "Employee records",
                "business_role": "master_data",
                "domain": "HR",
                "columns": [
                    {
                        "column_name": "employee_id",
                        "data_type": "int",
                        "is_nullable": False,
                        "is_primary_key": True,
                        "description": "Unique ID",
                        "semantic_type": "ID",
                    }
                ],
            },
            {
                "table_name": "departmentsss",
                "description": "Departments",
                "business_role": "master_data",
                "domain": "HR",
                "columns": [
                    {
                        "column_name": "department_id",
                        "data_type": "int",
                        "is_nullable": False,
                        "is_primary_key": True,
                        "description": "Dept ID",
                        "semantic_type": "ID",
                    }
                ],
            },
        ],
        "relationships": [
            {
                "from_table": "employee",
                "from_column": "department_id",
                "to_table": "departmentsss",
                "to_column": "department_id",
            }
        ],
        "entities": [{"name": "Employee"}, {"name": "Department"}],
        "entity_relationships": [
            {
                "entity": "Employee",
                "related_entities": "Department",
                "business_meaning": "belongs to",
            }
        ],
    }


class TestInitializeSchema:
    @pytest.mark.asyncio
    async def test_creates_constraints(self, store, mock_session):
        await store.initialize_schema()
        assert mock_session.run.call_count == 3
        calls = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("CREATE CONSTRAINT" in c and "t.name IS UNIQUE" in c for c in calls)
        assert any("CREATE CONSTRAINT" in c and "c.table, c.name" in c for c in calls)
        assert any("CREATE CONSTRAINT" in c and "e.name IS UNIQUE" in c for c in calls)


class TestLoadSchema:
    @pytest.mark.asyncio
    async def test_processes_metadata_correctly(self, store, mock_session, sample_metadata):
        await store.load_schema(sample_metadata)
        assert mock_session.run.call_count >= 4
        run_sqls = [c.args[0] for c in mock_session.run.call_args_list]
        assert any("MERGE (t:Table" in s for s in run_sqls)
        assert any("MERGE (c:Column" in s for s in run_sqls)
        assert any("FK_TO" in s for s in run_sqls)
        assert any("BELONGS_TO_ENTITY" in s for s in run_sqls)
        assert any("RELATED_TO" in s for s in run_sqls)

    @pytest.mark.asyncio
    async def test_empty_metadata_does_nothing(self, store, mock_session):
        await store.load_schema({})
        mock_session.run.assert_not_called()


class TestFindJoinPaths:
    @pytest.mark.asyncio
    async def test_returns_paths(self, store, mock_session):
        mock_session.run.return_value.__aiter__.return_value = iter([
            {
                "src_tbl": "employee",
                "src_col": "department_id",
                "tgt_tbl": "departmentsss",
                "tgt_col": "department_id",
            }
        ])
        paths = await store.find_join_paths(["employee", "departmentsss"])
        assert len(paths) == 1
        assert paths[0].tables == ["employee", "departmentsss"]
        assert paths[0].hops == 1

    @pytest.mark.asyncio
    async def test_returns_empty_for_disconnected_tables(self, store, mock_session):
        mock_session.run.return_value.__aiter__.return_value = iter([])
        paths = await store.find_join_paths(["employee", "flight"])
        assert paths == []

    @pytest.mark.asyncio
    async def test_respects_max_hops(self, store, mock_session):
        mock_session.run.return_value.__aiter__.return_value = iter([
            {
                "src_tbl": "a",
                "src_col": "id",
                "tgt_tbl": "b",
                "tgt_col": "id",
            },
            {
                "src_tbl": "b",
                "src_col": "id",
                "tgt_tbl": "c",
                "tgt_col": "id",
            },
        ])
        paths = await store.find_join_paths(["a", "c"], max_hops=1)
        assert paths == []

    @pytest.mark.asyncio
    async def test_single_table_returns_empty(self, store, mock_session):
        mock_session.run.return_value.__aiter__.return_value = iter([])
        paths = await store.find_join_paths(["employee"])
        assert paths == []


class TestClose:
    @pytest.mark.asyncio
    async def test_closes_driver(self, store, mock_driver):
        await store.close()
        mock_driver.close.assert_awaited_once()
        assert store._driver is None

    @pytest.mark.asyncio
    async def test_close_when_no_driver(self, store):
        store._driver = None
        await store.close()


class TestJoinPathDataclass:
    def test_join_path_creation(self):
        jp = JoinPath(
            tables=["employee", "departmentsss"],
            path=[("employee", "department_id", "departmentsss", "department_id")],
            hops=1,
        )
        assert jp.tables == ["employee", "departmentsss"]
        assert jp.hops == 1
