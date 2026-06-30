"""Connection persistence API router — save, list, get, delete, and run pipeline.

Provides endpoints to persist database connection details along with their
enriched schema metadata and generated insights into a PostgreSQL-backed
``saved_connections`` table.

Endpoints:
    POST   /connections                   — save a new connection
    GET    /connections                   — list saved connections (summaries)
    GET    /connections/search            — search connections by name
    GET    /connections/{id}              — get a single connection (full payload)
    PATCH  /connections/{id}              — partial update (
    name, description, status, error)
    PUT    /connections/{id}/schema       — replace enriched schema only
    PUT    /connections/{id}/insights     — replace insights only
    DELETE /connections/{id}              — delete a saved connection
    GET    /connections/{id}/details      — alias for get
    POST   /connections/extract-and-save  — extract DB + enrich + save in one call
    POST   /connections/{id}/refresh      — re-run pipeline on an existing connection
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC as _UTC
from datetime import datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.models.connection_schema import (
    CREATE_SAVED_CONNECTIONS_TABLE_SQL,
    MIGRATE_ADD_INSIGHTS_HASH_SQL,
    ConnectionCredentials,
    SavedConnection,
    SavedConnectionSummary,
)

# ---------------------------------------------------------------------------
# Thread pool for blocking pipeline work
# ---------------------------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="conn-pipeline")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database connection settings
# ---------------------------------------------------------------------------

_CONNECTIONS_DSN = os.getenv(
    "CONNECTIONS_DSN",
    os.getenv(
        "PGVECTOR_DSN",
        "postgresql://postgres:postgres@localhost:5432/schema_embeddings",
    ),
)

# ---------------------------------------------------------------------------
# Pool singleton
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    """Lazy-initialised connection pool for the ``saved_connections`` table."""
    global _pool
    if _pool is None:
        # Strip query params like ?sslmode=require (same pattern as VectorStore)
        from urllib.parse import urlparse, urlunparse

        clean_dsn = urlunparse(urlparse(_CONNECTIONS_DSN)._replace(query=""))
        _pool = await asyncpg.create_pool(
            clean_dsn,
            min_size=1,
            max_size=3,
            timeout=5,
        )
    return _pool


async def initialize_schema() -> None:
    """Create / migrate the ``saved_connections`` table."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SAVED_CONNECTIONS_TABLE_SQL)
        await conn.execute(MIGRATE_ADD_INSIGHTS_HASH_SQL)
    logger.info("saved_connections table initialised (if not exists)")


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def save_connection(
    name: str,
    database_type: str,
    credentials: dict[str, Any],
    enriched_schema: dict[str, Any] | None = None,
    insights: dict[str, Any] | None = None,
    description: str | None = None,
    status: str = "active",
    error_message: str | None = None,
) -> SavedConnection:
    """Insert a new saved connection row and return the persisted model."""
    insights_data = insights or {}
    new_hash = _compute_insights_hash(insights_data)
    pool = await _get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO saved_connections
            (name, description, database_type, credentials,
             enriched_schema, insights, insights_hash, status, error_message)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7, $8, $9)
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, insights_hash, status, error_message,
                  created_at, updated_at
        """,
        name,
        description,
        database_type,
        json.dumps(credentials),
        json.dumps(enriched_schema or {}),
        json.dumps(insights_data),
        new_hash,
        status,
        error_message,
    )

    return _row_to_connection(row)


async def list_connections(
    status_filter: str | None = None,
    database_type_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SavedConnectionSummary]:
    """Return a paginated list of connection summaries."""
    pool = await _get_pool()

    conditions: list[str] = []
    params: list[Any] = []
    param_idx = 1

    if status_filter:
        conditions.append(f"status = ${param_idx}")
        params.append(status_filter)
        param_idx += 1

    if database_type_filter:
        conditions.append(f"database_type = ${param_idx}")
        params.append(database_type_filter)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    query = f"""
        SELECT id, name, description, database_type, status,
               COALESCE(jsonb_array_length(enriched_schema->'tables'), 0) AS table_count,
               COALESCE(jsonb_array_length(enriched_schema->'views'), 0) AS view_count,
               created_at, updated_at
        FROM saved_connections
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])

    rows = await pool.fetch(query, *params)

    return [
        SavedConnectionSummary(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            database_type=row["database_type"],
            status=row["status"],
            table_count=row["table_count"],
            view_count=row["view_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


async def search_connections(
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> list[SavedConnectionSummary]:
    """Search saved connections by name (case-insensitive LIKE)."""
    pool = await _get_pool()

    rows = await pool.fetch(
        """
        SELECT id, name, description, database_type, status,
               COALESCE(jsonb_array_length(enriched_schema->'tables'), 0) AS table_count,
               COALESCE(jsonb_array_length(enriched_schema->'views'), 0) AS view_count,
               created_at, updated_at
        FROM saved_connections
        WHERE name ILIKE '%' || $1 || '%'
           OR description ILIKE '%' || $1 || '%'
        ORDER BY
            CASE
                WHEN name ILIKE $1 THEN 0
                WHEN name ILIKE $1 || '%' THEN 1
                WHEN name ILIKE '%' || $1 || '%' THEN 2
                ELSE 3
            END,
            created_at DESC
        LIMIT $2 OFFSET $3
        """,
        query,
        limit,
        offset,
    )

    return [
        SavedConnectionSummary(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            database_type=row["database_type"],
            status=row["status"],
            table_count=row["table_count"],
            view_count=row["view_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


async def get_connection(connection_id: str) -> SavedConnection | None:
    """Fetch a single saved connection by UUID, or return None."""
    pool = await _get_pool()

    row = await pool.fetchrow(
        """
        SELECT id, name, description, database_type, credentials,
               enriched_schema, insights, insights_hash, status, error_message,
               created_at, updated_at
        FROM saved_connections
        WHERE id = $1::uuid
        """,
        connection_id,
    )

    return _row_to_connection(row) if row else None


async def delete_connection(connection_id: str) -> bool:
    """Delete a saved connection by UUID. Returns True if deleted."""
    pool = await _get_pool()

    result = await pool.execute(
        "DELETE FROM saved_connections WHERE id = $1::uuid",
        connection_id,
    )
    return result != "DELETE 0"


async def update_connection(
    connection_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    error_message: str | None = None,
) -> SavedConnection | None:
    """Partially update metadata fields of a saved connection. Returns the updated row or None."""
    pool = await _get_pool()

    set_clauses: list[str] = []
    params: list[Any] = []
    param_idx = 1

    if name is not None:
        set_clauses.append(f"name = ${param_idx}")
        params.append(name)
        param_idx += 1
    if description is not None:
        set_clauses.append(f"description = ${param_idx}")
        params.append(description)
        param_idx += 1
    if status is not None:
        set_clauses.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1
    if error_message is not None:
        set_clauses.append(f"error_message = ${param_idx}")
        params.append(error_message)
        param_idx += 1

    if not set_clauses:
        return await get_connection(connection_id)

    set_clauses.append(f"updated_at = ${param_idx}")
    params.append(datetime.now(_UTC))
    param_idx += 1

    params.append(connection_id)
    query = f"""
        UPDATE saved_connections
        SET {", ".join(set_clauses)}
        WHERE id = ${param_idx}::uuid
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, insights_hash, status, error_message,
                  created_at, updated_at
    """

    pool = await _get_pool()
    row = await pool.fetchrow(query, *params)
    return _row_to_connection(row) if row else None


async def update_connection_schema(
    connection_id: str,
    enriched_schema: dict[str, Any],
) -> SavedConnection | None:
    """Replace the enriched schema for a saved connection."""
    pool = await _get_pool()
    row = await pool.fetchrow(
        """
        UPDATE saved_connections
        SET enriched_schema = $1::jsonb, updated_at = now()
        WHERE id = $2::uuid
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, insights_hash, status, error_message,
                  created_at, updated_at
        """,
        json.dumps(enriched_schema),
        connection_id,
    )
    return _row_to_connection(row) if row else None


async def update_connection_insights(
    connection_id: str,
    insights: dict[str, Any],
) -> SavedConnection | None:
    """Replace the insights for a saved connection.

    Computes a SHA-256 hash of the incoming payload and skips the DB write
    entirely when the hash matches the value already stored (i.e. nothing
    actually changed).  This avoids redundant writes after a re-generation
    that produced identical results.
    """
    new_hash = _compute_insights_hash(insights)
    pool = await _get_pool()

    # Quick hash check — one cheap SELECT before the expensive UPDATE.
    hash_row = await pool.fetchrow(
        "SELECT insights_hash FROM saved_connections WHERE id = $1::uuid",
        connection_id,
    )
    if hash_row is None:
        return None

    if hash_row["insights_hash"] == new_hash:
        logger.debug(
            "Insights hash unchanged for connection %s — skipping write",
            connection_id,
        )
        return await get_connection(connection_id)

    row = await pool.fetchrow(
        """
        UPDATE saved_connections
        SET insights       = $1::jsonb,
            insights_hash  = $2,
            updated_at     = now()
        WHERE id = $3::uuid
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, insights_hash, status, error_message,
                  created_at, updated_at
        """,
        json.dumps(insights),
        new_hash,
        connection_id,
    )
    return _row_to_connection(row) if row else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_connection(row: asyncpg.Record) -> SavedConnection:
    """Convert an asyncpg row to a ``SavedConnection`` model."""
    return SavedConnection(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        database_type=row["database_type"],
        credentials=ConnectionCredentials.model_validate(
            row["credentials"]
            if isinstance(row["credentials"], dict)
            else json.loads(row["credentials"])
        ),
        enriched_schema=(
            row["enriched_schema"]
            if isinstance(row["enriched_schema"], dict)
            else json.loads(row["enriched_schema"])
        ),
        insights=(
            row["insights"]
            if isinstance(row["insights"], dict)
            else json.loads(row["insights"])
        ),
        insights_hash=row.get("insights_hash"),
        status=row["status"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class SaveConnectionRequest(BaseModel):
    """Request body to save a new connection."""

    name: str = Field(..., min_length=1, description="Human-readable connection name")
    description: str | None = Field(default=None, description="Optional description")
    database_type: str = Field(
        ...,
        description="Database type: postgres, mysql, mariadb, sqlserver, oracle, sqlite",
    )
    credentials: ConnectionCredentials = Field(
        ..., description="Database connection credentials"
    )
    enriched_schema: dict[str, Any] | None = Field(
        default=None,
        description="Full enriched metadata output from the pipeline",
    )
    insights: dict[str, Any] | None = Field(
        default=None,
        description="Generated insights (KPIs, insights, opportunities, art_of_the_possible)",
    )
    status: str = Field(
        default="active",
        description="Connection status",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if something went wrong",
    )


class SaveConnectionResponse(BaseModel):
    """Response after saving a connection."""

    id: str = Field(..., description="Newly created connection UUID")
    name: str = Field(..., description="Connection name")
    database_type: str = Field(..., description="Database vendor")
    status: str = Field(default="active")
    created_at: datetime | None = Field(default=None)


class UpdateConnectionRequest(BaseModel):
    """Request body to partially update a saved connection."""

    name: str | None = Field(default=None, description="Human-readable connection name")
    description: str | None = Field(default=None, description="Optional description")
    status: str | None = Field(
        default=None,
        description="Connection status: active, error, archived",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if something went wrong",
    )


class ExtractAndSaveRequest(BaseModel):
    """Request body to extract schema from a live DB, enrich, and save in one call."""

    name: str = Field(..., min_length=1, description="Human-readable connection name")
    description: str | None = Field(default=None, description="Optional description")
    database_type: str = Field(
        ...,
        description="Database type: postgres, mysql, mariadb, sqlserver, oracle, sqlite",
    )
    credentials: ConnectionCredentials = Field(
        ..., description="Database connection credentials"
    )
    generate_insights: bool = Field(
        default=False,
        description="Whether to also generate insights after enrichment",
    )


# ---------------------------------------------------------------------------
# Insight categories supported by the frontend
# ---------------------------------------------------------------------------

INSIGHT_CATEGORIES = [
    "Overview",
    "Operations",
    "Finance",
    "Marketing",
    "Sales",
    "Human Resources",
    "IT",
]


# ---------------------------------------------------------------------------
# SHA256 delta utilities for insight patching
# ---------------------------------------------------------------------------


def _compute_insights_hash(insights: dict[str, Any]) -> str:
    """Compute SHA-256 hex digest of the full insights dict.

    Used to detect whether the insights payload has changed between
    regenerations.  Identical hashes → no DB write needed.
    """
    return hashlib.sha256(
        json.dumps(insights, sort_keys=True, ensure_ascii=False, default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def _item_sha256(item: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of a JSON-serialised dict.

    Used to detect whether an insight item (KPI, Insight, etc.) has
    changed between regenerations.  Items whose hash stays the same
    are kept verbatim (avoiding unnecessary writes).
    """
    return hashlib.sha256(
        json.dumps(item, sort_keys=True, ensure_ascii=False, default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def compute_category_delta(
    old_items: list[dict[str, Any]],
    new_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge old and new items for a single category sub-list (KPIs,
    insights, opportunities, or art_of_the_possible).

    Items whose SHA-256 hash is identical are kept from *old_items*
    (no change).  Items whose hash differs — or items only present in
    *new_items* — replace or are added.  Items only present in
    *old_items* are removed.

    This produces a minimal delta for the DB patch.
    """
    old_hashes: dict[str, dict[str, Any]] = {}
    for item in old_items:
        h = _item_sha256(item)
        old_hashes[h] = item

    new_hashes: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    for item in new_items:
        h = _item_sha256(item)
        new_hashes[h] = item
        seen.add(h)
        if h in old_hashes:
            # Same hash → keep old version (unchanged)
            merged.append(old_hashes[h])
        else:
            # New or modified → use new version
            merged.append(item)

    return merged


def _patch_category_insights(
    existing_category: dict[str, list[dict[str, Any]]],
    new_category: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Compute a SHA-256 delta merge between existing and new category
    data and return the patched result.

    Each of the four sub-lists (kpis, insights, opportunities,
    art_of_the_possible) is merged independently via
    :func:`compute_category_delta`.
    """
    keys = ("kpis", "insights", "opportunities", "art_of_the_possible")
    result: dict[str, list[dict[str, Any]]] = {}
    for key in keys:
        old_list = existing_category.get(key, [])
        new_list = new_category.get(key, [])
        result[key] = compute_category_delta(old_list, new_list)
        logger.debug(
            "Category delta for '%s': %d old → %d new → %d after merge",
            key,
            len(old_list),
            len(new_list),
            len(result[key]),
        )
    return result


# ---------------------------------------------------------------------------
# Multi-category insight generation
# ---------------------------------------------------------------------------


async def _generate_all_insights(
    enriched_schema: dict[str, Any],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Generate insights for all categories the frontend supports.

    Calls ``InsightsGenerator.generate()`` for each category in
    ``INSIGHT_CATEGORIES`` and returns a dict keyed by category name
    where each value is ``{kpis, insights, opportunities, art_of_the_possible}``.

    If any single category fails, it is replaced with an empty result so
    the rest of the data is still usable.
    """
    from etl_enrichment_pipeline.agents.insights_agent import InsightsGenerator

    generator = InsightsGenerator(
        enriched_metadata=enriched_schema,
    )

    results: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for category in INSIGHT_CATEGORIES:
        try:
            domain = None if category == "Overview" else category
            result = await generator.generate(domain=domain)
            results[category] = {
                "kpis": result.get("kpis", []),
                "insights": result.get("insights", []),
                "opportunities": result.get("opportunities", []),
                "art_of_the_possible": result.get("art_of_the_possible", []),
            }
            logger.info(
                "Generated %s insights: %d KPIs, %d insights, "
                "%d opportunities, %d art_of_the_possible",
                category,
                len(results[category]["kpis"]),
                len(results[category]["insights"]),
                len(results[category]["opportunities"]),
                len(results[category]["art_of_the_possible"]),
            )
        except Exception as exc:
            logger.warning(
                "Insights generation failed for category '%s': %s",
                category,
                exc,
            )
            results[category] = {
                "kpis": [],
                "insights": [],
                "opportunities": [],
                "art_of_the_possible": [],
            }

    return results


# ---------------------------------------------------------------------------
# Background insight generation
# ---------------------------------------------------------------------------


def _generate_all_insights_sync(
    enriched_schema: dict[str, Any],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Synchronous wrapper around ``_generate_all_insights``.

    Creates a new event loop in the calling thread so the async generator
    can be run inside a ``ThreadPoolExecutor`` without blocking the
    main event loop.
    """
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    _asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_generate_all_insights(enriched_schema))
    finally:
        loop.close()


async def _background_generate_and_update(
    connection_id: str,
    enriched_schema: dict[str, Any],
) -> None:
    """Generate all category insights in a background thread, apply per-category
    SHA-256 delta against the current insights, and persist only when the hash
    has actually changed.

    This is designed to be fired as ``asyncio.create_task`` so the HTTP
    response can be returned immediately while the (slow) LLM calls run in
    a ``ThreadPoolExecutor``.
    """
    try:
        loop = asyncio.get_running_loop()
        new_insights = await loop.run_in_executor(
            _executor,
            _generate_all_insights_sync,
            enriched_schema,
        )

        pool = await _get_pool()

        # Load current insights + hash for delta computation
        current_row = await pool.fetchrow(
            """
            SELECT insights, insights_hash
            FROM saved_connections
            WHERE id = $1::uuid
            """,
            connection_id,
        )
        if current_row is None:
            logger.warning(
                "Background insights: connection '%s' vanished before save",
                connection_id,
            )
            return

        current_insights_raw = current_row["insights"]
        current_insights: dict[str, Any] = (
            current_insights_raw
            if isinstance(current_insights_raw, dict)
            else json.loads(current_insights_raw)
        )
        current_hash: str | None = current_row["insights_hash"]

        # Per-category SHA-256 delta merge
        merged: dict[str, Any] = dict(current_insights)
        for category, new_data in new_insights.items():
            old_data = current_insights.get(category, {})
            merged[category] = _patch_category_insights(old_data, new_data)

        # Skip the DB write when nothing actually changed
        new_hash = _compute_insights_hash(merged)
        if current_hash == new_hash:
            logger.info(
                "Background insights unchanged for connection '%s' — skipping write",
                connection_id,
            )
            return

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE saved_connections
                SET insights      = $1::jsonb,
                    insights_hash = $2,
                    status        = 'active',
                    updated_at    = now()
                WHERE id = $3::uuid
                """,
                json.dumps(merged),
                new_hash,
                connection_id,
            )

        logger.info(
            "Background insights saved for connection '%s' — %d categories",
            connection_id,
            len(merged),
        )
    except Exception as exc:
        logger.exception(
            "Background insights failed for connection '%s'",
            connection_id,
        )
        try:
            pool = await _get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE saved_connections
                    SET status        = 'active',
                        error_message = $1,
                        updated_at    = now()
                    WHERE id = $2::uuid
                    """,
                    f"Insights generation failed: {exc}",
                    connection_id,
                )
        except Exception:
            logger.exception(
                "Failed to record insight failure for connection '%s'",
                connection_id,
            )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("", response_model=SaveConnectionResponse)
async def create_connection(request: SaveConnectionRequest) -> SaveConnectionResponse:
    """Save a new database connection with its enriched schema and insights.

    The connection credentials, enriched schema output, and insights are
    stored together in the ``saved_connections`` table for later retrieval.
    """
    try:
        saved = await save_connection(
            name=request.name,
            database_type=request.database_type,
            credentials=request.credentials.model_dump(mode="json"),
            enriched_schema=request.enriched_schema,
            insights=request.insights,
            description=request.description,
            status=request.status,
            error_message=request.error_message,
        )
        logger.info(
            "Saved connection '%s' (id=%s, type=%s)",
            saved.name,
            saved.id,
            saved.database_type,
        )
        return SaveConnectionResponse(
            id=saved.id or "",  # always set after DB INSERT
            name=saved.name,
            database_type=saved.database_type,
            status=saved.status,
            created_at=saved.created_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save connection")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=list[SavedConnectionSummary])
async def list_all_connections(
    status: str | None = Query(
        default=None,
        description="Filter by status (active, error, archived)",
    ),
    database_type: str | None = Query(
        default=None,
        description="Filter by database type",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> list[SavedConnectionSummary]:
    """List all saved connections with summary info (no credentials/payloads).

    Supports filtering by ``status`` and ``database_type``, plus pagination
    via ``limit`` and ``offset``.
    """
    try:
        return await list_connections(
            status_filter=status,
            database_type_filter=database_type,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        logger.exception("Failed to list connections")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/search", response_model=list[SavedConnectionSummary])
async def search_connections_endpoint(
    q: str = Query(
        ...,
        min_length=1,
        description="Search query (matched against name and description)",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> list[SavedConnectionSummary]:
    """Search saved connections by name or description (case-insensitive).

    Results are ordered by relevance: exact name match first, then prefix,
    then substring, then description match.
    """
    try:
        return await search_connections(query=q, limit=limit, offset=offset)
    except Exception as exc:
        logger.exception("Failed to search connections")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{connection_id}", response_model=SavedConnection)
async def get_connection_by_id(connection_id: str) -> SavedConnection:
    """Retrieve a full saved connection including credentials and all payloads."""
    connection = await get_connection(connection_id)
    if connection is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )
    return connection


@router.delete("/{connection_id}")
async def delete_connection_by_id(connection_id: str) -> JSONResponse:
    """Delete a saved connection by UUID."""
    deleted = await delete_connection(connection_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )
    logger.info("Deleted connection '%s'", connection_id)
    return JSONResponse(
        content={"message": f"Connection '{connection_id}' deleted"},
        status_code=200,
    )


@router.patch("/{connection_id}", response_model=SavedConnection)
async def update_connection_by_id(
    connection_id: str,
    request: UpdateConnectionRequest,
) -> SavedConnection:
    """Partially update a saved connection (name, description, status, error).

    Only the fields provided in the request body will be updated.
    """
    updated = await update_connection(
        connection_id,
        name=request.name,
        description=request.description,
        status=request.status,
        error_message=request.error_message,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )
    return updated


@router.get("/{connection_id}/details", response_model=SavedConnection)
async def get_connection_details(connection_id: str) -> SavedConnection:
    """Alias for ``GET /connections/{id}`` — clearer intent in the frontend."""
    return await get_connection_by_id(connection_id)


@router.put("/{connection_id}/schema", response_model=SavedConnection)
async def update_connection_schema_endpoint(
    connection_id: str,
    body: dict[str, Any],
) -> SavedConnection:
    """Replace the enriched schema for a saved connection.

    The entire request body is stored as the new ``enriched_schema`` JSON.
    Useful when you want to re-run enrichment externally and push the
    result back without touching the credentials or insights.
    """
    updated = await update_connection_schema(connection_id, body)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )
    return updated


@router.put("/{connection_id}/insights", response_model=SavedConnection)
async def update_connection_insights_endpoint(
    connection_id: str,
    body: dict[str, Any],
) -> SavedConnection:
    """Replace the insights for a saved connection.

    The entire request body is stored as the new ``insights`` JSON.
    Useful when you want to regenerate insights externally and push
    them back without re-running the full pipeline.

    Expected shape: ``{Overview: {kpis, insights, ...}, Operations: {...}, ...}``
    """
    updated = await update_connection_insights(connection_id, body)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )
    return updated


@router.post(
    "/{connection_id}/regenerate-insights/{category}",
    summary="Regenerate a single insight category and persist the delta",
    description=(
        "Generates fresh insights for one category (Overview, Operations, "
        "Finance, Marketing, Sales, Human Resources, IT), computes a "
        "SHA-256 delta against the existing data so unchanged items are "
        "kept verbatim, and patches the saved_connections row with only "
        "the changes."
    ),
)
async def regenerate_category_insights(
    connection_id: str,
    category: str,
) -> dict[str, list[dict[str, Any]]]:
    """Regenerate insights for a single category and persist the delta.

    Steps:
        1. Load existing connection (including current insights)
        2. Generate fresh insights for the requested category
        3. Compute SHA-256 delta between old and new category data
        4. Merge delta into the full insights dict
        5. Patch the DB with the merged results
        6. Return the refreshed category data
    """
    from etl_enrichment_pipeline.agents.insights_agent import InsightsGenerator

    # ── Validate category ────────────────────────────────────
    normalized = category.strip()
    if normalized not in INSIGHT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(INSIGHT_CATEGORIES)}"
            ),
        )

    # ── Load existing connection ─────────────────────────────
    existing = await get_connection(connection_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )

    enriched_schema = existing.enriched_schema or {}
    current_insights: dict[str, Any] = existing.insights or {}

    # ── Generate fresh insights for the category ─────────────
    import asyncio as _asyncio

    loop = asyncio.get_running_loop()
    domain = None if normalized == "Overview" else normalized

    def _generate_single_category() -> dict[str, list[dict[str, Any]]]:
        """Run the async generator in a fresh event loop in this thread."""
        inner = _asyncio.new_event_loop()
        _asyncio.set_event_loop(inner)
        try:
            gen = InsightsGenerator(enriched_metadata=enriched_schema)
            result = inner.run_until_complete(gen.generate(domain=domain))
            return {
                "kpis": result.get("kpis", []),
                "insights": result.get("insights", []),
                "opportunities": result.get("opportunities", []),
                "art_of_the_possible": result.get("art_of_the_possible", []),
            }
        finally:
            inner.close()

    try:
        new_category_data: dict[str, list[dict[str, Any]]] = await loop.run_in_executor(
            _executor, _generate_single_category
        )
    except Exception as exc:
        logger.exception(
            "Insights generation failed for category '%s' on connection '%s'",
            normalized,
            connection_id,
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # ── Compute SHA-256 delta ───────────────────────────────
    old_category_data: dict[str, list[dict[str, Any]]] = current_insights.get(
        normalized, {}
    )
    patched_category = _patch_category_insights(old_category_data, new_category_data)

    changed_count = sum(
        1
        for key in ("kpis", "insights", "opportunities", "art_of_the_possible")
        if old_category_data.get(key, []) != patched_category.get(key, [])
    )

    # ── Merge into full insights dict ───────────────────────
    merged_insights = dict(current_insights)
    merged_insights[normalized] = patched_category

    # ── Persist to DB ───────────────────────────────────────
    updated = await update_connection_insights(connection_id, merged_insights)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found after update",
        )

    logger.info(
        "Regenerated '%s' insights for connection '%s' — %d items changed",
        normalized,
        connection_id,
        changed_count,
    )

    return patched_category


# ---------------------------------------------------------------------------
# Combined endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/extract-and-save",
    response_model=SavedConnection,
    summary="Extract DB schema, enrich, and save connection",
    description=(
        "Takes database credentials, extracts schema metadata from the live "
        "database, runs the enrichment pipeline, optionally generates insights, "
        "and saves everything as a new connection — all in one call."
    ),
)
async def extract_and_save(request: ExtractAndSaveRequest) -> SavedConnection:
    """Combined endpoint: extract schema from a live database, enrich it,
    optionally generate insights, and persist everything as a saved connection.

    Flow:
        1. Connect to the database and extract schema metadata
        2. Run the enrichment pipeline (LLM + rules)
        3. Optionally generate insights
        4. Save credentials + enriched_schema + insights to ``saved_connections``
        5. Return the full ``SavedConnection``
    """
    t_start = time.monotonic()
    loop = asyncio.get_running_loop()
    creds_dict = request.credentials.model_dump(mode="json")

    # Lazy imports to avoid loading langgraph/agents at module level
    from etl_enrichment_pipeline.agents.extraction_agent import (  # noqa: PLC0415
        extract_schema_generic,
    )
    from etl_enrichment_pipeline.core.pipeline import (  # noqa: PLC0415
        run_pipeline_from_raw_json,
    )

    # ── Step 1: Extract ──────────────────────────────────────
    logger.info(
        "Extract-and-save: db_type=%s, host=%s, database=%s, name=%s",
        request.database_type,
        creds_dict.get("host", "?"),
        creds_dict.get("database", "?"),
        request.name,
    )

    try:
        raw_json = await loop.run_in_executor(
            _executor,
            extract_schema_generic,
            request.database_type,
            creds_dict,
        )
    except Exception as exc:
        logger.exception("DB extraction failed for '%s'", request.name)
        # Save as error so the user doesn't lose the credential setup
        saved = await save_connection(
            name=request.name,
            database_type=request.database_type,
            credentials=creds_dict,
            description=request.description,
            status="error",
            error_message=f"Extraction failed: {exc}",
        )
        return saved

    logger.info(
        "Extraction complete for '%s' — %d tables",
        request.name,
        len(raw_json.get("tables", [])),
    )

    # ── Step 2: Enrich ───────────────────────────────────────
    try:
        enriched_schema = await loop.run_in_executor(
            _executor,
            run_pipeline_from_raw_json,
            raw_json,
            f"connection:{request.name}:{request.database_type}",
        )
    except Exception as exc:
        logger.exception("Enrichment failed for '%s'", request.name)
        saved = await save_connection(
            name=request.name,
            database_type=request.database_type,
            credentials=creds_dict,
            enriched_schema=raw_json,  # save raw schema at least
            description=request.description,
            status="error",
            error_message=f"Enrichment failed: {exc}",
        )
        return saved

    # ── Step 3: Save enriched schema immediately ────────────────
    # Insights will be generated in the background so the user gets
    # the response as fast as enrichment allows.
    saved = await save_connection(
        name=request.name,
        database_type=request.database_type,
        credentials=creds_dict,
        enriched_schema=enriched_schema,
        insights={},  # placeholder — filled by background task
        description=request.description,
        status="active",
    )

    # ── Step 4: Fire background insight generation (non-blocking) ─
    if request.generate_insights and saved.id:
        asyncio.create_task(
            _background_generate_and_update(
                saved.id,  # narrowed: always a real UUID after INSERT
                enriched_schema,
            )
        )
        logger.info(
            "Background insights task launched for '%s' (id=%s)",
            saved.name,
            saved.id,
        )

    elapsed = time.monotonic() - t_start
    logger.info(
        "Extract-and-save complete for '%s' (id=%s) — %.1fs",
        saved.name,
        saved.id,
        elapsed,
    )

    return saved


@router.post(
    "/{connection_id}/refresh",
    response_model=SavedConnection,
    summary="Re-run pipeline on an existing connection",
    description=(
        "Re-extracts schema from the saved database credentials, re-runs the "
        "enrichment pipeline, optionally generates insights, and updates the "
        "connection record with the fresh results."
    ),
)
async def refresh_connection(
    connection_id: str,
    generate_insights: bool = Query(
        default=False,
        description="Whether to also regenerate insights",
    ),
) -> SavedConnection:
    """Re-run extraction + enrichment + optional insights on an existing saved
    connection. Uses the stored credentials to reconnect to the database.

    This is useful after the source database schema has changed.
    """
    t_start = time.monotonic()
    loop = asyncio.get_running_loop()

    # Lazy imports to avoid loading langgraph/agents at module level
    from etl_enrichment_pipeline.agents.extraction_agent import (  # noqa: PLC0415
        extract_schema_generic,
    )
    from etl_enrichment_pipeline.core.pipeline import (  # noqa: PLC0415
        run_pipeline_from_raw_json,
    )

    # ── Load existing connection ──────────────────────────────
    existing = await get_connection(connection_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )

    creds_dict = existing.credentials.model_dump(mode="json")
    logger.info(
        "Refreshing connection '%s' (id=%s, type=%s)",
        existing.name,
        existing.id,
        existing.database_type,
    )

    # ── Step 1: Re-extract ────────────────────────────────────
    try:
        raw_json = await loop.run_in_executor(
            _executor,
            extract_schema_generic,
            existing.database_type,
            creds_dict,
        )
    except Exception as exc:
        logger.exception("Re-extraction failed for '%s'", existing.name)
        await update_connection(
            connection_id,
            status="error",
            error_message=f"Re-extraction failed: {exc}",
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # ── Step 2: Re-enrich ─────────────────────────────────────
    try:
        enriched_schema = await loop.run_in_executor(
            _executor,
            run_pipeline_from_raw_json,
            raw_json,
            f"connection:{existing.name}:refresh",
        )
    except Exception as exc:
        logger.exception("Re-enrichment failed for '%s'", existing.name)
        await update_connection(
            connection_id,
            status="error",
            error_message=f"Re-enrichment failed: {exc}",
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # ── Step 3: Update enriched schema immediately ──────────────
    # Insights will be regenerated in the background so the user
    # gets the updated schema back as fast as enrichment allows.
    pool = await _get_pool()
    row = await pool.fetchrow(
        """
        UPDATE saved_connections
        SET enriched_schema = $1::jsonb,
            insights        = '{}'::jsonb,
            insights_hash   = NULL,
            status          = 'active',
            error_message   = NULL,
            updated_at      = now()
        WHERE id = $2::uuid
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, insights_hash, status, error_message,
                  created_at, updated_at
        """,
        json.dumps(enriched_schema),
        connection_id,
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found after refresh",
        )

    updated = _row_to_connection(row)

    # ── Step 4: Fire background insight regeneration (non-blocking) ─
    if generate_insights:
        asyncio.create_task(
            _background_generate_and_update(
                connection_id,
                enriched_schema,
            )
        )
        logger.info(
            "Background insights regeneration task launched for '%s' (id=%s)",
            existing.name,
            connection_id,
        )

    elapsed = time.monotonic() - t_start
    logger.info(
        "Refresh complete for '%s' (id=%s) — %.1fs",
        existing.name,
        connection_id,
        elapsed,
    )

    return updated


__all__ = [
    "ExtractAndSaveRequest",
    "SaveConnectionRequest",
    "SaveConnectionResponse",
    "SavedConnection",
    "SavedConnectionSummary",
    "UpdateConnectionRequest",
    "close_pool",
    "get_connection",
    "initialize_schema",
    "router",
    "save_connection",
    "update_connection_insights",
    "update_connection_schema",
]
