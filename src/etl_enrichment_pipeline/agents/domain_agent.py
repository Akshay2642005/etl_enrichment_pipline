"""Domain agent — detects business domain (Healthcare, Banking, Retail, etc.)."""

from __future__ import annotations

import logging
from typing import cast

from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.agent_outputs import DomainOutput
from etl_enrichment_pipeline.models.canonical import CanonicalSchema
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known aviation / airport-operations domain hints the LLM uses as context
# to produce consistent, accurate domain labels.
# ---------------------------------------------------------------------------
_DOMAIN_HINTS = """
The database schema is from an aviation / airport operations domain.
Use the table names and columns to determine the most specific
business domain label.

Known domain categories:
- Flight Operations: flight, flight_schedule, flight_leg,
  flight_crew_assignment
- Baggage Handling: baggage, baggage_loading, baggage_unloading,
  baggage_scan, lost_baggage
- Human Resources: employee, department, role, attendance, schedule,
  leave_request, training_record, shift
- Equipment Management: equipment, equipment_type,
  equipment_assignment, maintenance_history, maintenance_request
- Airport Infrastructure: gate, stand, gate_assignment,
  stand_assignment
- Ground Operations / Turnaround: catering_task, cleaning_task,
  refueling_task, boarding_task
- Turnaround Management: turnaround_operation, turnaround_checklist

If a table does not clearly match any aviation sub-domain, assign a
broader label such as "Reference Data" or "Lookup / Reference".
""".strip()

_DOMAIN_SYSTEM_PROMPT = (
    "You are a database schema analyst specializing in domain classification.\n"
    "Given a list of database tables with their columns and data types, classify"
    " each table\n"
    "into its most specific business domain label.\n"
    "\n"
    "{domain_hints}\n"
    "\n"
    "Return a mapping of each table_name to its detected domain.\n"
    "Each table must have exactly one domain label."
    " Use consistent labels across tables."
)

_DOMAIN_USER_PROMPT = (
    "Classify the business domain for each table in the following schema:\n"
    "\n"
    "{schema_tables}\n"
    "\n"
    "Return the domain for every table listed above."
)


def _format_tables(schema: CanonicalSchema) -> str:
    """Format all tables and their columns into a readable string for the prompt."""
    lines: list[str] = []
    for tbl in schema.tables:
        cols = ", ".join(f"{c.column_name} ({c.data_type})" for c in tbl.columns)
        lines.append(f"  - {tbl.table_name}: [{cols}]")
    if not lines:
        return "(no tables)"
    return "\n".join(lines)


def domain_node(state: PipelineState) -> PipelineState:
    """Detect the business domain of each table (Healthcare, Banking, Retail, etc.).

    Uses a LangChain ChatOpenRouter agent with structured output to classify
    every table in the canonical schema into a business domain label.

    Gracefully degrades (empty dict + warning log) when:
      - ``state.canonical_schema`` is ``None``
      - The ``OPENROUTER_API_KEY`` environment variable is not set
      - The LLM call fails for any other reason

    Args:
        state: The current pipeline state containing the canonical schema.

    Returns:
        Updated pipeline state with ``domains`` populated.
    """
    # --- Early exit when there is no schema to analyse -----------------------
    if state.canonical_schema is None:
        logger.warning("canonical_schema is None — skipping domain detection")
        state.domains = {}
        return state

    tables_str = _format_tables(state.canonical_schema)

    if not tables_str or tables_str == "(no tables)":
        logger.warning(
            "canonical_schema contains no tables — skipping domain detection"
        )
        state.domains = {}
        return state

    # --- Attempt LLM-based classification ------------------------------------
    try:
        llm = get_llm()

        structured_llm = llm.with_structured_output(
            DomainOutput, method="function_calling"
        )

        system_prompt = _DOMAIN_SYSTEM_PROMPT.format(domain_hints=_DOMAIN_HINTS)
        user_prompt = _DOMAIN_USER_PROMPT.format(schema_tables=tables_str)

        result = cast(
            "DomainOutput",
            structured_llm.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            ),
        )

        state.domains = result.domains

        # If the LLM returned an empty dict or a list instead of the
        # expected mapping, build a fallback from the schema.
        if not state.domains and state.canonical_schema is not None:
            logger.warning(
                "LLM returned no valid domains — using fallback for %d table(s)",
                len(state.canonical_schema.tables),
            )
            state.domains = {
                tbl.table_name: "Unknown"
                for tbl in state.canonical_schema.tables
            }

        logger.info("Detected domains for %d table(s)", len(state.domains))

    except Exception:
        logger.exception("Domain detection failed — falling back to empty domain map")
        state.domains = {}

    return state
