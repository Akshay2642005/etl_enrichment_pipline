"""LangGraph pipeline orchestrator — JSON adapter, pipeline builder, and runner."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from etl_enrichment_pipeline.agents import (
    business_role_node,
    description_node,
    domain_node,
    entity_discovery_node,
    pattern_detection_node,
    relationship_intelligence_node,
    sample_query_node,
    semantic_type_node,
    use_case_node,
    validation_node,
)
from etl_enrichment_pipeline.models.canonical import (
    CanonicalSchema,
    ColumnSchema,
    DatabaseInfo,
    RelationshipSchema,
    TableSchema,
)
from etl_enrichment_pipeline.models.final_output import FinalOutput
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# A. JSON Adapter —  load_raw_metadata
# ---------------------------------------------------------------------------


def load_raw_metadata_from_dict(raw: dict) -> CanonicalSchema:
    """Convert a raw metadata dictionary to a ``CanonicalSchema``.

    The expected JSON format is::

        {
            "database_type": "postgresql",
            "schema": "public",
            "tables": [
                {
                    "table_name": "attendance",
                    "columns": [...],
                    "constraints": [...],
                    "relationships": [...]
                }
            ]
        }
    """
    db_info = DatabaseInfo(
        name=raw.get("schema"),
        vendor=raw.get("database_type"),
    )

    tables: list[TableSchema] = []
    relationships: list[RelationshipSchema] = []

    for tbl in raw.get("tables", []):
        table_name: str = tbl["table_name"]

        # --- columns ---
        columns: list[ColumnSchema] = []
        for col in tbl.get("columns", []):
            col_name: str = col["column_name"]
            data_type: str = col["data_type"]
            nullable_raw = col.get("nullable", True)
            # nullable: false → is_nullable = False
            is_nullable = nullable_raw if isinstance(nullable_raw, bool) else True

            columns.append(
                ColumnSchema(
                    table_name=table_name,
                    column_name=col_name,
                    data_type=data_type,
                    is_nullable=is_nullable,
                )
            )

        # --- constraints: mark primary keys ---
        pk_columns: set[str] = set()
        for constraint in tbl.get("constraints", []):
            if constraint.get("constraint_type", "").upper() == "PRIMARY KEY":
                pk_columns.add(constraint["column_name"])

        for col in columns:
            if col.column_name in pk_columns:
                col.is_primary_key = True

        tables.append(
            TableSchema(
                table_name=table_name,
                columns=columns,
            )
        )

        # --- relationships ---
        for rel in tbl.get("relationships", []):
            relationships.append(
                RelationshipSchema(
                    from_table=table_name,
                    from_column=rel["child_column"],
                    to_table=rel["parent_table"],
                    to_column=rel["parent_column"],
                )
            )

    return CanonicalSchema(
        database_info=db_info,
        tables=tables,
        relationships=relationships,
    )


def load_raw_metadata(filepath: str) -> CanonicalSchema:
    """Read a ``raw_metadata.json`` file and convert it to a ``CanonicalSchema``."""
    raw = json.loads(Path(filepath).read_text(encoding="utf-8"))
    return load_raw_metadata_from_dict(raw)


# ---------------------------------------------------------------------------
# B. Pipeline builder
# ---------------------------------------------------------------------------

# ── Logging wrapper ────────────────────────────────────────────────────────
# Each agent node is wrapped so the user sees real-time progress.


def _logged_node(name: str, node_func: Any) -> Any:
    """Wrap a pipeline node with start/completion/failure logging."""

    def wrapper(state: PipelineState) -> PipelineState:
        logger.info("[%s] ▶  started", name)
        t0 = time.time()
        try:
            result = node_func(state)
            elapsed = time.time() - t0
            logger.info("[%s] ✓  completed (%.1fs)", name, elapsed)
            return result
        except Exception:
            elapsed = time.time() - t0
            logger.exception("[%s] ✗  failed after %.1fs", name, elapsed)
            raise

    return wrapper


# ── Node function wrappers that accept a state and return a state ──────────
# Each agent's node function already conforms to the signature:
#     node(state: PipelineState) -> PipelineState
# We import them as-is from etl_enrichment_pipeline.agents.


def _load_json_node(state: PipelineState) -> PipelineState:
    """Load the raw metadata JSON file pointed to by ``state.raw_input``.

    This node should be the **first** node in the graph.  It expects
    ``state.raw_input`` to contain a file path string (set before invocation).
    If no path is set, the state is returned unchanged.
    """
    if state.raw_input:
        schema = load_raw_metadata(state.raw_input)
        state.canonical_schema = schema
    return state


def build_pipeline() -> CompiledStateGraph:
    """Build the compiled LangGraph ``StateGraph`` for the enrichment pipeline.

    Pipeline flow (11 agent nodes + 1 adapter node)::

        load_json → description → business_role → domain → semantic_type
        → entity_discovery → relationship_intelligence → use_case
        → sample_query → pattern_detection → validation → END

    Returns
    -------
    StateGraph
        A compiled ``StateGraph`` whose ``.invoke()`` accepts a
        ``PipelineState`` and returns an updated ``PipelineState``.
    """
    workflow = StateGraph(PipelineState)

    # Register all nodes (wrapped with logging)
    workflow.add_node("load_json", _logged_node("load_json", _load_json_node))
    workflow.add_node("description", _logged_node("description", description_node))
    workflow.add_node(
        "business_role", _logged_node("business_role", business_role_node),
    )
    workflow.add_node("domain", _logged_node("domain", domain_node))
    workflow.add_node(
        "semantic_type", _logged_node("semantic_type", semantic_type_node),
    )
    workflow.add_node(
        "entity_discovery",
        _logged_node("entity_discovery", entity_discovery_node),
    )
    workflow.add_node(
        "relationship_intelligence",
        _logged_node("relationship_intelligence", relationship_intelligence_node),
    )
    workflow.add_node("use_case", _logged_node("use_case", use_case_node))
    workflow.add_node("sample_query", _logged_node("sample_query", sample_query_node))
    workflow.add_node(
        "pattern_detection",
        _logged_node("pattern_detection", pattern_detection_node),
    )
    workflow.add_node("validation", _logged_node("validation", validation_node))

    # Wire edges — linear chain
    workflow.set_entry_point("load_json")
    workflow.add_edge("load_json", "description")
    workflow.add_edge("description", "business_role")
    workflow.add_edge("business_role", "domain")
    workflow.add_edge("domain", "semantic_type")
    workflow.add_edge("semantic_type", "entity_discovery")
    workflow.add_edge("entity_discovery", "relationship_intelligence")
    workflow.add_edge("relationship_intelligence", "use_case")
    workflow.add_edge("use_case", "sample_query")
    workflow.add_edge("sample_query", "pattern_detection")
    workflow.add_edge("pattern_detection", "validation")
    workflow.add_edge("validation", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# C. Final output assembler
# ---------------------------------------------------------------------------


def assemble_final_output(state: PipelineState) -> dict[str, Any]:
    """Build a ``FinalOutput``-compatible dict from a completed ``PipelineState``.

    This helper constructs every section of the master plan's final output
    structure.  Fields that have no corresponding data in the state are
    left as their default (empty) values.
    """
    schema = state.canonical_schema

    # --- metadata -----------------------------------------------------------
    metadata: dict[str, Any] = {
        "source": "raw_metadata.json",
    }
    if schema:
        metadata["database_type"] = schema.database_info.vendor or ""
        metadata["schema"] = schema.database_info.name or ""
        metadata["tables_count"] = len(schema.tables)
        metadata["columns_count"] = sum(
            len(t.columns) for t in schema.tables
        )
        metadata["relationships_count"] = len(schema.relationships)

    # --- tables (enriched with descriptions, business_roles, domains) -------
    tables: list[dict[str, Any]] = []
    domains: dict[str, str] = {}
    if schema:
        desc = state.descriptions or {}
        table_descs: dict[str, str] = (
            desc.get("table_descriptions", {})
            if isinstance(desc, dict) and "table_descriptions" in desc
            else {}
        )
        column_descs: dict[str, dict[str, str]] = (
            desc.get("column_descriptions", {})
            if isinstance(desc, dict) and "column_descriptions" in desc
            else {}
        )
        business_roles = state.business_roles or {}
        domains = state.domains or {}
        semantic_types = state.semantic_types or {}

        for tbl in schema.tables:
            enriched_columns: list[dict[str, Any]] = []
            for col in tbl.columns:
                col_key = f"{tbl.table_name}.{col.column_name}"
                enriched_columns.append({
                    "column_name": col.column_name,
                    "data_type": col.data_type,
                    "is_nullable": col.is_nullable,
                    "is_primary_key": col.is_primary_key,
                    "description": (
                        column_descs.get(tbl.table_name, {}).get(col.column_name)
                    ),
                    "semantic_type": semantic_types.get(col_key),
                })

            tables.append({
                "table_name": tbl.table_name,
                "description": table_descs.get(tbl.table_name),
                "business_role": business_roles.get(tbl.table_name),
                "domain": domains.get(tbl.table_name),
                "columns": enriched_columns,
            })

    # --- views --------------------------------------------------------------
    views: list[dict[str, Any]] = []
    if schema:
        for v in schema.views:
            views.append({
                "view_name": v.view_name,
                "definition": v.definition,
            })

    # --- relationships ------------------------------------------------------
    relationships: list[dict[str, str]] = []
    if schema:
        for rel in schema.relationships:
            relationships.append({
                "from_table": rel.from_table,
                "from_column": rel.from_column,
                "to_table": rel.to_table,
                "to_column": rel.to_column,
            })

    # --- entities -----------------------------------------------------------
    entities: list[dict[str, str]] = []
    if state.entities:
        entities = [{"name": e} for e in state.entities]

    # --- entity_relationships -----------------------------------------------
    entity_relationships: list[dict[str, str]] = []
    if state.entity_relationships:
        rels = state.entity_relationships
        if isinstance(rels, dict) and "entity_relationships" in rels:
            entity_relationships = rels["entity_relationships"]
        elif isinstance(rels, list):
            entity_relationships = rels

    # --- business_processes -------------------------------------------------
    business_processes: list[dict[str, str]] = []
    if domains:
        # Derive a simple business-process list from domain groupings
        domain_groups: dict[str, list[str]] = {}
        for tbl_name, domain_label in domains.items():
            domain_groups.setdefault(domain_label, []).append(tbl_name)
        for domain_label, tbl_list in domain_groups.items():
            business_processes.append({
                "domain": domain_label,
                "tables": ", ".join(tbl_list),
            })

    # --- use_cases ----------------------------------------------------------
    use_cases: list[dict[str, str]] = state.use_cases or []

    # --- sample_queries -----------------------------------------------------
    sample_queries: list[dict[str, str]] = state.sample_queries or []

    # --- schema_patterns ----------------------------------------------------
    schema_patterns: list[dict[str, str]] = []
    if state.patterns:
        for p in state.patterns:
            schema_patterns.append({
                "pattern": p.get("pattern", ""),
                "table": p.get("table", ""),
                "evidence": (
                    ", ".join(p["evidence"])
                    if isinstance(p.get("evidence"), list)
                    else str(p.get("evidence", ""))
                ),
                "description": p.get("description", ""),
            })

    # --- validation_report --------------------------------------------------
    validation_report: list[dict[str, str]] = []
    if state.validation_report:
        for issue in state.validation_report.get("issues", []):
            validation_report.append({
                "severity": issue.get("severity", "INFO"),
                "type": issue.get("type", ""),
                "table": issue.get("table") or "",
                "column": issue.get("column") or "",
                "message": issue.get("message", ""),
            })

    return FinalOutput(
        metadata=metadata,
        tables=tables,
        views=views,
        relationships=relationships,
        entities=entities,
        entity_relationships=entity_relationships,
        business_processes=business_processes,
        use_cases=use_cases,
        sample_queries=sample_queries,
        schema_patterns=schema_patterns,
        validation_report=validation_report,
    ).model_dump()


# ---------------------------------------------------------------------------
# D. Pipeline runner
# ---------------------------------------------------------------------------


def run_pipeline(input_path: str) -> dict[str, Any]:
    """Convenience function: load metadata, run the full pipeline, return results.

    Steps
    -----
    1. Call ``load_raw_metadata(input_path)`` to get a ``CanonicalSchema``.
    2. Create a ``PipelineState`` with the schema and the raw input path.
    3. Build and compile the ``StateGraph`` via ``build_pipeline()``.
    4. Invoke the graph.
    5. Assemble the final output via ``assemble_final_output()``.
    6. Return the output as a plain dict.

    Parameters
    ----------
    input_path : str
        Path to a ``raw_metadata.json`` file.

    Returns
    -------
    dict[str, Any]
        The fully enriched output in the master plan final-output format.
    """
    logger.info("═" * 50)
    logger.info("Pipeline started — input: %s", input_path)

    # 1. Load raw metadata into canonical schema
    schema = load_raw_metadata(input_path)
    logger.info(
        "Loaded %d table(s), %d relationship(s)",
        len(schema.tables),
        len(schema.relationships),
    )

    # 2. Create initial state
    initial_state = PipelineState(
        raw_input=input_path,
        canonical_schema=schema,
    )

    # 3. Build and compile the graph
    graph = build_pipeline()
    logger.info("Pipeline graph compiled — 11 agent nodes")

    # 4. Run the pipeline
    t0 = time.time()
    result_state = graph.invoke(initial_state)
    total = time.time() - t0

    # graph.invoke returns a dict when using Pydantic BaseModel state;
    # convert back to PipelineState if necessary
    if isinstance(result_state, dict):
        final_state = PipelineState(**result_state)
    else:
        final_state = result_state

    # 5. Assemble output
    output = assemble_final_output(final_state)
    logger.info("Pipeline finished — %.1fs total", total)
    logger.info("Tables: %d | Relationships: %d | Entities: %d | Patterns: %d",
                len(output.get("tables", [])),
                len(output.get("relationships", [])),
                len(output.get("entities", [])),
                len(output.get("schema_patterns", [])))
    logger.info("═" * 50)
    return output


def run_pipeline_from_dict(raw: dict) -> dict[str, Any]:
    """Run the pipeline entirely in memory from a metadata dictionary."""
    logger.info("═" * 50)
    logger.info("Pipeline started — input: in-memory dictionary")

    # 1. Load raw metadata into canonical schema
    schema = load_raw_metadata_from_dict(raw)
    logger.info(
        "Loaded %d table(s), %d relationship(s)",
        len(schema.tables),
        len(schema.relationships),
    )

    # 2. Create initial state
    initial_state = PipelineState(
        raw_input="",
        canonical_schema=schema,
    )

    # 3. Build and compile the graph
    graph = build_pipeline()
    logger.info("Pipeline graph compiled — 11 agent nodes")

    # 4. Run the pipeline
    t0 = time.time()
    result_state = graph.invoke(initial_state)
    total = time.time() - t0

    if isinstance(result_state, dict):
        final_state = PipelineState(**result_state)
    else:
        final_state = result_state

    # 5. Assemble output
    output = assemble_final_output(final_state)
    logger.info("Pipeline finished — %.1fs total", total)
    logger.info("Tables: %d | Relationships: %d | Entities: %d | Patterns: %d",
                len(output.get("tables", [])),
                len(output.get("relationships", [])),
                len(output.get("entities", [])),
                len(output.get("schema_patterns", [])))
    logger.info("═" * 50)
    return output


__all__ = [
    "assemble_final_output",
    "build_pipeline",
    "load_raw_metadata",
    "load_raw_metadata_from_dict",
    "run_pipeline",
    "run_pipeline_from_dict",
]
