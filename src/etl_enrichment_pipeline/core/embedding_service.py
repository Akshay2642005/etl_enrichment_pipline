"""Embedding service for NL-to-SQL schema retrieval.

Generates embeddings from enriched schema metadata using sentence-transformers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from sentence_transformers import SentenceTransformer


@dataclass(frozen=True)
class SchemaEmbedding:
    """Embedding record for a schema object (table, column, or relationship)."""

    object_type: str  # "table" | "column" | "relationship"
    object_name: str  # e.g., "employee", "employee.employee_name"
    object_key: str   # unique key for upsert: "table:employee", "column:employee.employee_name"
    text_content: str  # the text that was embedded
    embedding: list[float]  # 384-dim vector
    metadata: dict[str, Any]  # additional context for retrieval


class EmbeddingService:
    """Service for generating embeddings from text using sentence-transformers.

    Uses BAAI/bge-small-en-v1.5 (384-dim) by default, configurable via
    EMBEDDING_MODEL environment variable.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize the embedding service.

        Args:
            model_name: Sentence-transformers model name. Defaults to
                EMBEDDING_MODEL env var or "BAAI/bge-small-en-v1.5".
        """
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
        )
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors (each 384-dim for bge-small-en-v1.5).
            Returns empty list if input is empty.
        """
        if not texts:
            return []

        embeddings = self.model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist()

    def embed_schema_objects(self, enriched_metadata: dict) -> list[SchemaEmbedding]:
        """Generate embeddings for all schema objects in enriched metadata.

        Creates embeddings for:
        - Tables: table name + description + column summaries
        - Columns: table.column + description + data_type + semantic_type
        - Relationships: from_table.from_col -> to_table.to_col + business meaning

        Args:
            enriched_metadata: The enriched_metadata.json dict.

        Returns:
            List of SchemaEmbedding records for all objects.
        """
        embeddings: list[SchemaEmbedding] = []

        tables = enriched_metadata.get("tables", [])
        relationships = enriched_metadata.get("relationships", [])
        entity_relationships = enriched_metadata.get("entity_relationships", [])

        # --- Embed tables ---
        table_texts: list[str] = []
        table_keys: list[str] = []
        table_names: list[str] = []
        table_metadatas: list[dict[str, Any]] = []

        for table in tables:
            table_name = table["table_name"]
            description = table.get("description", "")
            business_role = table.get("business_role", "")
            domain = table.get("domain", "")

            # Build column summary
            col_summaries = []
            for col in table.get("columns", []):
                col_name = col["column_name"]
                data_type = col["data_type"]
                semantic_type = col.get("semantic_type", "")
                col_desc = col.get("description", "")
                col_summaries.append(
                    f"{col_name} ({data_type})[{semantic_type}]: {col_desc}"
                )

            text = (
                f"Table: {table_name}\n"
                f"Description: {description}\n"
                f"Business Role: {business_role}\n"
                f"Domain: {domain}\n"
                f"Columns:\n" + "\n".join(f"  - {cs}" for cs in col_summaries)
            )

            table_texts.append(text)
            table_keys.append(f"table:{table_name}")
            table_names.append(table_name)
            table_metadatas.append(
                {
                    "table_name": table_name,
                    "description": description,
                    "business_role": business_role,
                    "domain": domain,
                    "column_count": len(table.get("columns", [])),
                }
            )

        if table_texts:
            table_embeddings = self.generate_embeddings(table_texts)
            for i, emb in enumerate(table_embeddings):
                embeddings.append(
                    SchemaEmbedding(
                        object_type="table",
                        object_name=table_names[i],
                        object_key=table_keys[i],
                        text_content=table_texts[i],
                        embedding=emb,
                        metadata=table_metadatas[i],
                    )
                )

        # --- Embed columns ---
        column_texts: list[str] = []
        column_keys: list[str] = []
        column_names: list[str] = []
        column_metadatas: list[dict[str, Any]] = []

        for table in tables:
            table_name = table["table_name"]
            for col in table.get("columns", []):
                col_name = col["column_name"]
                data_type = col["data_type"]
                semantic_type = col.get("semantic_type", "")
                description = col.get("description", "")
                is_pk = col.get("is_primary_key", False)
                is_nullable = col.get("is_nullable", True)

                text = (
                    f"Column: {table_name}.{col_name}\n"
                    f"Data Type: {data_type}\n"
                    f"Semantic Type: {semantic_type}\n"
                    f"Description: {description}\n"
                    f"Primary Key: {is_pk}\n"
                    f"Nullable: {is_nullable}"
                )

                column_texts.append(text)
                column_keys.append(f"column:{table_name}.{col_name}")
                column_names.append(f"{table_name}.{col_name}")
                column_metadatas.append(
                    {
                        "table_name": table_name,
                        "column_name": col_name,
                        "data_type": data_type,
                        "semantic_type": semantic_type,
                        "description": description,
                        "is_primary_key": is_pk,
                        "is_nullable": is_nullable,
                    }
                )

        if column_texts:
            column_embeddings = self.generate_embeddings(column_texts)
            for i, emb in enumerate(column_embeddings):
                embeddings.append(
                    SchemaEmbedding(
                        object_type="column",
                        object_name=column_names[i],
                        object_key=column_keys[i],
                        text_content=column_texts[i],
                        embedding=emb,
                        metadata=column_metadatas[i],
                    )
                )

        # --- Embed relationships (FK) ---
        rel_texts: list[str] = []
        rel_keys: list[str] = []
        rel_names: list[str] = []
        rel_metadatas: list[dict[str, Any]] = []

        for rel in relationships:
            # The metadata may use child_table/child_column/parent_table/parent_column
            # (canonical JSON) or from_table/from_column/to_table/to_column (raw schema).
            # Support both naming conventions.
            from_table = rel.get("from_table") or rel["child_table"]
            from_col = rel.get("from_column") or rel["child_column"]
            to_table = rel.get("to_table") or rel["parent_table"]
            to_col = rel.get("to_column") or rel["parent_column"]

            text = (
                f"Foreign Key: {from_table}.{from_col} -> {to_table}.{to_col}\n"
                f"Relationship Type: foreign_key"
            )

            rel_texts.append(text)
            rel_keys.append(f"relationship:{from_table}.{from_col}->{to_table}.{to_col}")
            rel_names.append(f"{from_table}.{from_col}->{to_table}.{to_col}")
            rel_metadatas.append(
                {
                    "from_table": from_table,
                    "from_column": from_col,
                    "to_table": to_table,
                    "to_column": to_col,
                    "relationship_type": "foreign_key",
                }
            )

        # --- Embed entity relationships ---
        for er in entity_relationships:
            entity = er.get("entity", "")
            related = er.get("related_entities", "")
            business_meaning = er.get("business_meaning", "")

            text = (
                f"Entity Relationship: {entity} -> {related}\n"
                f"Business Meaning: {business_meaning}\n"
                f"Relationship Type: entity_relationship"
            )

            rel_texts.append(text)
            rel_keys.append(f"entity_relationship:{entity}->{related}")
            rel_names.append(f"{entity}->{related}")
            rel_metadatas.append(
                {
                    "entity": entity,
                    "related_entities": related,
                    "business_meaning": business_meaning,
                    "relationship_type": "entity_relationship",
                }
            )

        if rel_texts:
            rel_embeddings = self.generate_embeddings(rel_texts)
            for i, emb in enumerate(rel_embeddings):
                embeddings.append(
                    SchemaEmbedding(
                        object_type="relationship",
                        object_name=rel_names[i],
                        object_key=rel_keys[i],
                        text_content=rel_texts[i],
                        embedding=emb,
                        metadata=rel_metadatas[i],
                    )
                )

        return embeddings


__all__ = ["EmbeddingService", "SchemaEmbedding"]