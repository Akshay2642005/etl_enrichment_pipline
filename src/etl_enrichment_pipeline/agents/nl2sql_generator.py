"""NL2SQL generator — converts natural language to PostgreSQL SQL.

Task 6 of the nl2sql-service plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, cast

from etl_enrichment_pipeline.core.context_builder import SchemaContext
from etl_enrichment_pipeline.core.llm import get_llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured-output schema
# ---------------------------------------------------------------------------


@dataclass
class GenerationResult:
    """Result from the NL2SQL generator for a single question."""

    sql: str = ""
    confidence: float = 0.0
    explanation: str | None = None
    context_used: dict | None = None


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert PostgreSQL SQL generator for aviation, "
    "airport operations, HR, and equipment maintenance domains.\n"
    "\n"
    "SQL Generation Rules:\n"
    "- Use table aliases for all tables in the query\n"
    "- Use explicit JOINs (INNER JOIN or LEFT JOIN) \u2014 never use "
    "implicit comma joins\n"
    "- Use proper WHERE clauses for filtering\n"
    "- Use column aliases where they add meaning (aggregates, "
    "expressions)\n"
    "- Only use tables and columns from the provided context \u2014 "
    "never invent tables or columns\n"
    "- Output ONLY valid PostgreSQL SQL (no explanations or markdown "
    "in the SQL output)\n"
    "- Use uppercase for SQL keywords, lowercase for identifiers\n"
    "- End every statement with a semicolon\n"
    "\n"
    "Examples:\n"
    "\n"
    "Question: Show employees working in the HR department\n"
    "SQL: SELECT e.* FROM employee e JOIN departmentsss d "
    "ON e.department_id = d.department_id "
    "WHERE d.department_name = 'HR';\n"
    "\n"
    "Question: List all flights with their baggage count\n"
    "SQL: SELECT f.flight_number, COUNT(b.baggage_id) AS baggage_count "
    "FROM flight f LEFT JOIN baggage b "
    "ON f.flight_id = b.flight_id "
    "GROUP BY f.flight_number;\n"
    "\n"
    "Question: Find equipment needing maintenance in the next 7 days\n"
    "SQL: SELECT e.equipment_name, e.last_maintenance_date "
    "FROM equipment e "
    "WHERE e.last_maintenance_date <= CURRENT_DATE + INTERVAL '7 days';"
)

_USER_PROMPT_TEMPLATE = (
    "Question: {question}\n"
    "\n"
    "Schema Context:\n"
    "{schema_context}"
)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class NL2SQLGenerator:
    """Natural language to PostgreSQL SQL generator.

    Uses ``get_llm()`` (ChatOpenAI-compatible) with structured output
    to produce deterministic SQL from a natural-language question and
    schema context.
    """

    def __init__(self) -> None:
        self._llm = get_llm()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, question: str, context: SchemaContext) -> GenerationResult:
        """Convert a natural-language question to PostgreSQL SQL.

        Args:
            question: The user's natural-language question.
            context: ``SchemaContext`` with tables, columns,
                relationships, and join paths relevant to the question.

        Returns:
            A ``GenerationResult`` with the generated SQL, confidence
            score, optional explanation, and context summary.
        """
        schema_text = self._format_context(context)
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            question=question, schema_context=schema_text
        )

        try:
            structured_llm = self._llm.with_structured_output(
                GenerationResult, method="function_calling"
            )
            result = cast(
                "GenerationResult",
                structured_llm.invoke(
                    [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ]
                ),
            )

            if result is None:
                logger.warning("LLM returned None \u2014 returning empty GenerationResult")
                return GenerationResult(
                    sql="",
                    confidence=0.0,
                    explanation="LLM returned no result",
                    context_used=self._summarize_context(context),
                )

            # Handle dict result (some providers return dict instead of GenerationResult)
            if isinstance(result, dict):
                result = GenerationResult(
                    sql=result.get("sql", "") or "",
                    confidence=float(result.get("confidence", 0.0) or 0.0),
                    explanation=result.get("explanation"),
                    context_used=result.get("context_used"),
                )

            if not result.sql.strip():
                logger.warning("LLM returned empty SQL \u2014 returning low-confidence result")
                result.confidence = 0.0
                result.context_used = self._summarize_context(context)
                return result

            result.context_used = self._summarize_context(context)
            logger.info(
                "Generated SQL (confidence=%.2f): %.80s",
                result.confidence,
                result.sql.replace("\n", " "),
            )
            return result

        except Exception:
            logger.exception(
                "NL2SQL generation failed \u2014 returning graceful degradation result"
            )
            return GenerationResult(
                sql="",
                confidence=0.0,
                explanation="NL2SQL generation failed due to an error",
                context_used=self._summarize_context(context),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_context(context: SchemaContext) -> str:
        """Format a ``SchemaContext`` into a structured prompt section."""
        sections: list[str] = []

        if context.tables:
            lines: list[str] = ["### Tables"]
            for tbl in context.tables:
                tbl_name = tbl.get("table_name", "")
                desc = tbl.get("description", "")
                role = tbl.get("business_role", "")
                lines.append(f"  Table: {tbl_name}")
                if desc:
                    lines.append(f"    Description: {desc}")
                if role:
                    lines.append(f"    Business Role: {role}")
                for col in tbl.get("columns", []):
                    col_name = col.get("column_name", "")
                    data_type = col.get("data_type", "")
                    sem_type = col.get("semantic_type", "")
                    col_desc = col.get("description", "")
                    pk = "PK" if col.get("is_primary_key") else ""
                    extras = f"  [{sem_type}]" if sem_type else ""
                    extras += f"  {col_desc}" if col_desc else ""
                    extras += f"  {pk}" if pk else ""
                    lines.append(f"    - {col_name} ({data_type}){extras}")
            sections.append("\n".join(lines))

        if context.columns:
            lines = ["### Relevant Columns"]
            for col in context.columns:
                lines.append(
                    f"  {col.get('table_name', '')}.{col.get('column_name', '')}"
                    f"  ({col.get('data_type', '')})"
                    f"  [{col.get('semantic_type', '')}]"
                )
            sections.append("\n".join(lines))

        if context.relationships:
            lines = ["### Foreign Key Relationships"]
            for rel in context.relationships:
                lines.append(
                    f"  {rel.get('from_table', '')}.{rel.get('from_column', '')}"
                    f"  \u2192  {rel.get('to_table', '')}.{rel.get('to_column', '')}"
                )
            sections.append("\n".join(lines))

        if context.join_paths:
            lines = ["### Join Paths"]
            for jp in context.join_paths:
                path_str = " \u2192 ".join(jp.get("tables", []))
                lines.append(f"  {path_str}  ({jp.get('hops', 0)} hop(s))")
                for step in jp.get("path", []):
                    lines.append(
                        f"    {step['from_table']}.{step['from_column']}"
                        f"  \u2192  {step['to_table']}.{step['to_column']}"
                    )
            sections.append("\n".join(lines))

        if context.entity_relationships:
            lines = ["### Entity Relationships"]
            for er in context.entity_relationships:
                meaning = er.get("business_meaning", "")
                extra = f"  :  {meaning}" if meaning else ""
                lines.append(
                    f"  {er.get('entity', '')}  \u2192  "
                    f"{er.get('related_entities', '')}{extra}"
                )
            sections.append("\n".join(lines))

        return "\n\n".join(sections).strip() if sections else "(no schema context)"

    @staticmethod
    def _summarize_context(context: SchemaContext) -> dict[str, Any]:
        """Build a summary of the context that was used for generation."""
        return {
            "table_count": len(context.tables),
            "column_count": len(context.columns),
            "relationship_count": len(context.relationships),
            "join_path_count": len(context.join_paths),
            "entity_relationship_count": len(context.entity_relationships),
            "table_names": [
                t.get("table_name", "") for t in context.tables
            ],
        }


__all__ = ["GenerationResult", "NL2SQLGenerator"]
