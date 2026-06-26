"""pgvector vector store for schema embedding similarity search.

Manages the schema_embeddings table with asyncpg connection pooling,
HNSW index on the embedding column, and cosine-similarity search.
"""

from __future__ import annotations

import json
import os
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qs

import asyncpg

from etl_enrichment_pipeline.core.embedding_service import SchemaEmbedding


@dataclass(frozen=True)
class SchemaEmbeddingResult:
    """SchemaEmbedding with similarity score from a vector search."""

    object_type: str
    object_name: str
    object_key: str
    text_content: str
    embedding: list[float]
    metadata: dict[str, Any]
    similarity: float


_PGVECTOR_DSN = os.getenv(
    "PGVECTOR_DSN",
    "postgresql://postgres:postgres@localhost:5432/schema_embeddings",
)


def _parse_dsn(dsn: str) -> tuple[str, dict]:
    """Strip query-string parameters from a DSN and return kwargs for asyncpg.

    On Windows, asyncpg raises ``[Errno 22] Invalid argument`` when the DSN
    contains query-string parameters such as ``?sslmode=require``.  We pull
    those out manually and pass SSL settings via the ``ssl`` keyword argument
    instead.

    Returns:
        A tuple of (clean_dsn, extra_kwargs) where ``extra_kwargs`` may
        contain an ``ssl`` key set to an :class:`ssl.SSLContext`.
    """
    parsed = urlparse(dsn)
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    extra_kwargs: dict = {}

    sslmode = query_params.pop("sslmode", [None])[0]
    if sslmode in ("require", "verify-ca", "verify-full"):
        ctx = ssl.create_default_context()
        if sslmode == "require":
            # Aiven and similar hosted providers use self-signed or
            # chain-signed certs — disable hostname / cert verification
            # only when the user explicitly set sslmode=require (not
            # verify-ca / verify-full).
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        extra_kwargs["ssl"] = ctx
    elif sslmode in ("prefer", "allow"):
        extra_kwargs["ssl"] = False

    # Rebuild the DSN without any query string
    clean = urlunparse(parsed._replace(query=""))
    return clean, extra_kwargs

_CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_embeddings (
    id          SERIAL PRIMARY KEY,
    object_type TEXT NOT NULL,
    object_name TEXT NOT NULL,
    object_key  TEXT NOT NULL UNIQUE,
    text_content TEXT NOT NULL,
    embedding   vector(384) NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_hnsw
    ON schema_embeddings
    USING hnsw (embedding vector_cosine_ops);
"""


class VectorStore:
    """Asyncpg-backed pgvector store for schema embeddings.

    Usage::

        store = VectorStore()
        await store.initialize_schema()
        await store.upsert_embeddings(embeddings)
        results = await store.search_similar(query_emb, object_type="table")
        await store.close()
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or _PGVECTOR_DSN
        self._pool: asyncpg.Pool | None = None

    _CONNECTION_TIMEOUT = 5  # seconds — fail fast when pgvector is unavailable

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            clean_dsn, extra_kwargs = _parse_dsn(self._dsn)
            self._pool = await asyncpg.create_pool(
                clean_dsn,
                min_size=1,
                max_size=5,
                timeout=self._CONNECTION_TIMEOUT,
                **extra_kwargs,
            )
        return self._pool

    async def initialize_schema(self) -> None:
        """Create the ``schema_embeddings`` table and HNSW index if they don't exist."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
            await conn.execute(_CREATE_INDEX_SQL)

    async def upsert_embeddings(self, embeddings: list[SchemaEmbedding]) -> None:
        """Upsert schema embeddings into the vector store.

        Rows are matched on ``object_key`` — existing records are updated,
        new records are inserted.
        """
        if not embeddings:
            return

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO schema_embeddings
                    (object_type, object_name, object_key, text_content, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb)
                ON CONFLICT (object_key) DO UPDATE SET
                    object_type  = EXCLUDED.object_type,
                    object_name  = EXCLUDED.object_name,
                    text_content = EXCLUDED.text_content,
                    embedding    = EXCLUDED.embedding,
                    metadata     = EXCLUDED.metadata,
                    updated_at   = now()
                """,
                [
                    (
                        emb.object_type,
                        emb.object_name,
                        emb.object_key,
                        emb.text_content,
                    str(emb.embedding),
                    json.dumps(emb.metadata),
                    )
                    for emb in embeddings
                ],
            )

    async def search_similar(
        self,
        query_embedding: list[float],
        object_type: str | None = None,
        top_k: int = 10,
    ) -> list[SchemaEmbeddingResult]:
        """Search for the *top_k* most similar schema embeddings via cosine distance.

        Arguments:
            query_embedding: 384-dim vector to compare against.
            object_type:      Optional filter (e.g. ``"table"``, ``"column"``,
                              ``"relationship"``).
            top_k:            Number of results to return (default 10).

        Returns:
            List of ``SchemaEmbeddingResult`` ordered by descending similarity.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if object_type:
                rows = await conn.fetch(
                    """
                    SELECT object_type, object_name, object_key,
                           text_content, embedding, metadata,
                           1 - (embedding <=> $1::vector) AS similarity
                    FROM schema_embeddings
                    WHERE object_type = $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                    """,
                    str(query_embedding),
                    object_type,
                    top_k,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT object_type, object_name, object_key,
                           text_content, embedding, metadata,
                           1 - (embedding <=> $1::vector) AS similarity
                    FROM schema_embeddings
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    str(query_embedding),
                    top_k,
                )

        return [
            SchemaEmbeddingResult(
                object_type=row["object_type"],
                object_name=row["object_name"],
                object_key=row["object_key"],
                text_content=row["text_content"],
                embedding=list(row["embedding"]),
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else dict(row["metadata"]),
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    async def close(self) -> None:
        """Close the connection pool and release all resources."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


__all__ = ["VectorStore", "SchemaEmbeddingResult"]
