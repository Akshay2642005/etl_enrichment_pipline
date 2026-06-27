"""NL2SQL generator — converts natural language to PostgreSQL SQL.

Task 6 of the nl2sql-service plan.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

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
    "You are an expert PostgreSQL SQL generator.\n"
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
    "- Use uppercase for SQL keywords, lowercase for identifiers\n"
    "- End every statement with a semicolon\n"
    "\n"
    "Output Instructions:\n"
    "- Return ONLY the SQL query starting with SELECT/INSERT/UPDATE/DELETE\n"
    "- Do NOT include any markdown, explanations, or backticks\n"
    "- Do NOT wrap the SQL in ```sql ... ``` or any other formatting\n"
    "- Just the raw SQL statement, nothing else\n"
    "\n"
    "Examples:\n"
    "\n"
    "Question: Show employees working in the HR department\n"
    "SELECT e.* FROM employee e JOIN departmentsss d "
    "ON e.department_id = d.department_id "
    "WHERE d.department_name = 'HR';\n"
    "\n"
    "Question: List all flights with their baggage count\n"
    "SELECT f.flight_number, COUNT(b.baggage_id) AS baggage_count "
    "FROM flight f LEFT JOIN baggage b "
    "ON f.flight_id = b.flight_id "
    "GROUP BY f.flight_number;\n"
    "\n"
    "Question: Find equipment needing maintenance in the next 7 days\n"
    "SELECT e.equipment_name, e.last_maintenance_date "
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

    @staticmethod
    def _extract_sql(text: str) -> str:
        """Extract a SQL statement from LLM response text.

        Handles common wrapping formats: markdown code blocks,
        ``sql`` prefixes, or plain SQL text.
        """
        # Strip markdown code blocks first
        text = text.strip()
        # ```sql ... ``` or ``` ... ```
        block_match = re.search(
            r"```(?:sql)?\s*\n?(.*?)\n?```", text, re.DOTALL | re.IGNORECASE
        )
        if block_match:
            text = block_match.group(1).strip()

        # Remove a leading "SQL:" label if present
        text = re.sub(r"^(?:SQL|sql)\s*:\s*", "", text).strip()

        # Find the first SQL statement (starts with SELECT/INSERT/UPDATE/DELETE/WITH)
        stmt_match = re.search(
            r"\b(SELECT\b.*?;|INSERT\b.*?;|UPDATE\b.*?;|DELETE\b.*?;|WITH\b.*?;)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if stmt_match:
            return stmt_match.group(1).strip()

        # Fallback: if the whole thing looks like SQL, return it
        if text.upper().startswith("SELECT") or text.upper().startswith("WITH"):
            return text

        return ""

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
            response = self._llm.invoke(
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )

            raw_text = getattr(response, "content", str(response)) or ""
            sql = self._extract_sql(raw_text)

            if not sql:
                logger.warning(
                    "LLM returned no extractable SQL — response: %.200s", raw_text
                )
                return GenerationResult(
                    sql="",
                    confidence=0.0,
                    explanation="LLM did not return a valid SQL statement",
                    context_used=self._summarize_context(context),
                )

            logger.info(
                "Generated SQL (%.1f chars): %.80s",
                len(sql),
                sql.replace("\n", " "),
            )
            return GenerationResult(
                sql=sql,
                confidence=0.8,
                explanation=None,
                context_used=self._summarize_context(context),
            )

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
        """Format a ``SchemaContext`` into a compact prompt section.

        Only includes what the LLM needs for SQL generation: table/column
        names, data types, PK flags, and FK relationships. Strips human-
        readable descriptions and semantic types to keep the prompt small.
        """
        sections: list[str] = []

        if context.tables:
            lines: list[str] = ["### Tables"]
            for tbl in context.tables:
                tbl_name = tbl.get("table_name", "")
                lines.append(f"  Table: {tbl_name}")
                for col in tbl.get("columns", []):
                    col_name = col.get("column_name", "")
                    data_type = col.get("data_type", "")
                    pk = " PK" if col.get("is_primary_key") else ""
                    lines.append(f"    - {col_name} ({data_type}){pk}")
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
