"""Consolidated enrichment agent — multi-pass LLM enrichment within a single node.

Splits the enrichment into 3 focused passes, each a smaller LLM call,
all within one LangGraph node:

1. **Table-level** — table descriptions, business roles, business domains
2. **Column-level** — column descriptions, semantic types (batched by table groups)
3. **Schema-level** — entities, entity relationships, use cases, sample queries

RuleEngine runs **before** the LLM calls so that fast PII/pattern-based
classifications are handled without consuming LLM tokens.

Uses **plain LLM invoke** (no with_structured_output) since many local/cloud
models behind Ollama do not reliably support structured JSON output mode.
The system prompt explicitly instructs the model to return valid JSON.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from etl_enrichment_pipeline.agents.pattern_detection_agent import (
    pattern_detection_node,
)
from etl_enrichment_pipeline.agents.rule_engine import RuleEngine
from etl_enrichment_pipeline.agents.validation_agent import validation_node
from etl_enrichment_pipeline.core.llm import get_llm
from etl_enrichment_pipeline.models.canonical import CanonicalSchema
from etl_enrichment_pipeline.models.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable batch size (env COLUMN_BATCH_SIZE, default 10)
# ---------------------------------------------------------------------------
_COLUMN_BATCH_SIZE = int(os.getenv("COLUMN_BATCH_SIZE", "10"))


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(\{.*?\})\n?\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)


def _extract_json(text: str) -> str | None:
    """Extract the first JSON object from model output.

    Tries (in order):
    1. A fenced code block (```json ... ``` or ``` ... ```)
    2. The first top-level ``{...}`` object in the text.
    3. The entire text as a last resort.
    """
    # Try fenced code blocks first
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return m.group(1)

    # Try first top-level { ... } object
    m = _JSON_OBJECT_RE.search(text)
    if m:
        candidate = m.group(1)
        # Basic check: ensure it starts and ends with braces and is parseable
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Last resort: try the whole text
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Structured LLM call — plain invoke + manual JSON parsing
# ---------------------------------------------------------------------------


def _call_json_llm(
    system_prompt: str,
    user_prompt: str,
    description: str = "",
) -> dict[str, Any] | None:
    """Invoke the LLM with a plain prompt and parse the response as JSON.

    Returns a parsed dict, or ``None`` on failure.
    """
    try:
        llm = get_llm()
        response = llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        raw = response.content
        if not raw:
            logger.warning(
                "[consolidated] LLM returned empty content — %s", description
            )
            return None

        json_str = _extract_json(str(raw))
        if json_str is None:
            logger.warning(
                "[consolidated] LLM response had no parseable JSON — %s. "
                "Response preview: %.200s",
                description,
                str(raw).replace("\n", " ")[:200],
            )
            return None

        parsed = json.loads(json_str)
        return parsed

    except Exception:
        logger.exception(
            "[consolidated] LLM call failed — %s",
            description,
        )
        return None


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_JSON_ONLY_INSTRUCTION = """\
IMPORTANT: Respond with ONLY a valid JSON object. No markdown, no code fences,
no explanation, no text before or after the JSON. The JSON must be parseable
by Python's json.loads()."""

_TABLE_SYSTEM_PROMPT = f"""\
You are a senior database schema analyst.  Your task is to analyse the
database tables below and produce **table-level** enrichment only.

{_JSON_ONLY_INSTRUCTION}

Produce a JSON object with these keys:
- "table_descriptions": {{"table_name": "concise business description (1-2 sentences)"}}
- "business_roles": {{"table_name": "one of: master_data, transactional, reference, audit, staging, reporting, fact, dimension, junction"}}
- "domains": {{"table_name": "business domain label (e.g. Flight Operations, Baggage Handling, Human Resources, Equipment Management, Reference Data)"}}

Cover EVERY table. Use sensible defaults if unsure.
"""

_COLUMN_SYSTEM_PROMPT = f"""\
You are a senior database schema analyst.  Your task is to analyse the
given tables and produce **column-level** enrichment only.

{_JSON_ONLY_INSTRUCTION}

Produce a JSON object with these keys:
- "column_descriptions": {{"table_name": {{"column_name": "short description (5-15 words)"}}}}
- "semantic_types": {{"table_name.column_name": "SEMANTIC_TYPE_LABEL"}}

Semantic type labels: ID, NAME, EMAIL, PHONE, FIRST_NAME, LAST_NAME,
DATE_OF_BIRTH, COUNTRY, CITY, POSTAL_CODE, STATUS, TIMESTAMP, DATE, TIME,
PRICE, AMOUNT, QUANTITY, PERCENTAGE, CODE, DESCRIPTION, COMMENT, GOVT_ID,
BOOLEAN_FLAG, URL, PHOTO, AGE, SEMANTIC_TYPE_UNKNOWN.

Cover EVERY column for EVERY table in this batch.
"""

