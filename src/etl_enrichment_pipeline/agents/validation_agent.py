"""Validation agent — validates extraction quality,
enrichment completeness, and relationship integrity.

This agent performs **lenient** validation: it collects issues (WARN, INFO)
but never blocks the pipeline or returns FAIL status.
"""

from __future__ import annotations

from etl_enrichment_pipeline.agents.rule_engine import RuleEngine
from etl_enrichment_pipeline.models.canonical import CanonicalSchema
from etl_enrichment_pipeline.models.pipeline_state import PipelineState


def _get_table_names(schema: CanonicalSchema) -> set[str]:
    """Return the set of all table names in the canonical schema."""
    return {t.table_name for t in schema.tables}


def validation_node(state: PipelineState) -> PipelineState:
    """Validate extraction quality, enrichment completeness, and relationship integrity.

    Performs six lenient checks — issues are collected but the pipeline is
    *never* blocked. Results are stored in ``state.validation_report`` as::

        {
            "status": "PASS" | "WARN",
            "issues": [
                {
                    "severity": "WARN" | "INFO",
                    "type": "missing_pk" | "broken_fk" | "empty_table"
                           | "missing_description" | "missing_semantic_type"
                           | "low_confidence",
                    "table": str | None,
                    "column": str | None,
                    "message": str,
                },
                ...
            ]
        }

    If ``state.canonical_schema`` is ``None``, a single WARN is emitted and
    the agent returns immediately.
    """
    issues: list[dict[str, str | None]] = []

    # ------------------------------------------------------------------
    # Early exit when there is nothing to validate
    # ------------------------------------------------------------------
    if state.canonical_schema is None:
        issues.append(
            {
                "severity": "WARN",
                "type": "no_schema",
                "table": None,
                "column": None,
                "message": "canonical_schema is None — no schema to validate",
            }
        )
        state.validation_report = {
            "status": "WARN",
            "issues": issues,
        }
        return state

    schema = state.canonical_schema
    table_names = _get_table_names(schema)

    # ------------------------------------------------------------------
    # 1. Missing PKs — tables without a primary key column
    # ------------------------------------------------------------------
    for table in schema.tables:
        has_pk = any(col.is_primary_key for col in table.columns)
        if not has_pk:
            issues.append(
                {
                    "severity": "WARN",
                    "type": "missing_pk",
                    "table": table.table_name,
                    "column": None,
                    "message": (
                        f"Table '{table.table_name}' has no primary key column. "
                        "Consider adding a PRIMARY KEY constraint."
                    ),
                }
            )

    # ------------------------------------------------------------------
    # 2. Broken FK references — FK pointing to non-existent parent table
    # ------------------------------------------------------------------
    for rel in schema.relationships:
        if rel.to_table not in table_names:
            issues.append(
                {
                    "severity": "WARN",
                    "type": "broken_fk",
                    "table": rel.from_table,
                    "column": rel.from_column,
                    "message": (
                        f"Foreign key {rel.from_table}.{rel.from_column} "
                        f"references table '{rel.to_table}', which does not "
                        "exist in the schema."
                    ),
                }
            )

    # ------------------------------------------------------------------
    # 3. Empty tables — tables with zero columns
    # ------------------------------------------------------------------
    for table in schema.tables:
        if not table.columns:
            issues.append(
                {
                    "severity": "WARN",
                    "type": "empty_table",
                    "table": table.table_name,
                    "column": None,
                    "message": (f"Table '{table.table_name}' has no columns defined."),
                }
            )

    # ------------------------------------------------------------------
    # 4. Missing descriptions — tables/columns without descriptions
    # ------------------------------------------------------------------
    # The descriptions field is populated by the description agent as a dict
    # with keys "table_descriptions" and "column_descriptions".
    table_descriptions: dict[str, str] = {}
    column_descriptions: dict[str, dict[str, str]] = {}
    if isinstance(state.descriptions, dict):
        raw_td = state.descriptions.get("table_descriptions")
        if isinstance(raw_td, dict):
            table_descriptions = raw_td
        raw_cd = state.descriptions.get("column_descriptions")
        if isinstance(raw_cd, dict):
            column_descriptions = raw_cd

    for table in schema.tables:
        # Check table-level description
        if table.table_name not in table_descriptions:
            issues.append(
                {
                    "severity": "INFO",
                    "type": "missing_description",
                    "table": table.table_name,
                    "column": None,
                    "message": (
                        f"Table '{table.table_name}' has no business description."
                    ),
                }
            )

        # Check column-level descriptions
        col_descs = column_descriptions.get(table.table_name, {})
        for col in table.columns:
            if col.column_name not in col_descs:
                issues.append(
                    {
                        "severity": "INFO",
                        "type": "missing_description",
                        "table": table.table_name,
                        "column": col.column_name,
                        "message": (
                            f"Column '{table.table_name}.{col.column_name}' "
                            "has no business description."
                        ),
                    }
                )

    # ------------------------------------------------------------------
    # 5. Missing semantic types — columns without semantic type labels
    # ------------------------------------------------------------------
    for table in schema.tables:
        for col in table.columns:
            key = f"{table.table_name}.{col.column_name}"
            if not state.semantic_types or key not in state.semantic_types:
                issues.append(
                    {
                        "severity": "INFO",
                        "type": "missing_semantic_type",
                        "table": table.table_name,
                        "column": col.column_name,
                        "message": (
                            f"Column '{table.table_name}.{col.column_name}' "
                            "has no semantic type label."
                        ),
                    }
                )

    # ------------------------------------------------------------------
    # 6. Low-confidence outputs — RuleEngine confidence below 0.5
    # ------------------------------------------------------------------
    try:
        engine = RuleEngine()
        for table in schema.tables:
            for col in table.columns:
                result = engine.classify(col.column_name, col.data_type)
                confidence = result.get("confidence", 0.0)
                if 0.0 < confidence < 0.5:
                    issues.append(
                        {
                            "severity": "INFO",
                            "type": "low_confidence",
                            "table": table.table_name,
                            "column": col.column_name,
                            "message": (
                                f"RuleEngine confidence for "
                                f"'{table.table_name}.{col.column_name}' "
                                f"is {confidence:.2f} (below 0.5)."
                            ),
                        }
                    )
    except Exception:
        # If RuleEngine fails (e.g. missing YAML files), skip this check
        # without blocking the pipeline
        pass

    # ------------------------------------------------------------------
    # Determine overall status: PASS if no WARN issues, WARN otherwise
    # ------------------------------------------------------------------
    has_warn = any(issue.get("severity") == "WARN" for issue in issues)

    state.validation_report = {
        "status": "WARN" if has_warn else "PASS",
        "issues": issues,
    }

    return state
