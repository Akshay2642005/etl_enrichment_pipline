"""Quality assessment API router — evaluates schema quality across 6 dimensions.

See ``agents/quality_agent.py`` for the underlying assessment logic.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.quality_agent import QualityAnalyst
from etl_enrichment_pipeline.api.shared_state import (
    ensure_stores_initialized,
    load_metadata,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class QualityRequest(BaseModel):
    table_name: str | None = Field(
        default=None,
        description="Optional table name to scope the assessment",
    )
    domain: str | None = Field(
        default=None,
        description="Optional domain to scope the assessment",
    )


class QualityResponse(BaseModel):
    overall_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall quality score (0.0–1.0)"
    )
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    relationships: float = Field(default=0.0, ge=0.0, le=1.0)
    naming_convention: float = Field(default=0.0, ge=0.0, le=1.0)
    documentation: float = Field(default=0.0, ge=0.0, le=1.0)
    normalization: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: list[dict[str, Any]] = Field(
        default=[], description="List of quality issues found"
    )
    recommendations: list[str] = Field(
        default=[], description="Actionable improvement recommendations"
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])

# ---------------------------------------------------------------------------
# Lazy singleton state (service-specific only)
# ---------------------------------------------------------------------------

_quality_agent: QualityAnalyst | None = None


def _get_quality_agent() -> QualityAnalyst:
    global _quality_agent
    if _quality_agent is None:
        _quality_agent = QualityAnalyst(enriched_metadata=load_metadata())
    return _quality_agent


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/assess", response_model=QualityResponse)
async def assess(request: QualityRequest) -> QualityResponse:
    """Assess schema quality, optionally scoped to a specific table or domain.

    Orchestrates the full quality assessment:

    1. Ensure stores (pgvector, Neo4j) are initialized
    2. Load enriched metadata
    3. Run QualityAnalyst assessment
    4. Return 6-dimension quality scores, issues, and recommendations
    """
    try:
        await ensure_stores_initialized()
        metadata = load_metadata()
        quality_analyst = QualityAnalyst(enriched_metadata=metadata)
        result = quality_analyst.assess(
            table_name=request.table_name,
            domain=request.domain,
        )
        return QualityResponse(**result)

    except Exception as exc:
        logger.exception("Quality assessment endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for the quality service."""
    return {
        "status": "ok",
        "service": "quality",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "QualityRequest",
    "QualityResponse",
    "router",
]
