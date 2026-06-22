"""Sample query agent — generates sample business queries
(Lookup, Reporting, Analytics, Aggregation, Relationship)."""

from __future__ import annotations

import logging
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured-output schema for the LLM
# ---------------------------------------------------------------------------


class QueryItem(BaseModel):
    """A single sample business query with natural-language question and SQL."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(description="Natural-language question the query answers")
    sql: str = Field(description="SQL query that answers the question")
    category: str = Field(
        description=(
            "One of: Lookup, Reporting, Analytics, Aggregation, Relationship"
        ),
    )


class SampleQueries(BaseModel):
    """Container returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    queries: list[QueryItem] = Field(
        description="3-5 sample business queries across different categories",
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SAMPLE_QUERY_HINTS = """
The database schema is from an aviation / airport operations domain.
Generate realistic SQL queries that reflect real business needs.

Query categories:
- Lookup: Simple lookups by key (e.g. find baggage by tag number,
  find flight by number)
- Reporting: Structured reports (e.g. list employees in a department,
  list flights on a date)
- Analytics: Analytical queries with GROUP BY and aggregation
  (e.g. most baggage items per flight)
- Aggregation: Summary statistics (e.g. total employees per department,
  average turnaround time)
- Relationship: Multi-table JOINs exploring entity relationships
  (e.g. all turnaround tasks for a flight)

Use standard SQL. Include JOINs where relationships exist.
Use meaningful table and column aliases.
"""

_SAMPLE_QUERY_SYSTEM_PROMPT = (
    "You are a data analyst specialising in aviation and airport operations.\n"
    "Given a database schema with tables, columns, and foreign-key "
    "relationships, generate 3-5 realistic sample business queries.\n"
    "\n"
    "{domain_hints}\n"
    "\n"
    "Each query must include:\n"
    "- question: A natural-language question the query answers\n"
    "- sql: The SQL query (use standard SQL syntax)\n"
    "- category: One of Lookup, Reporting, Analytics, Aggregation, "
    "Relationship\n"
    "\n"
    "Spread queries across at least 3 different categories. "
    "Make SQL realistic with proper JOINs, aliases, and WHERE clauses."
)

_SAMPLE_QUERY_USER_PROMPT = (
    "Generate sample business queries for the following schema:\n"
    "\n"
    "Tables and columns:\n"
    "{tables_info}\n"
    "\n"
    "Foreign-key relationships:\n"
    "{relationships_info}\n"
    "\n"
    "Generate 3-5 sample queries spread across at least "
    "3 different categories."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_schema(state: PipelineState) -> tuple[str, str]:
    """Format tables and relationships for the prompt.

    Returns (tables_info, relationships_info).
    """
    schema = state.canonical_schema
    if schema is None:
        return "", ""

    # Enrich column info with semantic types if available
    semantic_types = state.semantic_types or {}

    # Tables and columns
    table_lines: list[str] = []
    for table in schema.tables:
        col_lines: list[str] = []
        for c in table.columns:
            col_key = f"{table.table_name}.{c.column_name}"
            sem_type = semantic_types.get(col_key, "")
            sem_str = f" [{sem_type}]" if sem_type else ""
            col_lines.append(
                f"{c.column_name} ({c.data_type}){sem_str}"
                f"{' PK' if c.is_primary_key else ''}"
            )
        table_lines.append(
            f"  - {table.table_name}: [{', '.join(col_lines)}]"
        )
    tables_info = "\n".join(table_lines) if table_lines else "(no tables)"

    # Relationships
    rel_lines: list[str] = []
    for rel in schema.relationships:
        rel_lines.append(
            f"  - {rel.from_table}.{rel.from_column} \u2192 "
            f"{rel.to_table}.{rel.to_column}"
        )
    relationships_info = "\n".join(rel_lines) if rel_lines else "(no relationships)"

    return tables_info, relationships_info


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def sample_query_node(state: PipelineState) -> PipelineState:
    """Generate sample business queries across categories: Lookup, Reporting,
    Analytics, Aggregation, Relationship.

    Uses a LangChain ``ChatOpenRouter`` agent with structured output to produce
    3-5 realistic SQL queries based on the enriched schema context (table
    names, columns with semantic types, and FK relationships).

    Gracefully degrades (empty list + warning log) when:

    * ``state.canonical_schema`` is ``None``
    * The ``OPENROUTER_API_KEY`` environment variable is not set
    * The LLM call fails for any other reason

    Args:
        state: The current pipeline state containing the canonical schema
              and optional enrichment context (semantic_types, etc.).

    Returns:
        Updated pipeline state with ``sample_queries`` populated.
    """
    # --- Early exit when there is no schema ----------------------------------
    if state.canonical_schema is None:
        logger.warning(
            "canonical_schema is None \u2014 skipping sample query generation"
        )
        state.sample_queries = []
        return state

    tables_info, relationships_info = _format_schema(state)

    if not tables_info or tables_info == "(no tables)":
        logger.warning(
            "canonical_schema contains no tables \u2014 "
            "skipping sample query generation"
        )
        state.sample_queries = []
        return state

    # --- Build the prompt ----------------------------------------------------
    system_prompt = _SAMPLE_QUERY_SYSTEM_PROMPT.format(
        domain_hints=_SAMPLE_QUERY_HINTS
    )
    user_prompt = _SAMPLE_QUERY_USER_PROMPT.format(
        tables_info=tables_info,
        relationships_info=relationships_info,
    )

    # --- Call the LLM with structured output ---------------------------------
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(SampleQueries)
        result = cast("SampleQueries", structured_llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]))

        # Convert to state-compatible format (list[dict[str, str]])
        state.sample_queries = [
            {
                "question": q.question,
                "sql": q.sql,
                "category": q.category,
            }
            for q in result.queries
        ]
        logger.info("Generated %d sample query(ies)", len(state.sample_queries))

    except Exception:
        logger.exception(
            "Sample query generation failed \u2014 falling back to empty list"
        )
        state.sample_queries = []

    return state
