"""Context builder that combines vector search + graph traversal for LLM prompts.

Provides ContextBuilder which orchestrates embedding, vector search, graph
traversal, and deduplication to produce a structured SchemaContext ready for
LLM prompt formatting — no LLM calls, no SQL generation.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
from etl_enrichment_pipeline.core.graph_store import GraphStore, JoinPath
from etl_enrichment_pipeline.core.vector_store import VectorStore


@dataclass
class SchemaContext:
    """Structured schema context assembled for LLM prompt construction.

    Attributes:
        tables: Table definitions with name, description, business_role, domain,
            and full column details.
        columns: Column metadata with table name, data_type, semantic_type,
            description, and key constraints.
        relationships: Foreign-key relationships discovered via vector search.
        join_paths: Join sequences (table→table) from graph traversal.
        entity_relationships: Entity-level business relationships relevant to
            the matched schema elements.
    """

    tables: list[dict[str, Any]] = field(default_factory=list)
    columns: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    join_paths: list[dict[str, Any]] = field(default_factory=list)
    entity_relationships: list[dict[str, Any]] = field(default_factory=list)


class ContextBuilder:
    """Combines vector search + graph traversal to build schema context.

    Usage::

        builder = ContextBuilder(enriched_metadata)
        context = await builder.build_context(
            "show me all employees in department 5",
            vector_store,
            graph_store,
        )
        prompt = builder.format_prompt(context)
    """

    def __init__(
        self,
        enriched_metadata: dict[str, Any] | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize the context builder.

        Args:
            enriched_metadata: The enriched_metadata.json dictionary. Used to
                enrich vector search results with full descriptions, semantic
                types, and column lists. If omitted, only metadata embedded in
                the vector store results will be available.
            embedding_service: Optional EmbeddingService. A default one is
                created when not provided.
        """
        self._metadata = enriched_metadata or {}
        self._embedding_service = embedding_service or EmbeddingService()

    @classmethod
    def from_json(
        cls,
        json_path: str = "",
        embedding_service: EmbeddingService | None = None,
    ) -> ContextBuilder:
        """Load enriched metadata from a JSON file and return a ContextBuilder.

        Args:
            json_path: Path to enriched_metadata.json. Falls back to the
                ENRICHED_METADATA_PATH environment variable, then to
                ``output/enriched_metadata.json`` relative to the project root.
            embedding_service: Optional EmbeddingService instance.
        """
        path = (
            json_path
            or os.getenv("ENRICHED_METADATA_PATH")
            or os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "output",
                "enriched_metadata.json",
            )
        )
        with open(path, encoding="utf-8") as fh:
            metadata = json.load(fh)
        return cls(enriched_metadata=metadata, embedding_service=embedding_service)

    async def build_context(
        self,
        question: str,
        vector_store: VectorStore | None = None,
        graph_store: GraphStore | None = None,
        top_k_tables: int = 10,
        top_k_columns: int = 20,
        top_k_relationships: int = 10,
        graph_hops: int = 2,
    ) -> SchemaContext:
        """Build a SchemaContext from a natural-language question.

        Steps:
        1. Embed the question via EmbeddingService.
        2. Vector-search for tables, columns, and relationships.
        3. Extract matched table names.
        4. Graph-traverse from matched tables to discover join paths.
        5. Deduplicate and enrich results from enriched_metadata.
        6. Assemble into a SchemaContext.

        Args:
            question: The user's natural-language question.
            vector_store: Populated pgvector store (``None`` = skip vector search).
            graph_store: Populated Neo4j graph store (``None`` = skip graph traversal).
            top_k_tables: Max tables to retrieve.
            top_k_columns: Max columns to retrieve.
            top_k_relationships: Max relationships to retrieve.
            graph_hops: Max BFS depth for join-path discovery.

        Returns:
            A SchemaContext with deduplicated, ranked, and enriched results.
        """
        # --- Step 1: Embed ---
        query_embedding = self._embedding_service.generate_embeddings([question])[0]

        # --- Step 2: Vector search (skip when store is unavailable) ---
        table_results: list[Any] = []
        column_results: list[Any] = []
        relationship_results: list[Any] = []
        if vector_store is not None:
            # Run all 3 searches in parallel — they're independent DB calls
            search_results = await asyncio.gather(
                vector_store.search_similar(
                    query_embedding, object_type="table", top_k=top_k_tables
                ),
                vector_store.search_similar(
                    query_embedding, object_type="column", top_k=top_k_columns
                ),
                vector_store.search_similar(
                    query_embedding, object_type="relationship",
                    top_k=top_k_relationships
                ),
            )
            table_results, column_results, relationship_results = search_results

        # --- Step 3: Extract matched table names ---
        matched_table_names: set[str] = set()
        for r in table_results:
            matched_table_names.add(r.metadata["table_name"])
        for r in column_results:
            matched_table_names.add(r.metadata["table_name"])

        # --- Step 4: Graph traversal (skip when store is unavailable or no matches) ---
        join_paths_raw: list[JoinPath] = []
        if graph_store is not None and matched_table_names:
            join_paths_raw = await graph_store.find_join_paths(
                list(matched_table_names), max_hops=graph_hops
            )

        # Build enriched-metadata lookups
        tables_by_name, columns_by_key, all_relationships, all_entity_relationships = (
            self._build_metadata_lookups()
        )

        # --- Step 5: Deduplicate & enrich ---

        # 5a. Tables — from vector results, then append graph-discovered tables
        seen_tables: set[str] = set()
        tables_out: list[dict[str, Any]] = []

        for r in table_results:
            tbl_name: str = r.metadata["table_name"]
            if tbl_name in seen_tables:
                continue
            seen_tables.add(tbl_name)
            full = tables_by_name.get(tbl_name, {})
            tables_out.append(self._enrich_table(full, r.metadata, r.similarity))

        for jp in join_paths_raw:
            for tbl_name in jp.tables:
                if tbl_name in seen_tables:
                    continue
                seen_tables.add(tbl_name)
                full = tables_by_name.get(tbl_name, {})
                tables_out.append(self._enrich_table(full, {}, 0.0))

        # 5b. Columns — from vector results, enriched with metadata
        seen_columns: set[str] = set()
        columns_out: list[dict[str, Any]] = []

        for r in column_results:
            tbl_name = r.metadata.get("table_name", "")
            col_name = r.metadata.get("column_name", "")
            col_key = f"{tbl_name}.{col_name}"
            if col_key in seen_columns:
                continue
            seen_columns.add(col_key)
            full = columns_by_key.get(col_key, {})
            columns_out.append(self._enrich_column(full, r.metadata, r.similarity))

        # 5c. Relationships — separate FK from entity relationships
        seen_fk: set[str] = set()
        seen_er: set[str] = set()
        relationships_out: list[dict[str, Any]] = []
        entity_relationships_out: list[dict[str, Any]] = []

        for r in relationship_results:
            meta = r.metadata
            rel_type = meta.get("relationship_type", "foreign_key")

            if rel_type == "foreign_key":
                fk_key = (
                    f"{meta.get('from_table', '')}.{meta.get('from_column', '')}"
                    f"->{meta.get('to_table', '')}.{meta.get('to_column', '')}"
                )
                if fk_key in seen_fk:
                    continue
                seen_fk.add(fk_key)
                # Vector-store metadata may use child/parent keys if it was
                # populated before the normalisation fix — handle both.
                meta_from_table = meta.get("from_table") or meta.get("child_table", "")
                meta_to_table = meta.get("to_table") or meta.get("parent_table", "")
                relationships_out.append({
                    "from_table": meta_from_table,
                    "from_column": meta.get("from_column") or meta.get("child_column", ""),
                    "to_table": meta_to_table,
                    "to_column": meta.get("to_column") or meta.get("parent_column", ""),
                    "relationship_type": "foreign_key",
                    "similarity": r.similarity,
                })
            else:
                er_key = f"{meta.get('entity', '')}->{meta.get('related_entities', '')}"
                if er_key in seen_er:
                    continue
                seen_er.add(er_key)
                entity_relationships_out.append({
                    "entity": meta["entity"],
                    "related_entities": meta["related_entities"],
                    "business_meaning": meta.get("business_meaning", ""),
                    "relationship_type": "entity_relationship",
                    "similarity": r.similarity,
                })

        # 5d. Include all FK relationships that involve matched tables
        for rel in all_relationships:
            fk_key = (
                f"{rel['from_table']}.{rel['from_column']}"
                f"->{rel['to_table']}.{rel['to_column']}"
            )
            if fk_key in seen_fk:
                continue
            if rel["from_table"] in seen_tables or rel["to_table"] in seen_tables:
                seen_fk.add(fk_key)
                relationships_out.append({
                    "from_table": rel["from_table"],
                    "from_column": rel["from_column"],
                    "to_table": rel["to_table"],
                    "to_column": rel["to_column"],
                    "relationship_type": "foreign_key",
                    "similarity": 0.0,
                })

        # 5e. Include entity relationships that involve matched entities
        matched_entity_names: set[str] = {
            _table_to_entity_name(tn) for tn in seen_tables
        }
        # Also add exact entity names discovered via vector search
        for er in all_entity_relationships:
            er_key = f"{er['entity']}->{er['related_entities']}"
            if er_key in seen_er:
                continue
            if (
                er["entity"] in matched_entity_names
                or er["related_entities"] in matched_entity_names
            ):
                seen_er.add(er_key)
                entity_relationships_out.append({
                    "entity": er["entity"],
                    "related_entities": er["related_entities"],
                    "business_meaning": er.get("business_meaning", ""),
                    "relationship_type": "entity_relationship",
                    "similarity": 0.0,
                })

        # 5f. Build join_paths from graph results
        join_paths_out: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for jp in join_paths_raw:
            path_key = "->".join(jp.tables)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)
            path_details = [
                {
                    "from_table": step[0],
                    "from_column": step[1],
                    "to_table": step[2],
                    "to_column": step[3],
                }
                for step in jp.path
            ]
            join_paths_out.append({
                "tables": jp.tables,
                "path": path_details,
                "hops": jp.hops,
            })

        # --- Step 6: Assemble ---
        return SchemaContext(
            tables=tables_out,
            columns=columns_out,
            relationships=relationships_out,
            join_paths=join_paths_out,
            entity_relationships=entity_relationships_out,
        )

    def format_prompt(self, context: SchemaContext) -> str:
        """Format a SchemaContext into an LLM-ready prompt string.

        Produces a structured text block with:
        - Table definitions (columns, types, semantic types, descriptions)
        - Foreign-key relationships
        - Join paths
        - Entity-level relationships
        """
        sections: list[str] = []

        # --- Tables ---
        if context.tables:
            table_lines: list[str] = ["### Tables\n"]
            for tbl in context.tables:
                table_lines.append(f"Table: {tbl['table_name']}")
                table_lines.append(f"  Description: {tbl.get('description', '')}")
                table_lines.append(f"  Business Role: {tbl.get('business_role', '')}")
                table_lines.append(f"  Domain: {tbl.get('domain', '')}")
                table_lines.append("  Columns:")
                for col in tbl.get("columns", []):
                    col_name = col.get("column_name", "")
                    data_type = col.get("data_type", "")
                    sem_type = col.get("semantic_type", "")
                    col_desc = col.get("description", "")
                    pk = "PK" if col.get("is_primary_key") else ""
                    nullable = "" if col.get("is_nullable", True) else "NOT NULL"
                    flags = " ".join(filter(None, [pk, nullable]))
                    table_lines.append(
                        f"    - {col_name} ({data_type})[{sem_type}]"
                        f"{': ' + col_desc if col_desc else ''}"
                        f"{'  ' + flags if flags else ''}"
                    )
                table_lines.append("")
            sections.append("\n".join(table_lines))

        # --- Columns (additional context beyond what's in table defs) ---
        if context.columns:
            col_lines: list[str] = ["### Relevant Columns\n"]
            for col in context.columns:
                col_lines.append(
                    f"  {col['table_name']}.{col.get('column_name', '')}"
                    f"  ({col.get('data_type', '')})"
                    f"  [{col.get('semantic_type', '')}]"
                    f"  {col.get('description', '')}"
                )
            col_lines.append("")
            sections.append("\n".join(col_lines))

        # --- Foreign Key Relationships ---
        if context.relationships:
            fk_lines: list[str] = ["### Foreign Key Relationships\n"]
            for rel in context.relationships:
                fk_lines.append(
                    f"  {rel['from_table']}.{rel['from_column']}"
                    f"  →  {rel['to_table']}.{rel['to_column']}"
                )
            fk_lines.append("")
            sections.append("\n".join(fk_lines))

        # --- Join Paths ---
        if context.join_paths:
            jp_lines: list[str] = ["### Join Paths\n"]
            for path in context.join_paths:
                path_str = " → ".join(path.get("tables", []))
                jp_lines.append(f"  {path_str}  ({path.get('hops', 0)} hop(s))")
                for step in path.get("path", []):
                    jp_lines.append(
                        f"    {step['from_table']}.{step['from_column']}"
                        f"  →  {step['to_table']}.{step['to_column']}"
                    )
                jp_lines.append("")
            sections.append("\n".join(jp_lines))

        # --- Entity Relationships ---
        if context.entity_relationships:
            er_lines: list[str] = ["### Entity Relationships\n"]
            for er in context.entity_relationships:
                meaning = er.get("business_meaning", "")
                extra = f"  :  {meaning}" if meaning else ""
                er_lines.append(
                    f"  {er['entity']}  →  {er['related_entities']}{extra}"
                )
            er_lines.append("")
            sections.append("\n".join(er_lines))

        return "\n".join(sections).strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_metadata_lookups(
        self,
    ) -> tuple[
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """Build lookup dictionaries from enriched_metadata."""
        tables_by_name: dict[str, dict[str, Any]] = {}
        columns_by_key: dict[str, dict[str, Any]] = {}
        all_relationships: list[dict[str, Any]] = []
        all_entity_relationships: list[dict[str, Any]] = []

        for tbl in self._metadata.get("tables", []):
            name = tbl["table_name"]
            tables_by_name[name] = tbl
            for col in tbl.get("columns", []):
                col_key = f"{name}.{col['column_name']}"
                columns_by_key[col_key] = col

        for raw_rel in self._metadata.get("relationships", []):
            # Normalise child/parent → from/to keys so downstream code
            # can safely use ``rel["from_table"]`` etc. regardless of how
            # the metadata JSON was serialised.
            if "from_table" in raw_rel:
                rel = raw_rel
            else:
                rel = {
                    "from_table": raw_rel.get("child_table", ""),
                    "from_column": raw_rel.get("child_column", ""),
                    "to_table": raw_rel.get("parent_table", ""),
                    "to_column": raw_rel.get("parent_column", ""),
                }
                # Preserve any extra keys (name, description, …)
                rel.update(
                    (k, v) for k, v in raw_rel.items()
                    if k not in ("child_table", "child_column", "parent_table", "parent_column")
                )
            all_relationships.append(rel)

        for er in self._metadata.get("entity_relationships", []):
            all_entity_relationships.append(er)

        return (
            tables_by_name,
            columns_by_key,
            all_relationships,
            all_entity_relationships,
        )

    @staticmethod
    def _enrich_table(
        full: dict[str, Any],
        metadata: dict[str, Any],
        similarity: float,
    ) -> dict[str, Any]:
        """Enrich a table result with full metadata."""
        return {
            "table_name": full.get("table_name", metadata.get("table_name", "")),
            "description": full.get("description", metadata.get("description", "")),
            "business_role": full.get(
                "business_role", metadata.get("business_role", "")
            ),
            "domain": full.get("domain", metadata.get("domain", "")),
            "columns": full.get("columns", []),
            "similarity": similarity,
        }

    @staticmethod
    def _enrich_column(
        full: dict[str, Any],
        metadata: dict[str, Any],
        similarity: float,
    ) -> dict[str, Any]:
        """Enrich a column result with full metadata."""
        tbl = metadata.get("table_name", "")
        col = metadata.get("column_name", "")
        return {
            "table_name": full.get("table_name", tbl),
            "column_name": full.get("column_name", col),
            "data_type": full.get(
                "data_type", metadata.get("data_type", "")
            ),
            "semantic_type": full.get(
                "semantic_type", metadata.get("semantic_type", "")
            ),
            "description": full.get(
                "description", metadata.get("description", "")
            ),
            "is_primary_key": full.get(
                "is_primary_key", metadata.get("is_primary_key", False)
            ),
            "is_nullable": full.get(
                "is_nullable", metadata.get("is_nullable", True)
            ),
            "similarity": similarity,
        }


def _table_to_entity_name(table_name: str) -> str:
    """Convert a snake_case table name to a likely PascalCase entity name.

    Examples::

        >>> _table_to_entity_name("employee")
        'Employee'
        >>> _table_to_entity_name("departmentsss")
        'Departmentsss'
    """
    return table_name.title()


__all__ = ["ContextBuilder", "SchemaContext"]
