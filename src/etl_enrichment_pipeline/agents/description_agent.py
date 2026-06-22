"""Description agent — generates descriptions for tables, columns, and views."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

# ---------------------------------------------------------------------------
# Structured-output schema for the LLM
# ---------------------------------------------------------------------------

class TableDescriptions(BaseModel):
    """Schema for the LLM to fill with table and column descriptions."""

    model_config = ConfigDict(extra="forbid")

    table_descriptions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps each table_name to a concise business description"
            " (1-2 sentences)."
        ),
    )
    column_descriptions: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description=(
            "Maps each table_name to a dict of column_name → short description. "
            "Every column for every table must be included."
        ),
    )


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a database schema analyst. Given the following database table and \
column information, generate concise business descriptions.

For each table, describe what business data it stores and its purpose \
(1-2 sentences).
For each column, describe what business attribute it represents \
(a short phrase)."""


def _build_schema_text(
    database_info: str,
    tables_info: str,
) -> str:
    """Assemble the user message from the schema context."""
    parts: list[str] = []
    if database_info:
        parts.append(f"Schema context:\n{database_info}\n")
    parts.append(f"Tables and columns:\n{tables_info}")
    return "\n".join(parts)


def _format_tables(state: PipelineState) -> tuple[str, str]:
    """Format database info and tables for the prompt.

    Returns (database_info_text, tables_text).
    """
    schema = state.canonical_schema
    if schema is None:
        return "", ""

    # Database info
    db = schema.database_info
    db_lines: list[str] = []
    if db:
        if db.name:
            db_lines.append(f"  Database name: {db.name}")
        if db.vendor:
            db_lines.append(f"  Vendor: {db.vendor}")
        if db.version:
            db_lines.append(f"  Version: {db.version}")
    database_info = "\n".join(db_lines) if db_lines else ""

    # Tables and columns
    table_lines: list[str] = []
    for table in schema.tables:
        table_lines.append(f"\nTable: {table.table_name}")
        for col in table.columns:
            nullable = "NULL" if col.is_nullable else "NOT NULL"
            pk = " PK" if col.is_primary_key else ""
            table_lines.append(
                f"  - {col.column_name}: {col.data_type}"
                f" ({nullable}{pk})"
            )
    tables_text = "".join(table_lines)

    return database_info, tables_text


def description_node(state: PipelineState) -> PipelineState:
    """Generate human-readable descriptions for tables, columns, and views.

    Uses a GPT-4o LLM to produce concise business descriptions for every
    table and column in ``state.canonical_schema``.

    Results are stored in ``state.descriptions`` as a dict with two keys:

    * ``table_descriptions`` — maps ``table_name → str``
    * ``column_descriptions`` — maps ``table_name → {column_name → str}``

    If ``canonical_schema`` is ``None`` or the LLM call fails (e.g. missing
    API key), empty dicts are stored and the state is returned unchanged.
    """
    # --- early exit when there is nothing to describe ---------------------
    if state.canonical_schema is None:
        state.descriptions = {
            "table_descriptions": {},
            "column_descriptions": {},
        }
        return state

    database_info, tables_text = _format_tables(state)

    if not tables_text.strip():
        state.descriptions = {
            "table_descriptions": {},
            "column_descriptions": {},
        }
        return state

    # --- build the prompt ------------------------------------------------
    user_message = _build_schema_text(database_info, tables_text)

    # --- call the LLM with structured output -----------------------------
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(TableDescriptions)
        result = cast("TableDescriptions", structured_llm.invoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
        ))

        state.descriptions = {
            "table_descriptions": result.table_descriptions,
            "column_descriptions": result.column_descriptions,
        }

    except Exception:
        # Graceful degradation: missing / invalid API key, network error, etc.
        state.descriptions = {
            "table_descriptions": {},
            "column_descriptions": {},
        }

    return state
