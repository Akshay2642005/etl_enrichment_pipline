"""Standalone FastAPI application for the NL2SQL service — separate process.

Run with::

    uv run main.py nl2sql          # via the project entry point
    uv run uvicorn src.etl_enrichment_pipeline.api.nl2sql_app:app --port 8001
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI

# ── Load .env before any service initialises ────────────────────────
# When started via `uvicorn` directly (not `uv run main.py`), the
# process environment may not contain the PG / Neo4j credentials.
# We search upward from this file for the project .env file.
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)
    logging.getLogger(__name__).info("Loaded environment from %s", _env_path)
else:
    logging.getLogger(__name__).warning(
        ".env not found at %s — relying on process environment", _env_path
    )

from etl_enrichment_pipeline.api.nl2sql_service import nl2sql_lifespan, router
from etl_enrichment_pipeline.core.store_loader import load_enriched_metadata

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize NL2SQL services and load enriched metadata into stores."""
    async with nl2sql_lifespan(app):
        try:
            await load_enriched_metadata()
            logger.info("Schema stores populated — NL2SQL ready")
        except FileNotFoundError:
            logger.warning(
                "No enriched metadata found — run the enrichment pipeline first. "
                "NL2SQL will return empty results until stores are populated."
            )
        yield


app = FastAPI(
    title="NL2SQL Service",
    description="Natural-language to PostgreSQL SQL query service — separate process",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


__all__ = ["app"]
