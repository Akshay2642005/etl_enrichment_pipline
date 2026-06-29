"""Connection persistence API router — save, list, get, delete, and run pipeline.

Provides endpoints to persist database connection details along with their
enriched schema metadata and generated insights into a PostgreSQL-backed
``saved_connections`` table.

Endpoints:
    POST   /connections                   — save a new connection
    GET    /connections                   — list saved connections (summaries)
    GET    /connections/search            — search connections by name
    GET    /connections/{id}              — get a single connection (full payload)
    PATCH  /connections/{id}              — partial update (name, description, status, error)
    PUT    /connections/{id}/schema       — replace enriched schema only
    PUT    /connections/{id}/insights     — replace insights only
    DELETE /connections/{id}              — delete a saved connection
    GET    /connections/{id}/details      — alias for get
    POST   /connections/extract-and-save  — extract DB + enrich + save in one call
    POST   /connections/{id}/refresh      — re-run pipeline on an existing connection
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.extraction_agent import extract_schema_generic
from etl_enrichment_pipeline.core.pipeline import run_pipeline_from_raw_json
from etl_enrichment_pipeline.models.connection_schema import (
    CREATE_SAVED_CONNECTIONS_TABLE_SQL,
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
    os.getenv("PGVECTOR_DSN", "postgresql://postgres:postgres@localhost:5432/schema_embeddings"),
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
    """Create the ``saved_connections`` table if it doesn't exist."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SAVED_CONNECTIONS_TABLE_SQL)
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
    pool = await _get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO saved_connections
            (name, description, database_type, credentials,
             enriched_schema, insights, status, error_message)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7, $8)
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, status, error_message,
                  created_at, updated_at
        """,
        name,
        description,
        database_type,
        json.dumps(credentials),
        json.dumps(enriched_schema or {}),
        json.dumps(insights or {}),
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
               enriched_schema, insights, status, error_message,
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
    params.append(datetime.now(timezone.utc))
    param_idx += 1

    params.append(connection_id)
    query = f"""
        UPDATE saved_connections
        SET {', '.join(set_clauses)}
        WHERE id = ${param_idx}::uuid
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, status, error_message,
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
                  enriched_schema, insights, status, error_message,
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
    """Replace the insights for a saved connection."""
    pool = await _get_pool()
    row = await pool.fetchrow(
        """
        UPDATE saved_connections
        SET insights = $1::jsonb, updated_at = now()
        WHERE id = $2::uuid
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, status, error_message,
                  created_at, updated_at
        """,
        json.dumps(insights),
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
            row["credentials"] if isinstance(row["credentials"], dict)
            else json.loads(row["credentials"])
        ),
        enriched_schema=(
            row["enriched_schema"] if isinstance(row["enriched_schema"], dict)
            else json.loads(row["enriched_schema"])
        ),
        insights=(
            row["insights"] if isinstance(row["insights"], dict)
            else json.loads(row["insights"])
        ),
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
            id=saved.id,
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
        ..., min_length=1, description="Search query (matched against name and description)"
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

    Expected shape: ``{"kpis": [...], "insights": [...], "opportunities": [...], "art_of_the_possible": [...]}``
    """
    updated = await update_connection_insights(connection_id, body)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found",
        )
    return updated


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

    # ── Step 3: Insights (optional) ───────────────────────────
    insights: dict[str, Any] = {}
    if request.generate_insights:
        try:
            from etl_enrichment_pipeline.agents.insights_agent import InsightsGenerator

            generator = InsightsGenerator(
                enriched_metadata=enriched_schema,
            )
            insights_result = await generator.generate()
            insights = {
                "kpis": insights_result.get("kpis", []),
                "insights": insights_result.get("insights", []),
                "opportunities": insights_result.get("opportunities", []),
                "art_of_the_possible": insights_result.get("art_of_the_possible", []),
            }
        except Exception as exc:
            logger.warning("Insights generation failed for '%s': %s", request.name, exc)
            insights = {"error": str(exc)}

    # ── Step 4: Save ──────────────────────────────────────────
    saved = await save_connection(
        name=request.name,
        database_type=request.database_type,
        credentials=creds_dict,
        enriched_schema=enriched_schema,
        insights=insights,
        description=request.description,
        status="active",
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

    # ── Step 3: Regenerate insights (optional) ────────────────
    insights: dict[str, Any] = {}
    if generate_insights:
        try:
            from etl_enrichment_pipeline.agents.insights_agent import InsightsGenerator

            generator = InsightsGenerator(
                enriched_metadata=enriched_schema,
            )
            insights_result = await generator.generate()
            insights = {
                "kpis": insights_result.get("kpis", []),
                "insights": insights_result.get("insights", []),
                "opportunities": insights_result.get("opportunities", []),
                "art_of_the_possible": insights_result.get("art_of_the_possible", []),
            }
        except Exception as exc:
            logger.warning(
                "Insights regeneration failed for '%s': %s", existing.name, exc
            )

    # ── Step 4: Update the connection directly ────────────────
    pool = await _get_pool()
    row = await pool.fetchrow(
        """
        UPDATE saved_connections
        SET enriched_schema = $1::jsonb,
            insights        = $2::jsonb,
            status          = 'active',
            error_message   = NULL,
            updated_at      = now()
        WHERE id = $3::uuid
        RETURNING id, name, description, database_type, credentials,
                  enriched_schema, insights, status, error_message,
                  created_at, updated_at
        """,
        json.dumps(enriched_schema),
        json.dumps(insights),
        connection_id,
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{connection_id}' not found after refresh",
        )

    elapsed = time.monotonic() - t_start
    logger.info(
        "Refresh complete for '%s' (id=%s) — %.1fs",
        existing.name,
        connection_id,
        elapsed,
    )

    return _row_to_connection(row)


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
