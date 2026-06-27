"""Shared lazy singletons for API services — metadata, embedding, vector store, graph store.

Consolidates the duplicated store/metadata/embedding singletons that were previously
defined independently in ``nl2sql_service.py``, ``quality_service.py``, and
``insights_service.py``.  Each service now imports from this module instead of
maintaining its own private globals.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
from etl_enrichment_pipeline.core.graph_store import GraphStore
from etl_enrichment_pipeline.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default metadata path
# ---------------------------------------------------------------------------

_DEFAULT_METADATA_PATH = (
    Path(__file__).resolve().parents[3] / "output" / "enriched_metadata.json"
)

METADATA_PATH = str(_DEFAULT_METADATA_PATH)

# ---------------------------------------------------------------------------
# Lazy singleton state
# ---------------------------------------------------------------------------

_embedding_service: EmbeddingService | None = None
_vector_store: VectorStore | None = None
_graph_store: GraphStore | None = None
_store_initialized: bool = False


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def load_metadata(path_override: str | None = None) -> dict[str, Any]:
    """Read enriched metadata from disk.

    Always reads from disk — never returns a stale cached copy.

    Args:
        path_override: Optional explicit path.  Falls back to ``METADATA_PATH``
            (env var ``METADATA_PATH`` or ``output/enriched_metadata.json``).

    Returns:
        The parsed metadata dictionary, or ``{}`` if the file does not exist.
    """
    import os

    path = Path(path_override or os.getenv("METADATA_PATH", METADATA_PATH))
    if not path.exists():
        logger.warning("Metadata file not found at %s — using empty metadata", path)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_embedding_service() -> EmbeddingService:
    """Lazy-initialised ``EmbeddingService`` singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_vector_store() -> VectorStore:
    """Lazy-initialised ``VectorStore`` singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def get_graph_store() -> GraphStore:
    """Lazy-initialised ``GraphStore`` singleton."""
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore()
    return _graph_store


async def ensure_stores_initialized() -> None:
    """Initialise vector-store and graph-store schemas (idempotent).

    Each store is initialised independently so that a failure in one does not
    block the other.  On failure the store reference is set to ``None`` so
    callers can check availability.
    """
    global _store_initialized
    if _store_initialized:
        return

    vs = get_vector_store()
    try:
        await vs.initialize_schema()
    except Exception as exc:
        logger.warning("Failed to initialise VectorStore (pgvector): %s", exc)
        global _vector_store  # noqa: PLW0603
        _vector_store = None

    gs = get_graph_store()
    try:
        await gs.initialize_schema()
    except Exception as exc:
        logger.warning("Failed to initialise GraphStore (Neo4j): %s", exc)
        global _graph_store  # noqa: PLW0603
        _graph_store = None

    _store_initialized = True


async def close_stores() -> None:
    """Close vector-store and graph-store connections and reset state."""
    global _store_initialized, _vector_store, _graph_store

    if _vector_store is not None:
        try:
            await _vector_store.close()
        except Exception as exc:
            logger.warning("Error closing VectorStore: %s", exc)
        _vector_store = None

    if _graph_store is not None:
        try:
            await _graph_store.close()
        except Exception as exc:
            logger.warning("Error closing GraphStore: %s", exc)
        _graph_store = None

    _store_initialized = False


__all__ = [
    "METADATA_PATH",
    "close_stores",
    "ensure_stores_initialized",
    "get_embedding_service",
    "get_graph_store",
    "get_vector_store",
    "load_metadata",
]
