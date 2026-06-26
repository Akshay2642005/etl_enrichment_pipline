"""Insights API router — KPIs, Insights, Opportunities, Art of the Possible.

Exposes a FastAPI ``APIRouter`` at ``/api/v1/insights`` that wraps the
:class:`~etl_enrichment_pipeline.agents.insights_agent.InsightsGenerator`
with a lazy-singleton lifecycle identical to the NL2SQL service pattern.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.insights_agent import InsightsGenerator
from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
from etl_enrichment_pipeline.core.graph_store import GraphStore
from etl_enrichment_pipeline.core.store_loader import (
    load_enriched_metadata,  # noqa: F401  # re-export for external callers
)
from etl_enrichment_pipeline.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default metadata path
# ---------------------------------------------------------------------------

_DEFAULT_METADATA_PATH = (
    Path(__file__).resolve().parents[3] / "output" / "enriched_metadata.json"
)

_METADATA_PATH = os.getenv("METADATA_PATH", str(_DEFAULT_METADATA_PATH))

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class InsightsRequest(BaseModel):
    """Request body for the insights generation endpoint."""

    domain: str | None = Field(
        default=None,
        description=(
            "Optional domain filter (e.g. 'Flight Operations', 'Human Resources')"
        ),
    )
    entity: str | None = Field(
        default=None,
        description="Optional entity focus (e.g. 'Flight', 'Employee')",
    )


class InsightsResponse(BaseModel):
    """Response body containing all four insight categories."""

    kpis: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Key Performance Indicators (3-6 items)",
    )
    insights: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Data-driven business insights (3-5 items)",
    )
    opportunities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Operational improvement opportunities (2-4 items)",
    )
    art_of_the_possible: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Transformative / visionary capabilities (2-3 items)",
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

# ---------------------------------------------------------------------------
# Lazy singleton state
# ---------------------------------------------------------------------------

_metadata: dict[str, Any] | None = None
_embedding_service: EmbeddingService | None = None
_vector_store: VectorStore | None = None
_graph_store: GraphStore | None = None
_insights_generator: InsightsGenerator | None = None
_store_initialized: bool = False


def _load_metadata() -> dict[str, Any]:
    global _metadata
    if _metadata is None:
        path = Path(_METADATA_PATH)
        if not path.exists():
            logger.warning("Metadata file not found at %s — using empty metadata", path)
            _metadata = {}
        else:
            _metadata = json.loads(path.read_text(encoding="utf-8"))
    return _metadata


def _get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def _get_graph_store() -> GraphStore:
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore()
    return _graph_store


async def _ensure_stores_initialized() -> None:
    global _store_initialized
    if not _store_initialized:
        vs = _get_vector_store()
        await vs.initialize_schema()
        gs = _get_graph_store()
        await gs.initialize_schema()
        _store_initialized = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=InsightsResponse)
async def generate_insights(request: InsightsRequest) -> InsightsResponse:
    """Generate KPIs, Insights, Opportunities, and Art of the Possible from
    enriched schema metadata.

    Orchestrates the full insights pipeline:

    1. Ensure vector + graph stores are initialised
    2. Load enriched metadata from disk
    3. Create an ``InsightsGenerator`` with metadata + stores
    4. Call ``generate(domain=..., entity=...)`` for a single LLM call
    5. Return all four insight categories as structured JSON
    """
    try:
        await _ensure_stores_initialized()

        metadata = _load_metadata()

        generator = InsightsGenerator(
            enriched_metadata=metadata,
            vector_store=_get_vector_store(),
            graph_store=_get_graph_store(),
        )

        result = await generator.generate(
            domain=request.domain,
            entity=request.entity,
        )

        return InsightsResponse(
            kpis=result.get("kpis", []),
            insights=result.get("insights", []),
            opportunities=result.get("opportunities", []),
            art_of_the_possible=result.get("art_of_the_possible", []),
        )

    except Exception as exc:
        logger.exception("Insights generation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check for the insights service."""
    return {
        "status": "ok",
        "service": "insights",
    }


__all__ = [
    "InsightsRequest",
    "InsightsResponse",
    "router",
]
