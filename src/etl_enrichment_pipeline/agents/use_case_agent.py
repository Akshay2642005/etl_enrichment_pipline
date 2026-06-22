"""Use case agent — generates business use cases from the enriched schema."""

from __future__ import annotations

import json
import logging
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured-output schema for the LLM
# ---------------------------------------------------------------------------


class UseCaseItem(BaseModel):
    """A single business use case identified from the schema."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Short business name for the use case")
    description: str = Field(
        default="", description="Brief description of the use case in 1-2 sentences"
    )
    involved_tables: list[str] = Field(
        default_factory=list,
        description="Table names that participate in this use case",
    )


class BusinessUseCases(BaseModel):
    """Container returned by the LLM."""

    model_config = ConfigDict(extra="ignore")

    use_cases: list[UseCaseItem] = Field(
        default_factory=list,
        description="3-5 business use cases derived from the schema",
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_USE_CASE_HINTS = """
The database schema is from an aviation / airport operations domain.
Use the table names, columns, and relationships to derive meaningful
business use cases.

Example use cases for this domain:
- Flight Turnaround Management: flight, turnaround_operation,
  turnaround_checklist, catering_task, cleaning_task, refueling_task,
  boarding_task
- Employee Attendance Tracking: employee, attendance, schedule, shift
- Baggage Tracking and Tracing: baggage, baggage_scan, baggage_loading,
  baggage_unloading, lost_baggage
- Equipment Maintenance Management: equipment, maintenance_request,
  maintenance_history
- Gate and Stand Assignment: gate, gate_assignment, stand, stand_assignment
- Crew Scheduling and Management: employee, schedule, shift, training_record
- Catering and Cleaning Operations: catering_task, cleaning_task,
  turnaround_operation
"""

_USE_CASE_SYSTEM_PROMPT = (
    "You are a business analyst specialising in database schema analysis "
    "for aviation and airport operations.\n"
    "Given a list of database tables with their columns, data types, and "
    "foreign-key relationships, derive 3-5 meaningful business use cases.\n"
    "\n"
    "{domain_hints}\n"
    "\n"
    "Each use case must include:\n"
    "- name: A short, descriptive name for the use case\n"
    "- description: A 1-2 sentence explanation of the business value\n"
    "- involved_tables: The table names that are part of this use case\n"
    "\n"
    "Focus on how the tables work together to support real business processes."
)

_USE_CASE_USER_PROMPT = (
    "Derive business use cases from the following schema:\n"
    "\n"
    "Schema context:\n"
    "{schema_context}\n"
    "\n"
    "Tables and columns:\n"
    "{tables_info}\n"
    "\n"
    "Foreign-key relationships:\n"
    "{relationships_info}\n"
    "\n"
    "Return 3-5 business use cases."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_schema(state: PipelineState) -> tuple[str, str, str]:
    """Format schema context, tables, and relationships for the prompt.

    Returns (schema_context, tables_info, relationships_info).
    """
    schema = state.canonical_schema
    if schema is None:
        return "", "", ""

    # Schema-level context
    context_parts: list[str] = []
    db = schema.database_info
    if db:
        if db.name:
            context_parts.append(f"Database: {db.name}")
        if db.vendor:
            context_parts.append(f"Vendor: {db.vendor}")
    schema_context = (
        " | ".join(context_parts) if context_parts else "(no database info)"
    )

    # Tables and columns
    table_lines: list[str] = []
    for table in schema.tables:
        cols = ", ".join(
            f"{c.column_name} ({c.data_type}){' PK' if c.is_primary_key else ''}"
            for c in table.columns
        )
        table_lines.append(f"  - {table.table_name}: [{cols}]")
    tables_info = "\n".join(table_lines) if table_lines else "(no tables)"

    # Relationships
    rel_lines: list[str] = []
    for rel in schema.relationships:
        rel_lines.append(
            f"  - {rel.from_table}.{rel.from_column} \u2192 "
            f"{rel.to_table}.{rel.to_column}"
        )
    relationships_info = "\n".join(rel_lines) if rel_lines else "(no relationships)"

    return schema_context, tables_info, relationships_info


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def use_case_node(state: PipelineState) -> PipelineState:
    """Generate business use cases derived from the enriched schema.

    Uses a LangChain ``ChatOpenRouter`` agent with structured output to produce
    3-5 business use cases based on table names, columns, and FK
    relationships.

    Gracefully degrades (empty list + warning log) when:

    * ``state.canonical_schema`` is ``None``
    * The ``OPENROUTER_API_KEY`` environment variable is not set
    * The LLM call fails for any other reason

    Args:
        state: The current pipeline state containing the canonical schema.

    Returns:
        Updated pipeline state with ``use_cases`` populated.
    """
    # --- Early exit when there is no schema ----------------------------------
    if state.canonical_schema is None:
        logger.warning("canonical_schema is None \u2014 skipping use case generation")
        state.use_cases = []
        return state

    schema_context, tables_info, relationships_info = _format_schema(state)

    if not tables_info or tables_info == "(no tables)":
        logger.warning(
            "canonical_schema contains no tables \u2014 skipping use case generation"
        )
        state.use_cases = []
        return state

    # --- Build the prompt ----------------------------------------------------
    system_prompt = _USE_CASE_SYSTEM_PROMPT.format(domain_hints=_USE_CASE_HINTS)
    user_prompt = _USE_CASE_USER_PROMPT.format(
        schema_context=schema_context,
        tables_info=tables_info,
        relationships_info=relationships_info,
    )

    # --- Call the LLM with structured output ---------------------------------
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(
            BusinessUseCases, method="function_calling"
        )
        result = cast(
            "BusinessUseCases",
            structured_llm.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            ),
        )

        if result is None:
            logger.warning("LLM returned None — falling back to empty use cases")
            state.use_cases = []
            return state

        # Convert to state-compatible format (list[dict[str, str]])
        # involved_tables is a list[str] in the model but must be stored as a
        # string in the shared state (UseCaseList = list[dict[str, str]]).
        state.use_cases = [
            {
                "name": uc.name,
                "description": uc.description,
                "involved_tables": json.dumps(uc.involved_tables),
            }
            for uc in (result.use_cases or [])
        ]
        logger.info("Generated %d business use case(s)", len(state.use_cases))

    except Exception:
        logger.exception("Use case generation failed \u2014 falling back to empty list")
        state.use_cases = []

    return state
