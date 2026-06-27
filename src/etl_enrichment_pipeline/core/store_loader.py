"""Load enriched metadata into pgvector and Neo4j stores.

Run standalone::

    uv run python -m etl_enrichment_pipeline.core.store_loader

Or call :func:`load_enriched_metadata` programmatically after a pipeline run.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
from etl_enrichment_pipeline.core.graph_store import GraphStore
from etl_enrichment_pipeline.core.vector_store import VectorStore

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

    # --- 1. Generate embeddings ---
    logger.info("Generating embeddings for schema objects ...")
    loop = asyncio.get_running_loop()
    # Initialise the service (loads weights) in a thread so it doesn't block the event loop
    embedding_service = await loop.run_in_executor(None, EmbeddingService)
    # Generate embeddings for the entire schema in a thread
    embeddings = await loop.run_in_executor(
        None, embedding_service.embed_schema_objects, metadata
    )
    logger.info("Generated %d embeddings", len(embeddings))

    # --- 2. Upsert into pgvector ---
    logger.info("Upserting embeddings into pgvector ...")
    vector_store = VectorStore()
    try:
        await vector_store.initialize_schema()
        await vector_store.upsert_embeddings(embeddings)
        logger.info("pgvector store populated successfully")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pgvector store unavailable (%s: %s) — NL2SQL vector search will be skipped.",
            type(exc).__name__,
            exc,
        )
    finally:
        await vector_store.close()

    # --- 3. Load into Neo4j ---
    logger.info("Loading schema into Neo4j ...")
    graph_store = GraphStore()
    try:
        await graph_store.initialize_schema()
        await graph_store.load_schema(metadata)
        logger.info("Neo4j graph populated successfully")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Neo4j graph store unavailable (%s: %s) — graph-based queries will be skipped.",
            type(exc).__name__,
            exc,
        )
    finally:
        await graph_store.close()

    logger.info("Store loading complete — ready for NL2SQL queries")
    return metadata


async def main() -> None:
    """CLI entry point: load enriched metadata into stores."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    await load_enriched_metadata()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())


__all__ = ["load_enriched_metadata"]
