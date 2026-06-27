"""Insights API router — KPIs, Insights, Opportunities, Art of the Possible.

Exposes a FastAPI ``APIRouter`` at ``/api/v1/insights`` that wraps the
:class:`~etl_enrichment_pipeline.agents.insights_agent.InsightsGenerator`
with a lazy-singleton lifecycle identical to the NL2SQL service pattern.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.insights_agent import InsightsGenerator
from etl_enrichment_pipeline.api.shared_state import (
    ensure_stores_initialized,
    get_graph_store,
    get_vector_store,
    load_metadata,
)

logger = logging.getLogger(__name__)

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
        default=[],
        description="Key Performance Indicators (3-6 items)",
    )
    insights: list[dict[str, Any]] = Field(
        default=[],
        description="Data-driven business insights (3-5 items)",
    )
    opportunities: list[dict[str, Any]] = Field(
        default=[],
        description="Operational improvement opportunities (2-4 items)",
    )
    art_of_the_possible: list[dict[str, Any]] = Field(
        default=[],
        description="Transformative / visionary capabilities (2-3 items)",
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

# ---------------------------------------------------------------------------
# Lazy singleton state
# ---------------------------------------------------------------------------

_insights_generator: InsightsGenerator | None = None


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
        await ensure_stores_initialized()

        metadata = load_metadata()

        generator = InsightsGenerator(
            enriched_metadata=metadata,
            vector_store=get_vector_store(),
            graph_store=get_graph_store(),
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
