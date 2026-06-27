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
    consolidated_enrichment_node,
)
from etl_enrichment_pipeline.models.canonical import (
    CanonicalSchema,
    ColumnSchema,
    DatabaseInfo,
    RelationshipSchema,
    TableSchema,
    ViewSchema,
)
from etl_enrichment_pipeline.models.final_output import FinalOutput
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# A. JSON Adapter — raw dict → CanonicalSchema
# ---------------------------------------------------------------------------


def raw_json_to_canonical_schema(raw: dict) -> CanonicalSchema:
    """Convert a raw metadata JSON dict to a ``CanonicalSchema``.

    The expected JSON structure::

        {
            "database_type": "postgresql",
            "schema": "public",
            "database_version": "15.0",
            "tables": [
                {
                    "table_name": "attendance",
                    "columns": [...],
                    "constraints": [...],
                    "relationships": [...]
                }
            ],
            "views": [
                {
                    "view_name": "active_users",
                    "definition": "SELECT ...",
                    "columns": [...]
                }
            ]
        }
    """
    db_version = raw.get("database_version") or raw.get("version")
    db_info = DatabaseInfo(
        name=raw.get("schema"),
        vendor=raw.get("database_type"),
        version=db_version,
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
            is_nullable = nullable_raw if isinstance(nullable_raw, bool) else True

            columns.append(
                ColumnSchema(
                    table_name=table_name,
                    column_name=col_name,
                    data_type=data_type,
                    is_nullable=is_nullable,
                )
            )

        # --- constraints: mark primary keys and build FK name lookup ---
        pk_columns: set[str] = set()
        fk_constraint_names: dict[str, str] = {}  # column_name -> constraint_name
        for constraint in tbl.get("constraints", []):
            ctype = constraint.get("constraint_type", "").upper()
            if ctype == "PRIMARY KEY":
                pk_columns.add(constraint["column_name"])
            elif ctype == "FOREIGN KEY":
                col_name_fk = constraint["column_name"]
                constraint_name = constraint.get("constraint_name")
                if constraint_name:
                    fk_constraint_names[col_name_fk] = constraint_name

        for col in columns:
            if col.column_name in pk_columns:
                col.is_primary_key = True

        tables.append(
            TableSchema(
                table_name=table_name,
                columns=columns,
            )
        )

        # --- relationships (with optional constraint_name) ---
        for rel in tbl.get("relationships", []):
            child_col = rel["child_column"]
            constraint_name = fk_constraint_names.get(child_col)
            relationships.append(
                RelationshipSchema(
                    from_table=table_name,
                    from_column=child_col,
                    to_table=rel["parent_table"],
                    to_column=rel["parent_column"],
                    constraint_name=constraint_name,
                )
            )

    # --- views ---
    views: list[ViewSchema] = []
    for v in raw.get("views", []):
        view_name: str = v["view_name"]
        view_columns: list[ColumnSchema] = []
        for col in v.get("columns", []):
            nullable_raw = col.get("nullable", True)
            view_columns.append(
                ColumnSchema(
                    table_name=view_name,
                    column_name=col["column_name"],
                    data_type=col.get("data_type", "unknown"),
                    is_nullable=(
                        nullable_raw
                        if isinstance(nullable_raw, bool)
                        else True
                    ),
                )
            )
        views.append(
            ViewSchema(
                view_name=view_name,
                definition=v.get("definition", ""),
                columns=view_columns,
            )
        )

    return CanonicalSchema(
        database_info=db_info,
        tables=tables,
        views=views,
        relationships=relationships,
    )


def load_raw_metadata(filepath: str) -> CanonicalSchema:
    """Read a ``raw_metadata.json`` file and convert it to a ``CanonicalSchema``.

    Equivalent to ``raw_json_to_canonical_schema(json.loads(…))``.

    Parameters
    ----------
    filepath :
        Path to a ``.json`` file on disk.

    Returns
    -------
    CanonicalSchema
    """
    raw = json.loads(Path(filepath).read_text(encoding="utf-8"))
    return raw_json_to_canonical_schema(raw)


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

    If ``state.canonical_schema`` is already populated (e.g. set by
    ``run_pipeline_from_raw_json``), loading is skipped.
    """
    if state.canonical_schema is None and state.raw_input:
        schema = load_raw_metadata(state.raw_input)
        state.canonical_schema = schema
    return state


def build_pipeline() -> CompiledStateGraph:
    """Build the compiled LangGraph ``StateGraph`` for the enrichment pipeline.

    Pipeline flow (2 nodes)::

        load_json → enrichment → END

    The single ``enrichment`` node internally performs one consolidated LLM
    call for all enrichment (descriptions, roles, domains, semantic types,
    entities, relationships, use cases, sample queries) followed by fast
    rule-based passes (RuleEngine, pattern_detection, validation).

    Returns
    -------
    StateGraph
        A compiled ``StateGraph`` whose ``.invoke()`` accepts a
        ``PipelineState`` and returns an updated ``PipelineState``.
    """
    workflow = StateGraph(PipelineState)

    # Register nodes (wrapped with logging)
    workflow.add_node("load_json", _logged_node("load_json", _load_json_node))
    workflow.add_node(
        "enrichment",
        _logged_node("enrichment", consolidated_enrichment_node),
    )

    # Wire edges — simple 2-node pipeline
    workflow.set_entry_point("load_json")
    workflow.add_edge("load_json", "enrichment")
    workflow.add_edge("enrichment", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# C. Helpers & final output assembler
# ---------------------------------------------------------------------------


# Common table-name-to-entity mappings for better natural language
_ENTITY_OVERRIDES = {
    "people": "person",
    "employees": "employee",
    "staff": "staff_member",
    "users": "user",
    "children": "child",
    "men": "man",
    "women": "woman",
    "countries": "country",
    "cities": "city",
    "categories": "category",
    "species": "species",
    "series": "series",
    "statuses": "status",
    "addresses": "address",
    "supplies": "supply",
}


def _singular(name: str) -> str:
    """Simple singularisation for English table names."""
    lower = name.lower()
    if lower in _ENTITY_OVERRIDES:
        return _ENTITY_OVERRIDES[lower]
    if lower.endswith("ies") and len(lower) > 3:
        return name[:-3] + "y"
    if lower.endswith("sses") or lower.endswith("shes") or lower.endswith("ches"):
        return name[:-2]
    if lower.endswith("ses"):
        return name[:-2]
    if lower.endswith("s") and not lower.endswith("ss"):
        return name[:-1]
    return name


def _describe_relationship(
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
) -> str:
    """Generate a one-line natural-language description of a FK relationship.

    Instead of ``employee.department_id → department.id``, produce something
    a human would say:  *"each employee belongs to a department"*.
    """
    child = _singular(from_table)
    parent = _singular(to_table)
    fk_lower = from_column.lower()
    parent_lower = parent.lower()

    # ── heuristic: does the FK column contain the parent table name? ──
    # e.g.  employee.dept_id  →  department.id         => "belongs to"
    #       employee.department_id → department.id     => "belongs to"
    #       employee.manager_id → employee.id          => "reports to"
    if fk_lower == f"{parent_lower}_id" or parent_lower in fk_lower:
        if parent_lower in ("manager", "supervisor", "lead", "head"):
            return f"each {child} reports to a {parent}"
        return f"each {child} belongs to a {parent}"

    # ── self-referencing FK (manager_id → employee.id) ───────────────
    if from_table == to_table and from_column != to_column:
        if parent_lower in fk_lower:
            return f"each {child} reports to another {child}"
        return f"each {child} references another {child} via {from_column}"

    # ── junction / link table (composite key referencing two parents) ─
    # Detected by checking whether ``from_table`` looks like a composite
    # of the two parent names — not fully reliable here, so fall through.

    # ── generic fallback templates ────────────────────────────────────
    # Use the column name for a hint when the parent name isn't in the FK:
    if fk_lower in ("id", f"{from_table}_id"):
        return f"each {child} is associated with one {parent}"
    if fk_lower.startswith(parent_lower):
        return f"each {child} belongs to a {parent}"

    return f"each {child} references {parent} via {from_column}"


def _relationship_label(
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
) -> str:
    """Generate a concise natural-language label for a FK relationship.

    Returns a short verb phrase like "categorized by", "belongs to",
    "reports to", or "references".
    """
    child = _singular(from_table)
    parent = _singular(to_table)
    fk_lower = from_column.lower()
    parent_lower = parent.lower()

    # FK column contains parent table name — direct association
    if fk_lower == f"{parent_lower}_id" or parent_lower in fk_lower:
        if parent_lower in ("manager", "supervisor", "lead", "head"):
            return "reports to"
        return "categorized by"

    # Self-referencing FK (e.g. employee.manager_id → employee.id)
    if from_table == to_table and from_column != to_column:
        if parent_lower in fk_lower or parent_lower in ("manager", "supervisor"):
            return "reports to"
        return "refers to"

    # FK column is just "id" or "{table}_id"
    if fk_lower in ("id", f"{from_table}_id"):
        return "associated with"

    # FK column starts with parent name
    if fk_lower.startswith(parent_lower):
        return "categorized by"

    return "references"


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
        metadata["database_name"] = schema.database_info.name or ""
        metadata["database_version"] = schema.database_info.version or ""
        metadata["tables_count"] = len(schema.tables)
        metadata["columns_count"] = sum(len(t.columns) for t in schema.tables)
        metadata["views_count"] = len(schema.views)
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
                enriched_columns.append(
                    {
                        "column_name": col.column_name,
                        "data_type": col.data_type,
                        "is_nullable": col.is_nullable,
                        "is_primary_key": col.is_primary_key,
                        "description": (
                            column_descs.get(tbl.table_name, {}).get(col.column_name)
                        ),
                        "semantic_type": semantic_types.get(col_key),
                    }
                )

            tables.append(
                {
                    "table_name": tbl.table_name,
                    "description": table_descs.get(tbl.table_name),
                    "business_role": business_roles.get(tbl.table_name),
                    "domain": domains.get(tbl.table_name),
                    "columns": enriched_columns,
                }
            )

    # --- views --------------------------------------------------------------
    views: list[dict[str, Any]] = []
    if schema:
        for v in schema.views:
            view_cols = [
                {
                    "column_name": col.column_name,
                    "data_type": col.data_type,
                    "is_nullable": col.is_nullable,
                }
                for col in v.columns
            ]
            views.append(
                {
                    "view_name": v.view_name,
                    "definition": v.definition,
                    "columns": view_cols,
                }
            )

    # --- relationships (human-readable format) ------------------------------
    relationships: list[dict[str, str]] = []
    if schema:
        for rel in schema.relationships:
            relationships.append(
                {
                    "name": _relationship_label(
                        rel.from_table,
                        rel.from_column,
                        rel.to_table,
                        rel.to_column,
                    ),
                    "description": _describe_relationship(
                        rel.from_table,
                        rel.from_column,
                        rel.to_table,
                        rel.to_column,
                    ),
                    "from_table": rel.from_table,
                    "from_column": rel.from_column,
                    "to_table": rel.to_table,
                    "to_column": rel.to_column,
                    "child_table": rel.from_table,
                    "child_column": rel.from_column,
                    "parent_table": rel.to_table,
                    "parent_column": rel.to_column,
                }
            )

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
            business_processes.append(
                {
                    "domain": domain_label,
                    "tables": ", ".join(tbl_list),
                }
            )

    # --- use_cases ----------------------------------------------------------
    use_cases: list[dict[str, str]] = state.use_cases or []

    # --- sample_queries -----------------------------------------------------
    sample_queries: list[dict[str, str]] = state.sample_queries or []

    # --- schema_patterns ----------------------------------------------------
    schema_patterns: list[dict[str, str]] = []
    if state.patterns:
        for p in state.patterns:
            schema_patterns.append(
                {
                    "pattern": p.get("pattern", ""),
                    "table": p.get("table", ""),
                    "evidence": (
                        ", ".join(p["evidence"])
                        if isinstance(p.get("evidence"), list)
                        else str(p.get("evidence", ""))
                    ),
                    "description": p.get("description", ""),
                }
            )

    # --- validation_report --------------------------------------------------
    validation_report: list[dict[str, str]] = []
    if state.validation_report:
        for issue in state.validation_report.get("issues", []):
            validation_report.append(
                {
                    "severity": issue.get("severity", "INFO"),
                    "type": issue.get("type", ""),
                    "table": issue.get("table") or "",
                    "column": issue.get("column") or "",
                    "message": issue.get("message", ""),
                }
            )

    final_output = FinalOutput(
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

    try:
        from etl_enrichment_pipeline.agents.quality_agent import QualityAnalyst
        qa = QualityAnalyst(enriched_metadata=final_output)
        q_res = qa.assess(fast_mode=True)
        
        def _fmt(val: float) -> str:
            return f"{int(val * 100)}/100"
            
        final_output["metadata"]["quality_scores"] = {
            "overall": _fmt(q_res.get("overall_score", 0.0)),
            "completeness": _fmt(q_res.get("completeness", 0.0)),
            "relationships": _fmt(q_res.get("relationships", 0.0)),
            "naming": _fmt(q_res.get("naming_convention", 0.0)),
            "documentation": _fmt(q_res.get("documentation", 0.0)),
            "normalization": _fmt(q_res.get("normalization", 0.0))
        }
    except Exception as e:
        logger.warning(f"Quality assessment failed during final output assembly: {e}")

    return final_output


# ---------------------------------------------------------------------------
# D. Pipeline runner
# ---------------------------------------------------------------------------


def run_pipeline_from_raw_json(
    raw_json: dict,
    source_label: str = "raw_metadata",
) -> dict[str, Any]:
    """Run the full enrichment pipeline from a raw metadata dict.

    Steps
    -----
    1. Convert ``raw_json``
        to a ``CanonicalSchema`` via ``raw_json_to_canonical_schema()``.
    2. Create a ``PipelineState`` with the schema.
    3. Build and compile the ``StateGraph`` via ``build_pipeline()``.
    4. Invoke the graph.
    5. Assemble the final output via ``assemble_final_output()``.
    6. Return the output as a plain dict.

    Parameters
    ----------
    raw_json :
        A dict matching the ``raw_metadata.json`` format.
    source_label :
        A human-readable label for logging (e.g. the file path or source name).

    Returns
    -------
    dict[str, Any]
        The fully enriched output in the master plan final-output format.
    """
    logger.info("═" * 50)
    logger.info("Pipeline started — source: %s", source_label)

    schema = raw_json_to_canonical_schema(raw_json)
    logger.info(
        "Loaded %d table(s), %d view(s), %d relationship(s)",
        len(schema.tables),
        len(schema.views),
        len(schema.relationships),
    )

    initial_state = PipelineState(
        raw_input=source_label,
        canonical_schema=schema,
    )

    graph = build_pipeline()
    logger.info("Pipeline graph compiled — 1 consolidated enrichment node")

    t0 = time.time()
    result_state = graph.invoke(initial_state)
    total = time.time() - t0

    if isinstance(result_state, dict):
        final_state = PipelineState(**result_state)
    else:
        final_state = result_state

    output = assemble_final_output(final_state)
    logger.info("Pipeline finished — %.1fs total", total)
    logger.info(
        "Tables: %d | Relationships: %d | Entities: %d | Patterns: %d",
        len(output.get("tables", [])),
        len(output.get("relationships", [])),
        len(output.get("entities", [])),
        len(output.get("schema_patterns", [])),
    )
    logger.info("═" * 50)
    return output


def run_pipeline(input_path: str) -> dict[str, Any]:
    """Convenience function: load metadata from a JSON file, run the pipeline.

    Equivalent to ``run_pipeline_from_raw_json(json.loads(…), source_label=input_path)``

    Parameters
    ----------
    input_path :
        Path to a ``raw_metadata.json`` file.

    Returns
    -------
    dict[str, Any]
        The fully enriched output in the master plan final-output format.
    """
    raw_json = json.loads(Path(input_path).read_text(encoding="utf-8"))
    return run_pipeline_from_raw_json(raw_json, source_label=input_path)


run_pipeline_from_dict = run_pipeline_from_raw_json

__all__ = [
    "assemble_final_output",
    "build_pipeline",
    "load_raw_metadata",
    "raw_json_to_canonical_schema",
    "run_pipeline",
    "run_pipeline_from_dict",
    "run_pipeline_from_raw_json",
]
