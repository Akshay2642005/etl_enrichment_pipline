"""Entity discovery agent — converts schema objects into business entities."""

from __future__ import annotations

import logging
from typing import cast

from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.agent_outputs import EntityDiscoveryOutput
from etl_enrichment_pipeline.models.canonical import CanonicalSchema
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates for entity discovery
# ---------------------------------------------------------------------------

_ENTITY_SYSTEM_PROMPT = """\
You are a database schema analyst specializing in business entity discovery.
Given a list of database tables with their columns, data types, and foreign-key
relationships, identify the **business entity** each table belongs to.

## Rules

1.  **Name conversion**: Convert each table name into a singular, PascalCase
    business-entity name (e.g. `employee` → `Employee`, `attendance` → `Attendance`,
    `employee_role` → `EmployeeRole`).

2.  **Group related tables**: Tables that describe the same real-world concept
    should be merged into a single entity even if the underlying table names
    differ. For example:
    - `baggage`, `baggage_scan`, `baggage_loading`, `baggage_unloading`,
      `lost_baggage` → all map to the **`Baggage`** entity (different facets
      of baggage handling).
    - `catering_task`, `cleaning_task`, `refueling_task`, `boarding_task`
      → map to **`TurnaroundTask`** or are subsumed under **`TurnaroundOperation`**.
    - `equipment`, `equipment_type`, `equipment_assignment`,
      `maintenance_history`, `maintenance_request` → all map to **`Equipment`**.
    - `gate`, `gate_assignment` → **`Gate`** entity.
    - `stand`, `stand_assignment` → **`Stand`** entity.

3.  **Do NOT create entities for junction / history / audit tables**: Junction
    tables (e.g. `employee_role` — composite FK references to 2+ tables),
    history tables, and audit tables should be merged into the entity they
    serve rather than becoming standalone entities. For example:
    - `employee_role` is a junction between `employee` and `role` — do NOT
      emit it as a separate entity.

4.  **Each table maps to exactly one entity**. Produce a flat list of every
    table mapped to its entity name. Then at the end, return only the
    **unique, deduplicated** entity names.

5.  **Think about real-world business objects**. The goal is to produce a
    concise list of entities that a business analyst would recognise.

## Output

Return a list of unique PascalCase entity name strings.
"""

_ENTITY_USER_PROMPT = """\
Analyse the following database schema and produce a deduplicated list of
business entity names.

Schema tables:
{schema_tables}

Foreign-key relationships:
{schema_relationships}

Return the unique list of discovered business entity names (PascalCase,
singular)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_tables(schema: CanonicalSchema) -> str:
    """Format all tables and their columns into a readable string."""
    lines: list[str] = []
    for tbl in schema.tables:
        cols = ", ".join(
            f"{c.column_name} ({c.data_type}){' PK' if c.is_primary_key else ''}"
            for c in tbl.columns
        )
        lines.append(f"  - {tbl.table_name}: [{cols}]")
    if not lines:
        return "(no tables)"
    return "\n".join(lines)


def _format_relationships(schema: CanonicalSchema) -> str:
    """Format FK relationships into a readable string."""
    if not schema.relationships:
        return "(no relationships)"
    lines: list[str] = []
    for rel in schema.relationships:
        lines.append(
            f"  - {rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


def entity_discovery_node(state: PipelineState) -> PipelineState:
    """Convert schema tables / views into business entity names.

    Uses a LangChain ``ChatOpenRouter`` agent with structured output to identify
    business entities from the canonical schema. Related tables (junction,
    history, sub-aspects) are merged into the entity they serve rather than
    becoming standalone entities.

    Gracefully degrades (``state.entities`` left as ``None`` + warning log) when:

    - ``state.canonical_schema`` is ``None``
    - The ``OPENROUTER_API_KEY`` environment variable is not set
    - The LLM call fails for any other reason

    Args:
        state: The current pipeline state containing the canonical schema.

    Returns:
        Updated pipeline state with ``entities`` populated.
    """
    # --- Early exit when there is no schema to analyse -----------------------
    if state.canonical_schema is None:
        logger.warning("canonical_schema is None — skipping entity discovery")
        state.entities = None
        return state

    tables_str = _format_tables(state.canonical_schema)

    if not tables_str or tables_str == "(no tables)":
        logger.warning(
            "canonical_schema contains no tables — skipping entity discovery"
        )
        state.entities = None
        return state

    relationships_str = _format_relationships(state.canonical_schema)

    # --- Attempt LLM-based entity discovery ----------------------------------
    try:
        llm = get_llm()

        structured_llm = llm.with_structured_output(
            EntityDiscoveryOutput, method="function_calling"
        )

        system_prompt = _ENTITY_SYSTEM_PROMPT
        user_prompt = _ENTITY_USER_PROMPT.format(
            schema_tables=tables_str,
            schema_relationships=relationships_str,
        )

        result = cast(
            "EntityDiscoveryOutput",
            structured_llm.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            ),
        )

        if result is None:
            logger.warning("LLM returned None — falling back to empty entities")
            state.entities = None
            return state

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for entity in (result.entities or []):
            if entity not in seen:
                seen.add(entity)
                deduped.append(entity)

        state.entities = deduped
        logger.info("Discovered %d entity/ies", len(deduped))

    except Exception:
        logger.exception("Entity discovery failed — falling back to empty entities")
        state.entities = None

    return state
