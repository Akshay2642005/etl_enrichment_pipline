"""ETL Schema Intelligence API — FastAPI application.

Lean app setup only.  Router and schemas live in
:mod:`etl_enrichment_pipeline.api.extraction_service`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from etl_enrichment_pipeline.api.connection_service import (
    close_pool as close_connections_pool,
)
from etl_enrichment_pipeline.api.connection_service import (
    initialize_schema as init_connections_schema,
)
from etl_enrichment_pipeline.api.connection_service import (
    router as connections_router,
)
from etl_enrichment_pipeline.api.extraction_service import (
    router,
)
from etl_enrichment_pipeline.api.insights_service import router as insights_router
from etl_enrichment_pipeline.api.nl2sql_service import (
    nl2sql_lifespan,
)
from etl_enrichment_pipeline.api.nl2sql_service import (
    router as nl2sql_router,
)
from etl_enrichment_pipeline.api.quality_service import router as quality_router
from etl_enrichment_pipeline.api.shared_state import (
    ensure_stores_initialized,
    get_embedding_service,
)
from etl_enrichment_pipeline.core.log_buffer import buffer
from etl_enrichment_pipeline.core.store_loader import load_enriched_metadata

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Non-blocking lifespan — server accepts requests immediately.

    All heavy initialisation (embedding model, vector store, graph store,
    connections table) runs in a background task so the server is ready
    to accept requests within milliseconds.

    Services are lazily initialised on first request — the first NL2SQL
    or Insights call may be slower while the embedding model finishes
    loading, but the server itself is never blocked.
    """
    async with nl2sql_lifespan(app):
        task = asyncio.create_task(
            _background_init(),
            name="background-initializer",
        )
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await close_connections_pool()


async def _background_init() -> None:
    """Background task: initialise all heavy services.

    Runs concurrently — server is already accepting requests while this
    executes.  Every failure is logged but never re-raised, so a single
    unavailable service doesn't take down the whole server.
    """
    # ── 1. Connection persistence table (fast) ────────────────
    try:
        await init_connections_schema()
        logger.info("saved_connections table ready")
    except Exception:
        logger.warning(
            "Failed to initialise saved_connections table — "
            "connection persistence will be unavailable"
        )

    # ── 2. Embedding model (sentence-transformers — 15-30s) ────
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, get_embedding_service)
        logger.info("Embedding model loaded")
    except Exception:
        logger.warning("Failed to load embedding model — will lazy-init on first use")

    # ── 3. Vector + Graph stores (network connections) ─────────
    try:
        await ensure_stores_initialized()
        logger.info("Vector + Graph stores initialised")
    except Exception:
        logger.warning(
            "Failed to initialise stores — will lazy-init on first use"
        )

    # ── 4. Load enriched metadata into stores (populates data) ─
    try:
        await load_enriched_metadata()
        logger.info("Schema stores populated — all services ready")
    except FileNotFoundError:
        logger.warning(
            "Enriched metadata not found — run the enrichment pipeline first. "
            "NL2SQL / Insights / Quality may return empty results until "
            "stores are populated."
        )
    except Exception:
        logger.exception(
            "Failed to populate schema stores — NL2SQL/Insights/Quality "
            "may return empty results."
        )


app = FastAPI(
    title="ETL Schema Intelligence",
    description=(
        "AI-powered Schema Intelligence Platform. "
        "Accepts SQL DDL content or database credentials "
        "and returns fully enriched schema metadata."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────
app.include_router(router)
app.include_router(quality_router)
app.include_router(insights_router)
app.include_router(nl2sql_router)
app.include_router(connections_router)


# ── Pipeline log endpoint ───────────────────────────────────


@app.get("/logs")
async def get_pipeline_logs(
    lines: Annotated[int, Query(description="Number of recent log lines")] = 200,
    level: Annotated[
        str, Query(description="Minimum log level (DEBUG / INFO / WARNING / ERROR)")
    ] = "DEBUG",
) -> JSONResponse:
    """Return the most recent pipeline log entries from the in-memory buffer."""
    return JSONResponse(
        content={"lines": buffer.get_logs(lines=lines, level=level)}
    )


# ── Exception handlers ──────────────────────────────────────


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    logger.warning(
        "HTTP %d on %s %s: %s",
        exc.status_code,
        request.method,
        request.url,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail
        if isinstance(exc.detail, str)
        else str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unhandled exception processing %s %s", request.method, request.url
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "debug": traceback.format_exc()
            if logger.isEnabledFor(logging.DEBUG)
            else None,
        },
    )


__all__ = ["app"]
