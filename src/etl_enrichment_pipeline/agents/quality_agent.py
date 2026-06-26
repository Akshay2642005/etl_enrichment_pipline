"""Quality Analyst — assesses schema quality across 6 dimensions.

Reads from the enriched metadata dict and evaluates completeness,
relationships, naming conventions, documentation quality,
normalization, and produces an overall weighted score with
actionable recommendations.  Uses the LLM for boilerplate
detection and recommendation generation only.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel

from etl_enrichment_pipeline.core.llm import get_llm

logger = logging.getLogger(__name__)

__all__ = ["QualityAnalyst"]

# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------


class _BoilerplateResult(BaseModel):
    """Result from boilerplate description detection."""

    is_boilerplate: bool
    reason: str


class _RecommendationsResult(BaseModel):
    """Generated recommendations based on quality analysis."""

    recommendations: list[str]


# ---------------------------------------------------------------------------
# Weights for the composite overall score
# ---------------------------------------------------------------------------

_WEIGHTS: dict[str, float] = {
    "completeness": 0.25,
    "relationships": 0.20,
    "naming_convention": 0.15,
    "documentation": 0.25,
    "normalization": 0.15,
}

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_FK_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+_fkey$")

# Maximum number of LLM boilerplate checks per assess() call
_MAX_BOILERPLATE_CHECKS = 15

_BOILERPLATE_PROMPT = (
    "You are a data quality analyst reviewing database schema descriptions.\n"
    "Determine if the following description is boilerplate — generic,\n"
    "vague, auto-generated, or uninformative.\n"
    "A good description clearly says what the table or column represents\n"
    "in specific business terms.\n"
    "Boilerplate examples:\n"
    '- "Description of the table"\n'
    '- "Column for storing the value"\n'
    '- "Unique identifier for the record"\n'
    '- "The name of the X"\n'
    "- Any description that could apply to ANY table/column unchanged.\n"
    "\n"
    'Description: "{description}"\n'
    "Type: {item_type}\n"
    "Name: {item_name}"
    "give output in JSON format"
    """{{
      "overall_score": 0,
      "completeness": 0,
      "relationships": 0,
      "naming_convention": 0,
      "documentation": 0,
      "normalization": 0,
      "issues": [],
      "recommendations": []
    }}"""
)

_RECOMMENDATION_PROMPT = (
    "Based on the following database schema quality assessment results, "
    "generate 3-5 actionable, specific recommendations for improvement.\n"
    "\n"
    "Scores (0.0-1.0, higher is better):\n"
    "- Completeness: {completeness:.2f}\n"
    "- Relationships: {relationships:.2f}\n"
    "- Naming Convention: {naming:.2f}\n"
    "- Documentation: {documentation:.2f}\n"
    "- Normalization: {normalization:.2f}\n"
    "\n"
    "Total issues found: {issue_count}\n"
    "{sample_issues}"
    "\n"
    "Focus on the lowest-scoring dimensions first. "
    "Be specific and mention actual patterns when possible."
)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _detect_boilerplate(
    description: str,
    item_type: str,
    item_name: str,
) -> _BoilerplateResult:
    """Use LLM to determine if *description* is boilerplate.

    Returns a ``_BoilerplateResult`` with ``is_boilerplate=False`` on
    failure so the caller never blocks on an LLM error.
    """
    llm = get_llm()
    structured = llm.with_structured_output(
        _BoilerplateResult, method="function_calling"
    )
    prompt = _BOILERPLATE_PROMPT.format(
        description=description,
        item_type=item_type,
        item_name=item_name,
    )
    try:
        result = structured.invoke(
            [
                {"role": "user", "content": prompt},
            ]
        )
        if isinstance(result, dict):
            return _BoilerplateResult(
                is_boilerplate=result.get("is_boilerplate", False),
                reason=result.get("reason", ""),
            )
        if isinstance(result, _BoilerplateResult):
            return result
        logger.debug(
            "Boilerplate detection returned %s for %s '%s' — using fallback",
            type(result).__name__,
            item_type,
            item_name,
        )
        return _BoilerplateResult(
            is_boilerplate=False, reason="Unexpected LLM response"
        )
    except Exception:
        logger.debug(
            "Boilerplate detection LLM call failed for %s '%s' — using fallback",
            item_type,
            item_name,
        )
        return _BoilerplateResult(is_boilerplate=False, reason="LLM call failed")


# ---------------------------------------------------------------------------
# Quality Analyst
# ---------------------------------------------------------------------------


class QualityAnalyst:
    """Analyses enriched metadata quality across 6 dimensions.

    Accepts the enriched metadata dict (same shape as
    ``output/enriched_metadata.json``) and computes quality scores
    **without** making any live database queries.

    The enriched metadata is expected to have at least:
    - ``tables``: list of dicts with table_name, description,
      business_role, domain, columns (each with column_name,
      data_type, description, semantic_type, is_primary_key, ...)
    - ``relationships``: list of FK entries with name, description
    - ``entity_relationships``: list of ER entries with entity,
      related_entities, business_meaning
    """

    def __init__(self, enriched_metadata: dict[str, Any]) -> None:
        self._metadata = enriched_metadata
        self._tables: list[dict[str, Any]] = enriched_metadata.get("tables", [])
        self._relationships: list[dict[str, Any]] = enriched_metadata.get(
            "relationships", []
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess(
        self,
        table_name: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Run quality assessment across all 6 dimensions.

        Args:
            table_name: If provided, only assess this table.
            domain: If provided, only assess tables in this domain.

        Returns:
            dict with keys: ``overall_score``, ``completeness``,
            ``relationships``, ``naming_convention``, ``documentation``,
            ``normalization``, ``issues``, ``recommendations``.
        """
        tables = self._tables
        if table_name:
            tables = [t for t in tables if t["table_name"] == table_name]
        if domain:
            tables = [t for t in tables if t.get("domain") == domain]

        issues: list[dict[str, Any]] = []

        completeness_score = self._score_completeness(tables, issues)
        relationships_score = self._score_relationships(tables, issues)
        naming_score = self._score_naming(tables, issues)
        documentation_score = self._score_documentation(tables, issues)
        normalization_score = self._score_normalization(tables, issues)

        overall = (
            completeness_score * _WEIGHTS["completeness"]
            + relationships_score * _WEIGHTS["relationships"]
            + naming_score * _WEIGHTS["naming_convention"]
            + documentation_score * _WEIGHTS["documentation"]
            + normalization_score * _WEIGHTS["normalization"]
        )

        recommendations = self._generate_recommendations(
            completeness_score,
            relationships_score,
            naming_score,
            documentation_score,
            normalization_score,
            issues,
        )

        return {
            "overall_score": round(overall, 4),
            "completeness": round(completeness_score, 4),
            "relationships": round(relationships_score, 4),
            "naming_convention": round(naming_score, 4),
            "documentation": round(documentation_score, 4),
            "normalization": round(normalization_score, 4),
            "issues": issues,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Dimension assessors
    # ------------------------------------------------------------------

    @staticmethod
    def _score_completeness(
        tables: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> float:
        """% tables with description + business_role + domain;
        % columns with description + semantic_type."""
        if not tables:
            return 0.0

        table_ok = 0
        col_ok = 0
        col_total = 0

        for table in tables:
            tname = table["table_name"]
            has_desc = bool(table.get("description", "").strip())
            has_role = bool(table.get("business_role", "").strip())
            has_domain = bool(table.get("domain", "").strip())

            if has_desc and has_role and has_domain:
                table_ok += 1

            if not has_desc:
                issues.append(
                    {
                        "severity": "WARN",
                        "type": "missing_table_description",
                        "table": tname,
                        "column": None,
                        "message": f"Table '{tname}' has no business description.",
                    }
                )
            if not has_role:
                issues.append(
                    {
                        "severity": "WARN",
                        "type": "missing_business_role",
                        "table": tname,
                        "column": None,
                        "message": f"Table '{tname}' has no business_role assigned.",
                    }
                )
            if not has_domain:
                issues.append(
                    {
                        "severity": "WARN",
                        "type": "missing_domain",
                        "table": tname,
                        "column": None,
                        "message": f"Table '{tname}' has no domain assigned.",
                    }
                )

            for col in table.get("columns", []):
                cname = col["column_name"]
                col_total += 1
                has_col_desc = bool(col.get("description", "").strip())
                has_semantic = bool(col.get("semantic_type", "").strip())
                if has_col_desc and has_semantic:
                    col_ok += 1

                if not has_col_desc:
                    issues.append(
                        {
                            "severity": "INFO",
                            "type": "missing_column_description",
                            "table": tname,
                            "column": cname,
                            "message": (
                                f"Column '{tname}.{cname}' has no description."
                            ),
                        }
                    )
                if not has_semantic:
                    issues.append(
                        {
                            "severity": "INFO",
                            "type": "missing_semantic_type",
                            "table": tname,
                            "column": cname,
                            "message": (
                                f"Column '{tname}.{cname}' has no semantic_type."
                            ),
                        }
                    )

        table_score = table_ok / max(len(tables), 1)
        col_score = col_ok / max(col_total, 1)

        # 40 % table-level fields, 60 % column-level fields
        return 0.4 * table_score + 0.6 * col_score

    def _score_relationships(
        self,
        tables: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> float:
        """FK density, orphaned FK detection, FK naming consistency."""
        if not tables:
            return 0.0

        total_tables = len(tables)
        total_fks = len(self._relationships)

        if total_fks == 0:
            issues.append(
                {
                    "severity": "WARN",
                    "type": "no_relationships",
                    "table": None,
                    "column": None,
                    "message": "No foreign key relationships defined in the schema.",
                }
            )
            return 0.0

        # --- FK density  (FKs per table, ideal ~1.0-2.0) ---
        fk_density = total_fks / total_tables
        density_score = min(fk_density / 2.0, 1.0)

        # --- FK naming consistency ---
        naming_ok = 0
        for rel in self._relationships:
            fk_name = rel.get("name", "")
            if _FK_NAME_RE.match(fk_name):
                naming_ok += 1
            else:
                # Try to extract child table name heuristic:
                # convention: {table}_{column}_fkey
                parts = fk_name.rsplit("_", 2)
                child_table = parts[0] if len(parts) >= 3 else ""
                issues.append(
                    {
                        "severity": "WARN",
                        "type": "nonstandard_fk_name",
                        "table": child_table or None,
                        "column": None,
                        "message": (
                            f"FK '{fk_name}' does not follow the "
                            "{child_table}_{child_column}_fkey naming convention."
                        ),
                    }
                )

        naming_ratio = naming_ok / max(len(self._relationships), 1)

        # Combined: 50 % density, 50 % naming
        return 0.5 * density_score + 0.5 * naming_ratio

    @staticmethod
    def _score_naming(
        tables: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> float:
        """Snake_case compliance for all table and column names."""
        if not tables:
            return 0.0

        total = 0
        valid = 0

        for table in tables:
            tname = table["table_name"]
            total += 1
            if _SNAKE_CASE_RE.match(tname):
                valid += 1
            else:
                issues.append(
                    {
                        "severity": "WARN",
                        "type": "non_snake_case",
                        "table": tname,
                        "column": None,
                        "message": (
                            f"Table name '{tname}' does not follow "
                            "snake_case convention."
                        ),
                    }
                )

            for col in table.get("columns", []):
                cname = col["column_name"]
                total += 1
                if _SNAKE_CASE_RE.match(cname):
                    valid += 1
                else:
                    issues.append(
                        {
                            "severity": "WARN",
                            "type": "non_snake_case",
                            "table": tname,
                            "column": cname,
                            "message": (
                                f"Column name '{tname}.{cname}' does not follow "
                                "snake_case convention."
                            ),
                        }
                    )

        return valid / max(total, 1)

    def _score_documentation(
        self,
        tables: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> float:
        """Avg description length; detect boilerplate with LLM;
        entity relationship description coverage."""
        if not tables:
            return 0.0

        boilerplate_checks_remaining = _MAX_BOILERPLATE_CHECKS

        # --- Table descriptions ---
        table_desc_lengths: list[int] = []
        table_boilerplate = 0

        for table in tables:
            desc = table.get("description", "").strip()
            if desc:
                table_desc_lengths.append(len(desc))
                if len(desc) < 80 and boilerplate_checks_remaining > 0:
                    bp = _detect_boilerplate(desc, "table", table["table_name"])
                    boilerplate_checks_remaining -= 1
                    if bp.is_boilerplate:
                        table_boilerplate += 1
                        issues.append(
                            {
                                "severity": "WARN",
                                "type": "boilerplate_table_description",
                                "table": table["table_name"],
                                "column": None,
                                "message": (
                                    f"Table '{table['table_name']}' description "
                                    f"may be boilerplate: {bp.reason}"
                                ),
                            }
                        )

        avg_table_len = (
            (sum(table_desc_lengths) / max(len(table_desc_lengths), 1))
            if table_desc_lengths
            else 0.0
        )
        table_len_score = min(avg_table_len / 100.0, 1.0) if table_desc_lengths else 0.0
        if len(tables) > 0:
            table_len_score *= 1.0 - 0.3 * (table_boilerplate / max(len(tables), 1))

        # --- Column descriptions ---
        col_desc_lengths: list[int] = []
        col_boilerplate = 0

        for table in tables:
            tname = table["table_name"]
            for col in table.get("columns", []):
                desc = col.get("description", "").strip()
                if desc:
                    col_desc_lengths.append(len(desc))
                    if len(desc) < 60 and boilerplate_checks_remaining > 0:
                        bp = _detect_boilerplate(
                            desc, "column", f"{tname}.{col['column_name']}"
                        )
                        boilerplate_checks_remaining -= 1
                        if bp.is_boilerplate:
                            col_boilerplate += 1
                            issues.append(
                                {
                                    "severity": "INFO",
                                    "type": "boilerplate_column_description",
                                    "table": tname,
                                    "column": col["column_name"],
                                    "message": (
                                        f"Column '{tname}.{col['column_name']}' "
                                        f"description may be boilerplate: "
                                        f"{bp.reason}"
                                    ),
                                }
                            )

        avg_col_len = (
            (sum(col_desc_lengths) / max(len(col_desc_lengths), 1))
            if col_desc_lengths
            else 0.0
        )
        col_len_score = min(avg_col_len / 60.0, 1.0) if col_desc_lengths else 0.0
        total_cols = sum(len(t.get("columns", [])) for t in tables)
        if total_cols > 0:
            col_len_score *= 1.0 - 0.3 * (col_boilerplate / max(total_cols, 1))

        # --- Entity relationship coverage ---
        entity_rels = self._metadata.get("entity_relationships", [])
        er_with_meaning = sum(
            1 for er in entity_rels if bool(er.get("business_meaning", "").strip())
        )
        er_coverage = er_with_meaning / max(len(entity_rels), 1) if entity_rels else 1.0

        # Combined: 30 % table docs, 40 % column docs, 30 % ER coverage
        return 0.3 * table_len_score + 0.4 * col_len_score + 0.3 * er_coverage

    @staticmethod
    def _score_normalization(
        tables: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> float:
        """Duplicate column names across tables; wide tables; missing PKs;
        junction tables missing composite PK."""
        if not tables:
            return 0.0

        deductions = 0.0

        # --- 1. Duplicate column names (appearing in >5 tables) ---
        col_occurrences: dict[str, list[str]] = {}
        for table in tables:
            tname = table["table_name"]
            for col in table.get("columns", []):
                col_occurrences.setdefault(col["column_name"], []).append(tname)

        for cname, tlist in col_occurrences.items():
            if len(tlist) > 5:
                deductions += 0.1
                sample = tlist[:5]
                if len(tlist) > 5:
                    sample.append("...")
                issues.append(
                    {
                        "severity": "INFO",
                        "type": "redundant_column",
                        "table": None,
                        "column": cname,
                        "message": (
                            f"Column '{cname}' appears in {len(tlist)} tables "
                            f"({', '.join(sample)}). "
                            "This may indicate a missing normalization or "
                            "shared lookup table."
                        ),
                    }
                )

        # --- 2. Wide tables (>20 columns) ---
        for table in tables:
            tname = table["table_name"]
            col_count = len(table.get("columns", []))
            if col_count > 20:
                deductions += 0.2
                issues.append(
                    {
                        "severity": "WARN",
                        "type": "wide_table",
                        "table": tname,
                        "column": None,
                        "message": (
                            f"Table '{tname}' has {col_count} columns (>20). "
                            "Consider vertical partitioning or normalization."
                        ),
                    }
                )

        # --- 3. Tables without PK ---
        for table in tables:
            tname = table["table_name"]
            has_pk = any(col.get("is_primary_key") for col in table.get("columns", []))
            if not has_pk:
                deductions += 0.3
                issues.append(
                    {
                        "severity": "WARN",
                        "type": "missing_pk",
                        "table": tname,
                        "column": None,
                        "message": f"Table '{tname}' has no primary key column.",
                    }
                )

        # --- 4. Junction tables without composite PK ---
        for table in tables:
            tname = table["table_name"]
            if table.get("business_role") == "junction":
                pk_cols = [
                    col for col in table.get("columns", []) if col.get("is_primary_key")
                ]
                if len(pk_cols) < 2:
                    deductions += 0.2
                    issues.append(
                        {
                            "severity": "WARN",
                            "type": "junction_missing_composite_pk",
                            "table": tname,
                            "column": None,
                            "message": (
                                f"Junction table '{tname}' has fewer than 2 "
                                "primary key columns. Junction tables should "
                                "have a composite PK on the FK columns."
                            ),
                        }
                    )

        return max(1.0 - deductions, 0.0)

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        completeness: float,
        relationships: float,
        naming: float,
        documentation: float,
        normalization: float,
        issues: list[dict[str, Any]],
    ) -> list[str]:
        """Generate actionable recommendations using the LLM.

        Falls back to heuristic recommendations if the LLM call fails.
        """
        sample_issues_text = ""
        if issues:
            sample_issues_text = "Sample issues:\n"
            for issue in issues[:5]:
                sample_issues_text += (
                    f"- [{issue.get('severity', 'INFO')}] {issue.get('message', '')}\n"
                )

        prompt = _RECOMMENDATION_PROMPT.format(
            completeness=completeness,
            relationships=relationships,
            naming=naming,
            documentation=documentation,
            normalization=normalization,
            issue_count=len(issues),
            sample_issues=sample_issues_text,
        )

        try:
            llm = get_llm()
            structured = llm.with_structured_output(
                _RecommendationsResult, method="function_calling"
            )
            result = structured.invoke(
                [
                    {"role": "user", "content": prompt},
                ]
            )
            recs: list[str] = []
            if isinstance(result, dict):
                recs = result.get("recommendations", [])
            elif isinstance(result, _RecommendationsResult):
                recs = result.recommendations
            # Filter empty strings — model sometimes fills slots with blanks
            recs = [r for r in recs if r and r.strip()]
            if recs:
                return recs
            return self._fallback_recommendations(
                completeness, relationships, naming, documentation, normalization,
            )
        except Exception:
            logger.warning("Recommendation generation failed — using fallback")
            return self._fallback_recommendations(
                completeness,
                relationships,
                naming,
                documentation,
                normalization,
            )

    @staticmethod
    def _fallback_recommendations(
        completeness: float,
        relationships: float,
        naming: float,
        documentation: float,
        normalization: float,
    ) -> list[str]:
        """Heuristic fallback when the LLM is unavailable."""
        recs: list[str] = []

        if completeness < 0.7:
            recs.append(
                "Add descriptions, business_role, and domain to all tables; "
                "add descriptions and semantic_type to all columns."
            )
        if relationships < 0.7:
            recs.append(
                "Review foreign key relationships: ensure FK naming follows "
                "the {child_table}_{child_column}_fkey convention and all "
                "relationships are properly defined."
            )
        if naming < 0.7:
            recs.append(
                "Standardize naming conventions: all table and column names "
                "should use snake_case."
            )
        if documentation < 0.7:
            recs.append(
                "Improve documentation quality: write longer, more specific "
                "descriptions for tables and columns. Avoid boilerplate text."
            )
        if normalization < 0.7:
            recs.append(
                "Review schema normalization: add primary keys to tables "
                "missing them, use composite PKs in junction tables, "
                "and consider splitting wide tables."
            )
        if not recs:
            recs.append("Schema quality is good. Continue monitoring for regressions.")
        return recs
