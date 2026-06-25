"""Unit tests for VectorStore."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etl_enrichment_pipeline.core.embedding_service import SchemaEmbedding
from etl_enrichment_pipeline.core.vector_store import (
    SchemaEmbeddingResult,
    VectorStore,
)


@pytest.fixture
def mock_conn():
    return AsyncMock()


@pytest.fixture
def mock_pool(mock_conn):
    pool = MagicMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__.return_value = mock_conn
    acquire_ctx.__aexit__.return_value = None
    pool.acquire.return_value = acquire_ctx
    pool.close = AsyncMock()
    return pool


@pytest.fixture
def store(mock_pool):
    s = VectorStore(dsn="postgresql://test:test@localhost:5432/test")
    s._pool = mock_pool
    return s


@pytest.fixture
def sample_embedding():
    return SchemaEmbedding(
        object_type="table",
        object_name="employee",
        object_key="table:employee",
        text_content="Table: employee",
        embedding=[0.1] * 384,
        metadata={"table_name": "employee"},
    )


class TestInitializeSchema:
    @pytest.mark.asyncio
    async def test_calls_execute_with_correct_sql(self, store, mock_conn):
        await store.initialize_schema()
        assert mock_conn.execute.call_count == 2
        calls = [c.args[0] for c in mock_conn.execute.call_args_list]
        assert any("CREATE EXTENSION IF NOT EXISTS vector" in c for c in calls)
        assert any("CREATE TABLE IF NOT EXISTS schema_embeddings" in c for c in calls)
        assert any("CREATE INDEX IF NOT EXISTS idx_schema_embeddings_hnsw" in c for c in calls)


class TestUpsertEmbeddings:
    @pytest.mark.asyncio
    async def test_upserts_embedding_successfully(self, store, mock_conn, sample_embedding):
        await store.upsert_embeddings([sample_embedding])
        mock_conn.executemany.assert_awaited_once()
        args = mock_conn.executemany.call_args
        assert "INSERT INTO schema_embeddings" in args[0][0]
        assert len(args[0][1]) == 1
        row = args[0][1][0]
        assert row[0] == "table"
        assert row[1] == "employee"
        assert row[2] == "table:employee"

    @pytest.mark.asyncio
    async def test_empty_list_does_nothing(self, store, mock_conn):
        await store.upsert_embeddings([])
        mock_conn.executemany.assert_not_called()


class TestSearchSimilar:
    @pytest.mark.asyncio
    async def test_returns_correctly_shaped_results(self, store, mock_conn):
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "object_type": "table",
                    "object_name": "employee",
                    "object_key": "table:employee",
                    "text_content": "Table: employee",
                    "embedding": [0.1] * 384,
                    "metadata": {"table_name": "employee"},
                    "similarity": 0.95,
                }
            ]
        )
        results = await store.search_similar([0.1] * 384)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, SchemaEmbeddingResult)
        assert r.object_type == "table"
        assert r.object_name == "employee"
        assert abs(r.similarity - 0.95) < 1e-9
        assert len(r.embedding) == 384

    @pytest.mark.asyncio
    async def test_filters_by_object_type(self, store, mock_conn):
        mock_conn.fetch = AsyncMock(return_value=[])
        await store.search_similar([0.1] * 384, object_type="table")
        call_sql = mock_conn.fetch.call_args[0][0]
        assert "WHERE object_type = $2" in call_sql

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_results(self, store, mock_conn):
        mock_conn.fetch = AsyncMock(return_value=[])
        results = await store.search_similar([0.1] * 384)
        assert results == []

    @pytest.mark.asyncio
    async def test_respects_top_k(self, store, mock_conn):
        mock_conn.fetch = AsyncMock(return_value=[])
        await store.search_similar([0.1] * 384, top_k=5)
        call_sql = mock_conn.fetch.call_args[0][0]
        assert "LIMIT $2" in call_sql or "LIMIT $3" in call_sql


class TestClose:
    @pytest.mark.asyncio
    async def test_closes_pool(self, store, mock_pool):
        await store.close()
        mock_pool.close.assert_awaited_once()
        assert store._pool is None

    @pytest.mark.asyncio
    async def test_close_when_no_pool(self, store):
        store._pool = None
        await store.close()
