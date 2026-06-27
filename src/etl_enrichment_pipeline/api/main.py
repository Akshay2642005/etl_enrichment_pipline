"""ETL Schema Intelligence API — FastAPI application.

Lean app setup only.  Router and schemas live in
:mod:`etl_enrichment_pipeline.api.extraction_service`.
"""

from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from etl_enrichment_pipeline.api.extraction_service import ErrorDetail, ErrorResponse, router
from etl_enrichment_pipeline.api.insights_service import router as insights_router
from etl_enrichment_pipeline.api.nl2sql_service import (
    nl2sql_lifespan,
    router as nl2sql_router,
)
from etl_enrichment_pipeline.api.quality_service import router as quality_router
from etl_enrichment_pipeline.core.store_loader import load_enriched_metadata

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize NL2SQL services and load enriched metadata into stores."""
    async with nl2sql_lifespan(app):
        try:
            await load_enriched_metadata()
            logger.info("Schema stores populated — all services ready")
        except (FileNotFoundError, KeyError) as exc:
            logger.warning(
                "Schema stores not populated (%s: %s) — run the enrichment pipeline first. "
                "NL2SQL / Insights / Quality may return empty results until "
                "stores are populated.",
                type(exc).__name__,
                exc,
            )
        yield


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
