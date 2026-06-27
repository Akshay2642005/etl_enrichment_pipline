"""Load enriched metadata into pgvector and Neo4j stores.

Uses the shared lazy singletons from :mod:`~etl_enrichment_pipeline.api.shared_state`
so the embedding model, pgvector connection, and Neo4j connection are only
initialised once across the entire application.

Run standalone::

    uv run python -m etl_enrichment_pipeline.core.store_loader
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from etl_enrichment_pipeline.api.shared_state import (
    close_stores,
    ensure_stores_initialized,
    get_embedding_service,
    get_graph_store,
    get_vector_store,
)

logger = logging.getLogger(__name__)

_DEFAULT_METADATA_PATH = (
    Path(__file__).resolve().parents[3] / "output" / "enriched_metadata.json"
)
_METADATA_PATH = os.getenv("METADATA_PATH", str(_DEFAULT_METADATA_PATH))


async def load_enriched_metadata(
    metadata_path: str | None = None,
) -> dict[str, Any]:
    """Load enriched metadata into pgvector (embeddings) and Neo4j (graph).

    Reads the enriched metadata JSON, generates embeddings for every schema
    object (tables, columns, relationships), upserts them into the pgvector
    store, and loads the schema structure into the Neo4j graph store.

    Uses the shared lazy singletons so the embedding model, vector-store
    connection pool, and graph-store driver are only initialised once.

    Args:
        metadata_path: Path to ``enriched_metadata.json``. Falls back to the
            ``METADATA_PATH`` env var, then to ``output/enriched_metadata.json``.

    Returns:
        The loaded metadata dictionary.

    Raises:
        FileNotFoundError: If the metadata file does not exist.
    """
    path = Path(metadata_path or _METADATA_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched metadata not found at {path}. "
            "Run the enrichment pipeline first (e.g. `uv run main.py --sql-file ...`)."
        )

    logger.info("Loading enriched metadata from %s", path)
    metadata = json.loads(path.read_text(encoding="utf-8"))

    tables_count = len(metadata.get("tables", []))
    rels_count = len(metadata.get("relationships", []))
    logger.info(
        "Metadata loaded: %d tables, %d relationships",
        tables_count,
        rels_count,
    )

    # --- 1. Generate embeddings (shared singleton — loads model once) ---
    logger.info("Generating embeddings for schema objects ...")
    embedding_service = get_embedding_service()
    embeddings = embedding_service.embed_schema_objects(metadata)
    logger.info("Generated %d embeddings", len(embeddings))

    # --- 2. Upsert into pgvector (shared connection pool) ---
    logger.info("Upserting embeddings into pgvector ...")
    await ensure_stores_initialized()
    vector_store = get_vector_store()
    if vector_store is not None:
        try:
            await vector_store.upsert_embeddings(embeddings)
            logger.info("pgvector store populated successfully")
        except Exception:
            logger.exception("Failed to upsert embeddings into pgvector")
    else:
        logger.warning("VectorStore unavailable — skipping pgvector upsert")

    # --- 3. Load into Neo4j (shared driver) ---
    logger.info("Loading schema into Neo4j ...")
    graph_store = get_graph_store()
    if graph_store is not None:
        try:
            await graph_store.load_schema(metadata)
            logger.info("Neo4j graph populated successfully")
        except Exception:
            logger.exception("Failed to load schema into Neo4j")
    else:
        logger.warning("GraphStore unavailable — skipping Neo4j load")

    logger.info("Store loading complete — ready for NL2SQL queries")
    return metadata


async def main() -> None:
    """CLI entry point: load enriched metadata into stores."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        await load_enriched_metadata()
    finally:
        await close_stores()


if __name__ == "__main__":
    asyncio.run(main())


__all__ = ["load_enriched_metadata"]