_SCHEMA_SYSTEM_PROMPT = f"""\
You are a senior database schema analyst.  Given the list of tables and
their foreign-key relationships, produce schema-level enrichment.

{_JSON_ONLY_INSTRUCTION}

Produce a JSON object with these keys:
- "entities": ["PascalCase entity names derived from tables. Merge related tables (e.g. baggage, baggage_scan, lost_baggage → Baggage). Do not create entities for pure junction/history/audit tables."]
- "entity_relationships": [{{"entity": "source entity", "related_entities": "comma-separated related entities", "business_meaning": "description with cardinality"}}]
- "use_cases": [{{"name": "short name", "description": "1-2 sentence description", "involved_tables": ["table1", "table2"]}}] (3-5 use cases)
- "sample_queries": [{{"question": "natural language question", "sql": "SQL statement", "category": "Lookup|Reporting|Analytics|Aggregation|Relationship"}}] (3-5 queries)
"""


def _prompt_tables_info(schema: CanonicalSchema) -> str:
    """Format a compact table listing for the LLM prompt."""
    lines: list[str] = []
    for tbl in schema.tables:
        cols = ", ".join(
            f"{c.column_name} ({c.data_type}){' PK' if c.is_primary_key else ''}"
            for c in tbl.columns
        )
        lines.append(f"  - {tbl.table_name}: [{cols}]")
    return "\n".join(lines) if lines else "(no tables)"


def _prompt_relationships_info(schema: CanonicalSchema) -> str:
    """Format relationships for the LLM prompt."""
    lines: list[str] = []
    for rel in schema.relationships:
        lines.append(
            f"  - {rel.from_table}.{rel.from_column} "
            f"\u2192 {rel.to_table}.{rel.to_column}"
        )
    return "\n".join(lines) if lines else "(no relationships)"


def _db_ctx(schema: CanonicalSchema) -> str:
    """Short database context for prompts."""
    db = schema.database_info
    ctx = f"Database: {db.name or '(unknown)'} | {db.vendor or '(unknown)'}"
    if db.version:
        ctx += f" | Version: {db.version}"
    return ctx


# ---------------------------------------------------------------------------
# Node function — single enrichment node with multi-pass LLM calls
# ---------------------------------------------------------------------------


