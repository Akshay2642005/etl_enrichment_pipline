"""Extraction API router and service — mirrors nl2sql_service.py pattern.

Two endpoints:
- ``POST /extract`` — extract schema from a live database + run enrichment
- ``POST /parse-sql`` — parse SQL DDL content + run enrichment

All logic lives here: schemas, service functions, and the APIRouter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.ddl_parser import ddl_to_json
from etl_enrichment_pipeline.agents.extraction_agent import extract_schema_generic
from etl_enrichment_pipeline.core.pipeline import run_pipeline_from_raw_json
from etl_enrichment_pipeline.core.store_loader import load_enriched_metadata

logger = logging.getLogger(__name__)

# ===================================================================
# Thread pool — shared across all endpoint handlers
# ===================================================================

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline")

# Embedding status tracker — frontend polls this after pipeline runs
_EMBEDDING_STATUS: dict[str, Any] = {
    "status": "idle",
    "updated_at": None,
    "error": None,
}


def _run_pipeline(raw_json: dict[str, Any], source_label: str) -> dict[str, Any]:
    """Run the enrichment pipeline (blocking — called in executor thread)."""
    return run_pipeline_from_raw_json(raw_json, source_label=source_label)


async def _embed_in_background() -> None:
    """Load enriched metadata into pgvector + Neo4j in background.

    Fire-and-forget — updates _EMBEDDING_STATUS, never raises.
    """
    _EMBEDDING_STATUS.update(
        {
            "status": "embedding",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": None,
        }
    )
    try:
        result = await load_enriched_metadata()
        _EMBEDDING_STATUS.update(
            {
                "status": "complete",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "error": None,
            }
        )
        logger.info(
            "Background embedding complete — %d tables indexed",
            len(result.get("tables", [])),
        )
    except FileNotFoundError:
        _EMBEDDING_STATUS.update(
            {
                "status": "failed",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "error": "Enriched metadata file not found",
            }
        )
        logger.warning(
            "Enriched metadata file not found — skipping background embedding"
        )  # noqa: E501
    except Exception:
        _EMBEDDING_STATUS.update(
            {
                "status": "failed",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "error": "Embedding failed (stores may be unavailable)",
            }
        )
        logger.exception("Background embedding failed (stores may be unavailable)")


# ===================================================================
# Schemas
# ===================================================================


class ExtractDBRequest(BaseModel):
    """Extract schema from a live database using connection credentials."""

    database_type: str = Field(
        ...,
        description="Database type: postgres, mysql, mariadb, sqlserver, oracle, sqlite",  # noqa: E501
    )
    credentials: dict[str, Any] = Field(
        ...,
        description=(
            "Connection credentials. Must include 'host', 'database'. "
            "Optionally: 'port', 'username', 'password'."
        ),
    )


class ParseSQLRequest(BaseModel):
    """Parse SQL DDL content to extract schema metadata."""

    sql_text: str = Field(
        ...,
        min_length=1,
        description="SQL DDL content (CREATE TABLE / CREATE VIEW statements)",
    )
    database_type: str = Field(
        default="postgresql",
        description="Database vendor (postgresql, mysql, etc.)",
    )
    schema_name: str = Field(
        default="public",
        description="Target database schema (public, dbo, etc.)",
        validation_alias="schema",
    )


# ===================================================================
# Error schemas
# ===================================================================


class ErrorDetail(BaseModel):
    """Structured error detail returned on failure."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: str | None = Field(default=None, description="Optional additional context")


class ErrorResponse(BaseModel):
    """Top-level error response body."""

    detail: str = Field(
        default="",
        description="Human-readable error detail for the frontend",
    )


