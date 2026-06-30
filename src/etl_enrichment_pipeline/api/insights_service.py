"""Insights API router — KPIs, Insights, Opportunities, Art of the Possible.

Insights are scoped to a saved connection.  A ``connection_id`` is required for
every generation request so that:

* Insights are only produced from a fully-extracted and enriched schema.
* Each connection's insights are isolated — one connection cannot accidentally
  read another connection's data.
* The global ``output/enriched_metadata.json`` file is never used by this
  endpoint; the enriched schema stored in ``saved_connections`` is used instead.

Flow
----
1. Load the connection by ``connection_id``.
2. Guard: connection must exist, be ``active``, and have a non-empty enriched
   schema (i.e. extraction + enrichment must be complete).
3. Create an :class:`~etl_enrichment_pipeline.agents.insights_agent.InsightsGenerator`
   with the connection's ``enriched_schema``.
4. Call ``generate(domain=..., entity=...)`` for a single LLM call.
5. Return the four insight categories as structured JSON.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.insights_agent import InsightsGenerator
from etl_enrichment_pipeline.api.connection_service import get_connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class InsightsRequest(BaseModel):
    """Request body for the insights generation endpoint."""

    connection_id: str = Field(
        ...,
        description=(
            "UUID of the saved connection whose enriched schema will be used. "
            "The connection must be active and have completed extraction + enrichment."
        ),
    )
    domain: str | None = Field(
        default=None,
        description=(
            "Optional domain filter (e.g. 'Flight Operations', 'Human Resources'). "
            "When omitted, insights span all domains found in the schema."
        ),
    )
    entity: str | None = Field(
        default=None,
        description="Optional entity focus (e.g. 'Flight', 'Employee')",
    )


class InsightsResponse(BaseModel):
    """Response body containing all four insight categories."""

    connection_id: str = Field(
        ...,
        description="The connection ID this response was generated from",
    )
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
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=InsightsResponse)
async def generate_insights(request: InsightsRequest) -> InsightsResponse:
    """Generate KPIs, Insights, Opportunities, and Art of the Possible from
    the enriched schema of a specific saved connection.

    The connection must:

    * Exist in the ``saved_connections`` table.
    * Have ``status == 'active'`` (extraction + enrichment complete).
    * Have a non-empty ``enriched_schema`` (at least one table).

    Raises HTTP 404 if the connection is not found, HTTP 400 if the
    connection is not ready (still processing, errored, or not yet enriched).
    """
    # ── 1. Load the connection ───────────────────────────────────────────────
    try:
        connection = await get_connection(request.connection_id)
    except Exception as exc:
        logger.exception(
            "Failed to load connection '%s' for insights generation",
            request.connection_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Connection database is unavailable — cannot load connection. "
                f"Detail: {exc}"
            ),
        ) from exc

    if connection is None:
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{request.connection_id}' not found.",
        )

    # ── 2. Guard: connection must be active and fully enriched ───────────────
    if connection.status != "active":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Connection '{request.connection_id}' is not active "
                f"(current status: '{connection.status}'). "
                "Complete extraction and enrichment before requesting insights."
            ),
        )

    enriched_schema: dict[str, Any] = connection.enriched_schema or {}
    tables = enriched_schema.get("tables") or []
    if not tables:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Connection '{request.connection_id}' has no enriched schema tables. "
                "Run extraction and enrichment first, then retry."
            ),
        )

    # ── 3. Generate insights from the connection's enriched schema ───────────
    logger.info(
        "Generating insights for connection '%s' (name=%s, tables=%d, "
        "domain=%s, entity=%s)",
        request.connection_id,
        connection.name,
        len(tables),
        request.domain or "<all>",
        request.entity or "<none>",
    )

    try:
        generator = InsightsGenerator(enriched_metadata=enriched_schema)
        result = await generator.generate(
            domain=request.domain,
            entity=request.entity,
        )
    except Exception as exc:
        logger.exception(
            "Insights generation failed for connection '%s'",
            request.connection_id,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "Insights generated for connection '%s': %d KPIs, %d insights, "
        "%d opportunities, %d art_of_the_possible",
        request.connection_id,
        len(result.get("kpis", [])),
        len(result.get("insights", [])),
        len(result.get("opportunities", [])),
        len(result.get("art_of_the_possible", [])),
    )

    return InsightsResponse(
        connection_id=request.connection_id,
        kpis=result.get("kpis", []),
        insights=result.get("insights", []),
        opportunities=result.get("opportunities", []),
        art_of_the_possible=result.get("art_of_the_possible", []),
    )


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