def consolidated_enrichment_node(state: PipelineState) -> PipelineState:
    """Single enrichment node: multi-pass LLM + fast rule-based passes.

    PipelineState fields produced
    -----------------------------
    - ``descriptions`` — from Pass 1 (table) + Pass 2 (column)
    - ``business_roles`` — from Pass 1
    - ``domains`` — from Pass 1
    - ``semantic_types`` — from Pass 2 (column) + RuleEngine overrides
    - ``entities`` — from Pass 3
    - ``entity_relationships`` — physical (from schema) + entity-level (from Pass 3)
    - ``use_cases`` — from Pass 3
    - ``sample_queries`` — from Pass 3
    - ``patterns`` — from rule-based pattern_detection (fast)
    - ``validation_report`` — from rule-based validation (fast)
    """
    # --- Early exit when there is no schema ----------------------------------
    if state.canonical_schema is None:
        logger.warning("canonical_schema is None — skipping enrichment")
        _set_empty(state)
        return state

    schema = state.canonical_schema
    if not schema.tables:
        logger.warning("canonical_schema has no tables — skipping enrichment")
        _set_empty(state)
        return state

    logger.info(
        "[consolidated] ▶  enrichment start — %d tables, %d columns, %d relationships",
        len(schema.tables),
        sum(len(t.columns) for t in schema.tables),
        len(schema.relationships),
    )

    # ==================================================================
    # Step 0: RuleEngine — fast PII/pattern-based semantic types
    # (runs before LLM so we can skip columns RuleEngine already knows)
    # ==================================================================
    engine = RuleEngine()
    rule_semantic_types: dict[str, str] = {}
    for table in schema.tables:
        for column in table.columns:
            key = f"{table.table_name}.{column.column_name}"
            rule_result = engine.classify(column.column_name, column.data_type)
            if rule_result.get("classification"):
                rule_semantic_types[key] = rule_result["classification"]

    logger.info(
        "[consolidated] ✓  RuleEngine — %d columns pre-classified",
        len(rule_semantic_types),
    )

    # ==================================================================
    # Pass 1: Table-level — descriptions, roles, domains
    # ==================================================================
    tables_info = _prompt_tables_info(schema)
    db_ctx_str = _db_ctx(schema)

    logger.info(
        "[consolidated] Pass 1/3 ▶  table-level enrichment (%d tables)",
        len(schema.tables),
    )

    pass1_data = _call_json_llm(
        _TABLE_SYSTEM_PROMPT,
        f"""{db_ctx_str}

Tables and columns:
{tables_info}

Produce table descriptions, business roles, and business domains for EVERY table listed above.""",
        description="Pass 1 (table-level)",
    )

    if pass1_data is not None:
        state.descriptions = {
            "table_descriptions": pass1_data.get("table_descriptions", {}),
            "column_descriptions": {},  # filled in Pass 2
        }
        state.business_roles = pass1_data.get("business_roles", {})
        state.domains = pass1_data.get("domains", {})
        logger.info(
            "[consolidated] Pass 1/3 ✓  %d tables described, %d roles, %d domains",
            len(pass1_data.get("table_descriptions", {})),
            len(pass1_data.get("business_roles", {})),
            len(pass1_data.get("domains", {})),
        )
    else:
        logger.warning(
            "[consolidated] Pass 1/3 ✗  failed — table enrichment will be empty"
        )
        state.descriptions = {"table_descriptions": {}, "column_descriptions": {}}
        state.business_roles = {}
        state.domains = {}

    # ==================================================================
    # Pass 2: Column-level — descriptions, semantic types (batched)
    # ==================================================================
    all_column_descriptions: dict[str, dict[str, str]] = {}
    all_semantic_types: dict[str, str] = dict(rule_semantic_types)

    # Group tables into batches
    table_batches = [
        schema.tables[i : i + _COLUMN_BATCH_SIZE]
        for i in range(0, len(schema.tables), _COLUMN_BATCH_SIZE)
    ]

    logger.info(
        "[consolidated] Pass 2/3 ▶  column-level enrichment "
        "(%d columns across %d batches of ~%d tables)",
        sum(len(t.columns) for t in schema.tables),
        len(table_batches),
        _COLUMN_BATCH_SIZE,
    )

    for batch_idx, batch in enumerate(table_batches):
        batch_tables_info_lines: list[str] = []
        for tbl in batch:
            cols = ", ".join(
                f"{c.column_name} ({c.data_type}){' PK' if c.is_primary_key else ''}"
                for c in tbl.columns
            )
            batch_tables_info_lines.append(f"  - {tbl.table_name}: [{cols}]")
        batch_info = "\n".join(batch_tables_info_lines)
        batch_column_count = sum(len(t.columns) for t in batch)

        logger.info(
            "[consolidated] Pass 2/3 — batch %d/%d (%d tables, %d columns)",
            batch_idx + 1,
            len(table_batches),
            len(batch),
            batch_column_count,
        )

        pass2_data = _call_json_llm(
            _COLUMN_SYSTEM_PROMPT,
            f"""{db_ctx_str}

Tables (batch {batch_idx + 1} of {len(table_batches)}):
{batch_info}

Produce column descriptions and semantic types for EVERY column in the tables above.""",
            description=f"Pass 2 (column-level, batch {batch_idx + 1}/{len(table_batches)})",
        )

        if pass2_data is not None:
            # Merge column descriptions
            for tbl_name, col_descs in (
                pass2_data.get("column_descriptions", {}) or {}
            ).items():
                if tbl_name not in all_column_descriptions:
                    all_column_descriptions[tbl_name] = {}
                if isinstance(col_descs, dict):
                    all_column_descriptions[tbl_name].update(col_descs)

            # Merge semantic types (RuleEngine classifications take precedence)
            for key, stype in (pass2_data.get("semantic_types", {}) or {}).items():
                if key not in rule_semantic_types:
                    all_semantic_types[key] = stype

            logger.info(
                "[consolidated] Pass 2/3 ✓  batch %d — %d columns processed",
                batch_idx + 1,
                batch_column_count,
            )
        else:
            logger.warning(
                "[consolidated] Pass 2/3 ✗  batch %d failed"
                " — column enrichment may be incomplete",
                batch_idx + 1,
            )

    # Update state with column-level results
    if (
        isinstance(state.descriptions, dict)
        and "table_descriptions" in state.descriptions
    ):
        state.descriptions["column_descriptions"] = all_column_descriptions
    else:
        state.descriptions = {
            "table_descriptions": (
                state.descriptions.get("table_descriptions", {})
                if isinstance(state.descriptions, dict)
                else {}
            ),
            "column_descriptions": all_column_descriptions,
        }
    state.semantic_types = all_semantic_types

    logger.info(
        "[consolidated] Pass 2/3 ✓  total — %d table(s) with column descriptions, %d semantic types",
        len(all_column_descriptions),
        len(all_semantic_types),
    )

    # ==================================================================
    # Pass 3: Schema-level — entities, relationships, use cases, queries
    #
    # Uses a COMPACT format (table names only, no column details) so the
    # prompt is small enough for the model to handle quickly.
    # ==================================================================
    relationships_info = _prompt_relationships_info(schema)

    # Compact tables info: just table names (no columns) to keep prompt tiny
    compact_tables = "\n".join(f"  - {t.table_name}" for t in schema.tables)

    logger.info("[consolidated] Pass 3/3 ▶  schema-level enrichment (compact schema)")

    pass3_data = _call_json_llm(
        _SCHEMA_SYSTEM_PROMPT,
        f"""{db_ctx_str}

Tables:
{compact_tables}

Foreign-key relationships:
{relationships_info}

Produce business entities, entity relationships, use cases, and sample queries.""",
        description="Pass 3 (schema-level)",
    )

    if pass3_data is not None:
        # Entities
        entities: list[str] = []
        raw_entities = pass3_data.get("entities", []) or []
        if isinstance(raw_entities, list):
            seen: set[str] = set()
            for e in raw_entities:
                if isinstance(e, str) and e not in seen:
                    seen.add(e)
                    entities.append(e)
        state.entities = entities if entities else None

        # Entity relationships
        entity_rels: list[dict[str, str]] = []
        raw_rels = pass3_data.get("entity_relationships", []) or []
        if isinstance(raw_rels, list):
            for item in raw_rels:
                if isinstance(item, dict):
                    entity_rels.append(
                        {
                            "entity": item.get("entity", ""),
                            "related_entities": item.get("related_entities", ""),
                            "business_meaning": item.get("business_meaning", ""),
                        }
                    )

        # Physical relationships (from canonical schema)
        physical: list[dict[str, str]] = []
        for rel in schema.relationships:
            physical.append(
                {
                    "from_table": rel.from_table,
                    "to_table": rel.to_table,
                    "from_column": rel.from_column,
                    "to_column": rel.to_column,
                }
            )

        state.entity_relationships = {
            "physical_relationships": physical,
            "entity_relationships": entity_rels,
        }

        # Use cases
        use_cases: list[dict[str, str]] = []
        raw_ucs = pass3_data.get("use_cases", []) or []
        if isinstance(raw_ucs, list):
            for uc in raw_ucs:
                if isinstance(uc, dict):
                    involved = uc.get("involved_tables", []) or []
                    if isinstance(involved, list):
                        involved_str = ", ".join(str(t) for t in involved)
                    else:
                        involved_str = str(involved)
                    use_cases.append(
                        {
                            "name": uc.get("name", ""),
                            "description": uc.get("description", ""),
                            "involved_tables": involved_str,
                        }
                    )
        state.use_cases = use_cases

        # Sample queries
        sample_queries: list[dict[str, str]] = []
        raw_qs = pass3_data.get("sample_queries", []) or []
        if isinstance(raw_qs, list):
            for q in raw_qs:
                if isinstance(q, dict):
                    sample_queries.append(
                        {
                            "question": q.get("question", ""),
                            "sql": q.get("sql", ""),
                            "category": q.get("category", ""),
                        }
                    )
        state.sample_queries = sample_queries

        logger.info(
            "[consolidated] Pass 3/3 ✓  %d entities, %d relationships, "
            "%d use cases, %d queries",
            len(entities),
            len(entity_rels),
            len(use_cases),
            len(sample_queries),
        )
    else:
        logger.warning(
            "[consolidated] Pass 3/3 ✗  failed — schema-level enrichment will be empty"
        )
        state.entities = None
        state.entity_relationships = None
        state.use_cases = []
        state.sample_queries = []

    # ==================================================================
    # Fast rule-based passes (pattern_detection, validation)
    # ==================================================================
    _run_fast_passes(state)

    logger.info("[consolidated] ✓  enrichment complete — all passes finished")
    return state


def _set_empty(state: PipelineState) -> None:
    """Set all enrichment fields to empty/None defaults."""
    state.descriptions = {"table_descriptions": {}, "column_descriptions": {}}
    state.business_roles = {}
    state.domains = {}
    state.semantic_types = {}
    state.entities = None
    state.entity_relationships = None
    state.use_cases = []
    state.sample_queries = []
    state.patterns = []
    state.validation_report = None


def _run_fast_passes(state: PipelineState) -> None:
    """Run fast rule-based passes that don't need LLM calls."""
    pattern_detection_node(state)
    validation_node(state)

    logger.info(
        "[consolidated] ✓  Fast passes complete — %d patterns, validation: %s",
        len(state.patterns or []),
        state.validation_report.get("status", "N/A")
        if isinstance(state.validation_report, dict)
        else "N/A",
    )


__all__ = ["consolidated_enrichment_node"]
