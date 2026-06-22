"""Semantic type agent — detects business meaning of columns
(EMAIL, PHONE, PII, etc.)."""

from __future__ import annotations

import logging
from typing import cast

from etl_enrichment_pipeline.agents.rule_engine import RuleEngine
from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.agent_outputs import SemanticTypeOutput
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Semantic type labels the LLM is constrained to — kept in sync with the
# YAML rules under etl_enrichment_pipeline/rules/.
# ---------------------------------------------------------------------------
_SEMANTIC_TYPE_LABELS = """
EMAIL, PHONE, FIRST_NAME, LAST_NAME, FULL_NAME
DATE_OF_BIRTH, COUNTRY, CITY, STATE, POSTAL_CODE
STATUS, TIMESTAMP, DATE, TIME
PRICE, AMOUNT, QUANTITY, PERCENTAGE
ID, CODE, NAME, DESCRIPTION, COMMENT
GOVT_ID (for SSN, PAN, Aadhaar, Passport)
BOOLEAN_FLAG, URL, PHOTO, AGE
SEMANTIC_TYPE_UNKNOWN (for truly ambiguous columns)
""".strip()

_SYSTEM_PROMPT = (
    "You are a database column semantic-type classifier.\n"
    "Given a column name and its data type, infer the business meaning "
    "(semantic type) of the column.\n"
    "\n"
    "Use only the following semantic type labels:\n"
    "{type_labels}\n"
    "\n"
    "Return a mapping of \"table.column\" identifiers to their semantic type labels."
)

_USER_PROMPT = (
    "Classify the semantic type for each of the following columns "
    "that were not matched by our rule-based classifier:\n"
    "\n"
    "{unclassified_columns}\n"
    "\n"
    "Return the semantic type for every column listed above."
)


def _format_unclassified(
    unclassified: list[tuple[str, str, str]],
) -> str:
    """Format unclassified columns into a readable string for the LLM prompt."""
    lines: list[str] = []
    for table_name, column_name, data_type in unclassified:
        lines.append(f"  - {table_name}.{column_name} ({data_type})")
    if not lines:
        return "(no unclassified columns)"
    return "\n".join(lines)


def semantic_type_node(state: PipelineState) -> PipelineState:
    """Detect business meaning / semantic type of columns (EMAIL, PHONE, PII, etc.).

    Two-pass approach:
      1. Rule-based classification via ``RuleEngine`` (pattern matching).
      2. LLM-based classification
         (``nvidia/nemotron-3-super-120b-a12b:free``)
         for columns the rule engine could not classify.

    Gracefully degrades when:
      - ``state.canonical_schema`` is ``None``
      - The ``OPENROUTER_API_KEY`` environment variable is not set
      - The LLM call fails for any other reason

    Args:
        state: The current pipeline state containing the canonical schema.

    Returns:
        Updated pipeline state with ``semantic_types`` populated.
    """
    # --- Early exit when there is no schema to analyse -----------------------
    if state.canonical_schema is None:
        logger.warning("canonical_schema is None — skipping semantic type detection")
        state.semantic_types = {}
        return state

    engine = RuleEngine()
    result: dict[str, str] = {}
    unclassified: list[tuple[str, str, str]] = []

    # --- Pass 1: Rule-based classification -----------------------------------
    for table in state.canonical_schema.tables:
        for column in table.columns:
            key = f"{table.table_name}.{column.column_name}"
            rule_result = engine.classify(column.column_name, column.data_type)
            if rule_result.get("classification"):
                result[key] = rule_result["classification"]
                logger.debug(
                    "Rule matched: %s -> %s", key, rule_result["classification"]
                )
            else:
                unclassified.append(
                    (table.table_name, column.column_name, column.data_type)
                )

    # --- Pass 2: LLM for remaining unclassified columns -----------------------
    if unclassified:
        try:
            llm = get_llm()
            structured_llm = llm.with_structured_output(SemanticTypeOutput)

            system_prompt = _SYSTEM_PROMPT.format(type_labels=_SEMANTIC_TYPE_LABELS)
            user_prompt = _USER_PROMPT.format(
                unclassified_columns=_format_unclassified(unclassified)
            )

            llm_result = cast("SemanticTypeOutput", structured_llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]))

            result.update(llm_result.semantic_types)
            logger.info(
                "LLM classified %d column(s); %d total semantic types",
                len(llm_result.semantic_types),
                len(result),
            )

        except Exception:
            logger.exception(
                "Semantic type LLM classification failed — "
                "using only rule-based results (%d columns classified)",
                len(result),
            )

    state.semantic_types = result
    logger.info(
        "Semantic types detected for %d column(s)", len(result),
    )
    return state