def _error_json(status_code: int, code: str, message: str) -> JSONResponse:
    """Build a structured error JSON response the frontend can parse."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=message).model_dump(mode="json"),
    )


# ===================================================================
# Service functions
# ===================================================================


async def _extract_from_db(req: ExtractDBRequest) -> dict[str, Any]:
    """Extract schema from a live database, then run enrichment."""
    creds: dict[str, Any] = dict(req.credentials)
    loop = asyncio.get_running_loop()

    def _extract() -> dict[str, Any]:
        return extract_schema_generic(req.database_type, creds)

    raw_json = await loop.run_in_executor(_executor, _extract)
    return await loop.run_in_executor(
        _executor,
        _run_pipeline,
        raw_json,
        f"api:db:{req.database_type}",
    )


async def _parse_sql(req: ParseSQLRequest) -> dict[str, Any]:
    """Parse SQL DDL content, then run enrichment."""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sql",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(req.sql_text)
            tmp_path = Path(tmp.name)

        raw_json = ddl_to_json(
            filepath=str(tmp_path),
            database_type=req.database_type,
            schema=req.schema_name,
        )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _executor,
            _run_pipeline,
            raw_json,
            f"api:sql:{req.database_type}",
        )
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# ===================================================================
# Router
# ===================================================================

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "ok",
            "service": "etl-enrichment-pipeline",
            "version": "0.1.0",
        },
        status_code=200,
    )


@router.get("/embedding/status")
async def embedding_status() -> JSONResponse:
    """Return the current embedding status for frontend polling."""
    return JSONResponse(content=_EMBEDDING_STATUS, status_code=200)


@router.post(
    "/extract",
    summary="Extract and enrich schema from a live database",
    description=(
        "Accepts database connection credentials, connects to the live "
        "database, extracts its schema metadata, runs the enrichment "
        "pipeline, and returns the enriched result."
    ),
)
async def extract(request: Request) -> JSONResponse:
    """Extract schema from a live database connection."""
    t_start = time.monotonic()

    try:
        body_raw: dict[str, Any] = await request.json()
    except json.JSONDecodeError as exc:
        return _error_json(
            400, "invalid_json", f"Request body is not valid JSON: {exc}"
        )  # noqa: E501

    try:
        parsed = ExtractDBRequest.model_validate(body_raw)
    except Exception as exc:
        return _error_json(422, "validation_error", str(exc))

    logger.info(
        "Extract request — db_type=%s, host=%s, database=%s",
        parsed.database_type,
        parsed.credentials.get("host", "?"),
        parsed.credentials.get("database", "?"),
    )

    try:
        result = await _extract_from_db(parsed)
    except HTTPException:
        raise
    except Exception as exc:
        elapsed = time.monotonic() - t_start
        logger.error("Extraction failed after %.1fs: %s", elapsed, exc, exc_info=True)
        return _error_json(500, "pipeline_error", str(exc))

    # Save to disk so Insights and NL2SQL services can use it
    try:
        out_path = Path("output/enriched_metadata.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save enriched metadata to disk: %s", exc)

    _EMBEDDING_STATUS.update(
        {
            "status": "embedding",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": None,
        }
    )
    asyncio.ensure_future(_embed_in_background())

    elapsed = time.monotonic() - t_start
    logger.info(
        "Extraction complete — %.1fs, %d tables, %d views, %d relationships",
        elapsed,
        len(result.get("tables", [])),
        len(result.get("views", [])),
        len(result.get("relationships", [])),
    )

    return JSONResponse(
        content={"data": result},
        status_code=200,
    )


@router.post(
    "/parse-sql",
    summary="Parse SQL DDL and enrich schema metadata",
    description=(
        "Accepts inline SQL DDL content (CREATE TABLE / CREATE VIEW), "
        "parses it into canonical schema metadata, runs the enrichment "
        "pipeline, and returns the enriched result."
    ),
)
async def parse_sql(request: Request) -> JSONResponse:
    """Parse SQL DDL content and run enrichment."""
    t_start = time.monotonic()

    try:
        body_raw: dict[str, Any] = await request.json()
    except json.JSONDecodeError as exc:
        return _error_json(
            400, "invalid_json", f"Request body is not valid JSON: {exc}"
        )  # noqa: E501

    try:
        parsed = ParseSQLRequest.model_validate(body_raw)
    except Exception as exc:
        return _error_json(422, "validation_error", str(exc))

    logger.info(
        "Parse-SQL request — db_type=%s, schema=%s, %d chars",
        parsed.database_type,
        parsed.schema_name,
        len(parsed.sql_text),
    )

    try:
        result = await _parse_sql(parsed)
    except HTTPException:
        raise
    except Exception as exc:
        elapsed = time.monotonic() - t_start
        logger.error("SQL parsing failed after %.1fs: %s", elapsed, exc, exc_info=True)
        return _error_json(500, "pipeline_error", str(exc))

    # Save to disk so Insights and NL2SQL services can use it
    try:
        out_path = Path("output/enriched_metadata.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save enriched metadata to disk: %s", exc)

    _EMBEDDING_STATUS.update(
        {
            "status": "embedding",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": None,
        }
    )
    asyncio.ensure_future(_embed_in_background())

    elapsed = time.monotonic() - t_start
    logger.info(
        "Parse-SQL complete — %.1fs, %d tables, %d views, %d relationships",
        elapsed,
        len(result.get("tables", [])),
        len(result.get("views", [])),
        len(result.get("relationships", [])),
    )

    return JSONResponse(
        content={"data": result},
        status_code=200,
    )


__all__ = [
    "ExtractDBRequest",
    "ParseSQLRequest",
    "router",
]
