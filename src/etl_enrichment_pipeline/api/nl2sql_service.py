"""NL2SQL API router — natural-language to PostgreSQL SQL endpoint.

Task 7 of the nl2sql-service plan.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl_enrichment_pipeline.agents.nl2sql_generator import NL2SQLGenerator
from etl_enrichment_pipeline.core.context_builder import ContextBuilder
from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
from etl_enrichment_pipeline.core.graph_store import GraphStore
from etl_enrichment_pipeline.core.sql_validator import SQLValidator
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


class NL2SQLRequest(BaseModel):
    question: str = Field(..., description="Natural-language question to convert to SQL")
    context_limit: int = Field(default=10, ge=1, le=500, description="Max schema context items to retrieve (1–500)")
    include_explanation: bool = Field(default=False, description="Whether to include explanation in response")


class NL2SQLResponse(BaseModel):
    sql: str = Field(default="", description="Generated PostgreSQL SQL")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score (0.0–1.0)")
    context_used: list[dict[str, Any]] = Field(default_factory=list, description="Schema context items used for generation")
    explanation: str | None = Field(default=None, description="Optional explanation of the generated SQL")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/nl2sql", tags=["nl2sql"])

# ---------------------------------------------------------------------------
# Lazy singleton state
# ---------------------------------------------------------------------------

_metadata: dict[str, Any] | None = None
_embedding_service: EmbeddingService | None = None
_vector_store: VectorStore | None = None
_graph_store: GraphStore | None = None
_context_builder: ContextBuilder | None = None
_nl2sql_generator: NL2SQLGenerator | None = None
_sql_validator: SQLValidator | None = None
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


def _get_context_builder() -> ContextBuilder:
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder(
            enriched_metadata=_load_metadata(),
            embedding_service=_get_embedding_service(),
        )
    return _context_builder


def _get_nl2sql_generator() -> NL2SQLGenerator:
    global _nl2sql_generator
    if _nl2sql_generator is None:
        _nl2sql_generator = NL2SQLGenerator()
    return _nl2sql_generator


def _get_sql_validator() -> SQLValidator:
    global _sql_validator
    if _sql_validator is None:
        _sql_validator = SQLValidator(metadata=_load_metadata())
    return _sql_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_context_summary(context_used_schema: Any) -> list[dict[str, Any]]:
    """Flatten a ``SchemaContext`` into a list of dicts for the response."""
    summary: list[dict[str, Any]] = []
    for tbl in getattr(context_used_schema, "tables", []):
        summary.append({
            "type": "table",
            "name": tbl.get("table_name", ""),
            "similarity": tbl.get("similarity", 0.0),
        })
    for col in getattr(context_used_schema, "columns", []):
        summary.append({
            "type": "column",
            "table": col.get("table_name", ""),
            "name": col.get("column_name", ""),
            "similarity": col.get("similarity", 0.0),
        })
    for rel in getattr(context_used_schema, "relationships", []):
        summary.append({
            "type": "relationship",
            "from": f"{rel.get('from_table', '')}.{rel.get('from_column', '')}",
            "to": f"{rel.get('to_table', '')}.{rel.get('to_column', '')}",
            "similarity": rel.get("similarity", 0.0),
        })
    for jp in getattr(context_used_schema, "join_paths", []):
        summary.append({
            "type": "join_path",
            "tables": jp.get("tables", []),
            "hops": jp.get("hops", 0),
        })
    for er in getattr(context_used_schema, "entity_relationships", []):
        summary.append({
            "type": "entity_relationship",
            "entity": er.get("entity", ""),
            "related_entities": er.get("related_entities", ""),
            "business_meaning": er.get("business_meaning", ""),
        })
    return summary


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=NL2SQLResponse)
async def nl2sql(request: NL2SQLRequest) -> NL2SQLResponse:
    """Convert a natural-language question to PostgreSQL SQL.

    Orchestrates the full NL2SQL pipeline:

    1. Build schema context via vector search + graph traversal
    2. Generate SQL via LLM
    3. Validate generated SQL against enriched metadata
    """
    try:
        await _ensure_stores_initialized()

        context = await _get_context_builder().build_context(
            question=request.question,
            vector_store=_get_vector_store(),
            graph_store=_get_graph_store(),
            top_k_tables=request.context_limit,
            top_k_columns=request.context_limit * 2,
            top_k_relationships=request.context_limit,
        )

        generation = _get_nl2sql_generator().generate(request.question, context)

        sql = generation.sql.strip()
        if sql:
            validation = _get_sql_validator().validate(sql)
            confidence = min(generation.confidence, validation.confidence)
        else:
            confidence = 0.0

        return NL2SQLResponse(
            sql=sql,
            confidence=confidence,
            context_used=_build_context_summary(context),
            explanation=generation.explanation if request.include_explanation else None,
        )

    except Exception as exc:
        logger.exception("NL2SQL endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for the NL2SQL service."""
    return {
        "status": "ok",
        "service": "nl2sql",
        "version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# Lifespan utility (for use in ``main.py`` app lifespan)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def nl2sql_lifespan(_app: Any) -> AsyncGenerator[None, None]:
    """Lifespan context manager for NL2SQL service lifecycle.

    Usage in the FastAPI app (``main.py``)::

        from contextlib import asynccontextmanager
        from fastapi import FastAPI
        from etl_enrichment_pipeline.api.nl2sql_service import nl2sql_lifespan

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with nl2sql_lifespan(app):
                yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(nl2sql_router)
    """
    try:
        _load_metadata()
        _get_embedding_service()
        await _ensure_stores_initialized()
        _get_context_builder()
        _get_nl2sql_generator()
        _get_sql_validator()
        logger.info("NL2SQL services initialized")
        yield
    finally:
        vs = _get_vector_store()
        await vs.close()
        gs = _get_graph_store()
        await gs.close()
        logger.info("NL2SQL services shut down")


__all__ = [
    "NL2SQLRequest",
    "NL2SQLResponse",
    "nl2sql_lifespan",
    "router",
]
