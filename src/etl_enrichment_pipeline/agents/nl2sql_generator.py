"""NL2SQL generator — converts natural language to PostgreSQL SQL.

Task 6 of the nl2sql-service plan.

Includes schema-aware guardrails that reject out-of-scope questions before
generating SQL and enforce strict table/column existence constraints.
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
    """Result from the NL2SQL generator for a single question.

    Attributes:
        sql: The generated SQL statement (empty when status is OUT_OF_SCOPE).
        confidence: Confidence score (0.0 for OUT_OF_SCOPE).
        explanation: Optional explanation of the generated SQL.
        context_used: Summary of schema context used for generation.
        status: ``"SUCCESS"`` or ``"OUT_OF_SCOPE"``.
        reason: Populated when status is ``"OUT_OF_SCOPE"``.
    """

    sql: str = ""
    confidence: float = 0.0
    explanation: str | None = None
    context_used: dict | None = None
    status: str = "SUCCESS"
    reason: str | None = None


# ---------------------------------------------------------------------------
# Placeholder SQL patterns to reject after generation
# ---------------------------------------------------------------------------

_PLACEHOLDER_SQL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bSELECT\s+0\b", re.IGNORECASE),
    re.compile(r"\bSELECT\s+NULL\b", re.IGNORECASE),
    re.compile(r"\bSELECT\s+\d+\s+AS\s+", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert PostgreSQL SQL generator.\n"
    "\n"
    "## Guardrails (must follow these rules strictly)\n"
    "\n"
    "1. **Schema-only answers**: Only use tables, views, and columns from the "
    "provided Schema Context. Never invent tables, views, or columns.\n"
    "2. **Out-of-scope detection**: If the question references entities, "
    "metrics, or concepts that do not appear in the Schema Context, do NOT "
    "generate SQL. Instead respond with exactly:\n"
    "   OUT_OF_SCOPE: Question cannot be answered using the available "
    "database schema.\n"
    "3. **No fabricated data**: Never generate placeholder or fallback SQL "
    "such as SELECT 0, SELECT NULL, hardcoded counts, or any query that "
    "references tables or columns not present in the schema.\n"
    "4. **When uncertain, reject**: If you are unsure whether the question "
    "maps to the schema, return OUT_OF_SCOPE rather than generating "
    "potentially incorrect SQL.\n"
    "\n"
    "## SQL Generation Rules\n"
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
    "## Output Format\n"
    "- If the question is answerable: Return ONLY the raw SQL query. "
    "No markdown, no backticks, no explanations, no ```sql blocks.\n"
    "- If the question is NOT answerable: Return exactly:\n"
    "  OUT_OF_SCOPE: <specific reason>\n"
    "\n"
    "Examples:\n"
    "\n"
    "Question: Show employees working in the HR department\n"
    "SELECT e.* FROM employee e JOIN department d "
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

        Applies schema guardrails before and after generation:

        * Pre-check: empty schema context → OUT_OF_SCOPE
        * LLM generation with guardrail-aware system prompt
        * Post-check: placeholder/fabricated SQL → OUT_OF_SCOPE

        Args:
            question: The user's natural-language question.
            context: ``SchemaContext`` with tables, columns,
                relationships, and join paths relevant to the question.

        Returns:
            A ``GenerationResult`` with the generated SQL, confidence
            score, optional explanation, context summary, and scope status.
        """
        # ── Pre-check: Empty schema context ─────────────────────────────
        if not context.tables:
            logger.info(
                "OUT_OF_SCOPE (no schema context) — question: %.80s", question
            )
            return GenerationResult(
                status="OUT_OF_SCOPE",
                reason="Question cannot be answered using the available "
                "database schema — no matching tables found.",
                context_used=self._summarize_context(context),
            )

        # ── Generate ────────────────────────────────────────────────────
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
            trimmed = raw_text.strip()

            # ── Check if LLM returned OUT_OF_SCOPE ──────────────────────
            if trimmed.upper().startswith("OUT_OF_SCOPE"):
                reason = trimmed[len("OUT_OF_SCOPE:"):].strip()
                if not reason:
                    reason = "Question cannot be answered using the "
                    "available database schema."
                logger.info("LLM returned OUT_OF_SCOPE: %s", reason)
                return GenerationResult(
                    status="OUT_OF_SCOPE",
                    reason=reason,
                    context_used=self._summarize_context(context),
                )

            sql = self._extract_sql(trimmed)

            if not sql:
                logger.warning(
                    "LLM returned no extractable SQL — response: %.200s",
                    raw_text,
                )
                return GenerationResult(
                    status="OUT_OF_SCOPE",
                    reason="Question cannot be answered using the available "
                    "database schema.",
                    explanation="LLM did not return a valid SQL statement",
                    context_used=self._summarize_context(context),
                )

            # ── Post-check: placeholder / fabricated SQL ─────────────────
            if self._is_placeholder_sql(sql):
                logger.warning(
                    "LLM returned placeholder SQL — rejecting: %.100s",
                    sql.replace("\n", " "),
                )
                return GenerationResult(
                    status="OUT_OF_SCOPE",
                    reason="Question cannot be answered using the available "
                    "database schema.",
                    explanation="LLM returned placeholder SQL instead of a "
                    "real query",
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
                status="OUT_OF_SCOPE",
                reason="Question cannot be answered using the available "
                "database schema.",
                explanation="NL2SQL generation failed due to an error",
                context_used=self._summarize_context(context),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_placeholder_sql(sql: str) -> bool:
        """Detect placeholder or fabricated SQL patterns.

        Returns ``True`` if the SQL matches known placeholder patterns
        (SELECT 0, SELECT NULL, hardcoded scalar values).
        """
        return any(pattern.search(sql) for pattern in _PLACEHOLDER_SQL_PATTERNS)

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
