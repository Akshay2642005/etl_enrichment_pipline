"""Quality assessment API router — evaluates schema quality across 6 dimensions.

See ``agents/quality_agent.py`` for the underlying assessment logic.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.quality_agent import QualityAnalyst
from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
from etl_enrichment_pipeline.core.graph_store import GraphStore
from etl_enrichment_pipeline.core.store_loader import (
    load_enriched_metadata,  # noqa: F401
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
# Lazy singleton state
# ---------------------------------------------------------------------------

_metadata: dict[str, Any] | None = None
_embedding_service: EmbeddingService | None = None
_vector_store: VectorStore | None = None
_graph_store: GraphStore | None = None
_quality_agent: QualityAnalyst | None = None
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


def _get_quality_agent() -> QualityAnalyst:
    global _quality_agent
    if _quality_agent is None:
        _quality_agent = QualityAnalyst(enriched_metadata=_load_metadata())
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
        await _ensure_stores_initialized()
        metadata = _load_metadata()
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
