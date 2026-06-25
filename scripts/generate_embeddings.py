#!/usr/bin/env python3
"""Generate embeddings from enriched metadata and store in pgvector + Neo4j.

Usage:
    python -m scripts.generate_embeddings

Environment variables:
    METADATA_PATH   Path to enriched_metadata.json (default: etl_enrichment_pipline/output/enriched_metadata.json)
    EMBEDDING_MODEL Sentence-transformers model name (default: BAAI/bge-small-en-v1.5)
    PGVECTOR_DSN    PostgreSQL connection string for pgvector (default: postgresql://postgres:postgres@localhost:5432/schema_embeddings)
    NEO4J_URI       Neo4j URI (default: bolt://localhost:7687)
    NEO4J_USER      Neo4j username (default: neo4j)
    NEO4J_PASSWORD  Neo4j password (default: password)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from tqdm import tqdm

from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
from etl_enrichment_pipeline.core.vector_store import VectorStore
from etl_enrichment_pipeline.core.graph_store import GraphStore

DEFAULT_METADATA_PATH = "etl_enrichment_pipline/output/enriched_metadata.json"


def load_metadata(path: str) -> dict:
    filepath = Path(path)
    if not filepath.exists():
        print(f"Error: Metadata file not found: {filepath.resolve()}", file=sys.stderr)
        sys.exit(1)
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


async def main() -> None:
    metadata_path = os.getenv("METADATA_PATH", DEFAULT_METADATA_PATH)

    print(f"Loading metadata from {metadata_path}...")
    try:
        metadata = load_metadata(metadata_path)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: Failed to load metadata: {e}", file=sys.stderr)
        sys.exit(1)

    tables = metadata.get("tables", [])
    relationships = metadata.get("relationships", [])
    entity_relationships = metadata.get("entity_relationships", [])
    column_count = sum(len(t.get("columns", [])) for t in tables)
    print(f"  Loaded {len(tables)} tables, {column_count} columns, "
          f"{len(relationships)} FK relationships, {len(entity_relationships)} entity relationships")

    print("Initializing EmbeddingService...")
    try:
        embedding_service = EmbeddingService()
    except Exception as e:
        print(f"Error: Failed to initialize EmbeddingService: {e}", file=sys.stderr)
        sys.exit(1)

    print("Generating embeddings for schema objects...")
    try:
        with tqdm(total=1, desc="Embedding schema objects", unit="step") as pbar:
            embeddings = embedding_service.embed_schema_objects(metadata)
            pbar.update(1)
    except Exception as e:
        print(f"Error: Failed to generate embeddings: {e}", file=sys.stderr)
        sys.exit(1)

    table_embs = [e for e in embeddings if e.object_type == "table"]
    column_embs = [e for e in embeddings if e.object_type == "column"]
    relationship_embs = [e for e in embeddings if e.object_type == "relationship"]

    print(f"  Generated {len(table_embs)} table embeddings")
    print(f"  Generated {len(column_embs)} column embeddings")
    print(f"  Generated {len(relationship_embs)} relationship embeddings")

    print("Initializing VectorStore (pgvector)...")
    vector_store = VectorStore()
    try:
        await vector_store.initialize_schema()
        print("  Schema initialized")
    except Exception as e:
        print(f"Error: VectorStore schema initialization failed: {e}", file=sys.stderr)
        await vector_store.close()
        sys.exit(1)

    try:
        await vector_store.upsert_embeddings(embeddings)
        print(f"  Upserted {len(embeddings)} embeddings to pgvector")
    except Exception as e:
        print(f"Error: Failed to upsert embeddings to pgvector: {e}", file=sys.stderr)
        await vector_store.close()
        sys.exit(1)

    await vector_store.close()
    print("  VectorStore connection closed")

    print("Initializing GraphStore (Neo4j)...")
    graph_store = GraphStore()
    try:
        await graph_store.initialize_schema()
        print("  Schema constraints created")
    except Exception as e:
        print(f"Error: GraphStore schema initialization failed: {e}", file=sys.stderr)
        await graph_store.close()
        sys.exit(1)

    try:
        await graph_store.load_schema(metadata)
        print("  Schema loaded into Neo4j")
    except Exception as e:
        print(f"Error: Failed to load schema into Neo4j: {e}", file=sys.stderr)
        await graph_store.close()
        sys.exit(1)

    await graph_store.close()
    print("  GraphStore connection closed")

    print(f"\nEmbedded {len(table_embs)} tables, {len(column_embs)} columns, "
          f"{len(relationship_embs)} relationships")


if __name__ == "__main__":
    asyncio.run(main())
