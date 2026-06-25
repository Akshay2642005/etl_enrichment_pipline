"""Consolidated enrichment agent — single LLM call for all enrichment.

Replaces 8 separate LLM-based agents with one comprehensive LLM call,
then runs fast rule-based passes (RuleEngine, pattern_detection, validation).
"""

from __future__ import annotations

import logging
from typing import cast

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
# Structured-output schema for the single LLM call
# ---------------------------------------------------------------------------


class UseCaseItem(BaseModel):
    """A single business use case."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Short business name for the use case")
    description: str = Field(
        default="", description="Brief description in 1-2 sentences"
    )
    involved_tables: list[str] = Field(
        default_factory=list,
        description="Table names that participate in this use case",
    )


class QueryItem(BaseModel):
    """A single sample business query."""

    model_config = ConfigDict(extra="ignore")

    question: str = Field(
        default="", description="Natural-language question the query answers"
    )
    sql: str = Field(default="", description="SQL query that answers the question")
    category: str = Field(
        default="",
        description="One of: Lookup, Reporting, Analytics, Aggregation, Relationship",
    )


class EntityRelationshipItem(BaseModel):
    """A single entity-level relationship."""

    model_config = ConfigDict(extra="ignore")

    entity: str = Field(
        default="", description="Source business entity name (PascalCase)"
    )
    related_entities: str = Field(
        default="",
        description="Comma-separated list of related PascalCase entity names",
    )
    business_meaning: str = Field(
        default="",
        description="Natural-language description including cardinality",
    )


class ConsolidatedEnrichmentOutput(BaseModel):
    """Everything produced by the single LLM enrichment call.

    All fields are optional so the model can gracefully omit sections
    it is unsure about.
    """

    model_config = ConfigDict(extra="ignore")

    table_descriptions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps each table_name to a concise business description (1-2 sentences)"
        ),
    )
    column_descriptions: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description=(
            "Maps each table_name to a dict of column_name -> short description. "
            "Every column for every table should be included."
        ),
    )
    business_roles: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps each table_name to its business role "
            "(master_data, transactional, reference, audit, staging, "
            "reporting, fact, dimension, junction)"
        ),
    )
    domains: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps each table_name to its business domain label "
            "(e.g. Flight Operations, Baggage Handling, Human Resources, "
            "Equipment Management, Reference Data)"
        ),
    )
    semantic_types: dict[str, str] = Field(
        default_factory=dict,
        description=(
            'Maps "table.column" identifiers to semantic type labels '
            "(e.g. EMAIL, PHONE, FIRST_NAME, DATE_OF_BIRTH, "
            "PRICE, AMOUNT, STATUS, ID, NAME, GOVT_ID, SEMANTIC_TYPE_UNKNOWN)"
        ),
    )
    entities: list[str] = Field(
        default_factory=list,
        description=(
            "Unique list of PascalCase business entity names derived "
            "from the schema tables (e.g. Employee, Department, Attendance)"
        ),
    )
    entity_relationships: list[EntityRelationshipItem] = Field(
        default_factory=list,
        description=(
            "Entity-level relationships inferred from foreign-key constraints, "
            "with business meaning descriptions"
        ),
    )
    use_cases: list[UseCaseItem] = Field(
        default_factory=list,
        description="3-5 business use cases derived from the schema",
    )
    sample_queries: list[QueryItem] = Field(
        default_factory=list,
        description="3-5 sample business queries across different categories",
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a senior database schema analyst. Given the complete database schema
below, perform **all** of the following enrichment tasks in a single pass:

1. **Table descriptions** — concise business descriptions (1-2 sentences each).
2. **Column descriptions** — short phrase describing each column's business attribute.
3. **Business roles** — classify each table as one of:
   - master_data, transactional, reference, audit, staging, reporting,
     fact, dimension, junction
4. **Business domains** — classify each table into its most specific business domain
   (e.g. Flight Operations, Baggage Handling, Human Resources, Equipment Management,
   Airport Infrastructure, Ground Operations, Turnaround Management, Reference Data).
5. **Semantic types** — classify each column into a semantic type label
   (e.g. EMAIL, PHONE, FIRST_NAME, LAST_NAME, DATE_OF_BIRTH, COUNTRY, CITY,
   POSTAL_CODE, STATUS, TIMESTAMP, DATE, TIME, PRICE, AMOUNT, QUANTITY,
   PERCENTAGE, ID, CODE, NAME, DESCRIPTION, COMMENT, GOVT_ID, BOOLEAN_FLAG,
   URL, PHOTO, AGE, SEMANTIC_TYPE_UNKNOWN).
6. **Business entities** — convert table names into singular PascalCase business
   entities. Merge related tables (e.g. baggage, baggage_scan, lost_baggage
   all become Baggage). Do not create entities for junction/history/audit tables.
7. **Entity relationships** — for each source entity that participates in FK
   relationships, describe how it relates to other entities with cardinality
   (e.g. "An employee belongs to one department").
8. **Use cases** — 3-5 business use cases showing how tables work together to
   support real business processes.
9. **Sample queries** — 3-5 realistic SQL queries (Lookup, Reporting, Analytics,
   Aggregation, Relationship categories) with natural-language questions.

Be thorough. Cover every table and every column in your output.
If you are unsure about any classification, use a sensible default
(e.g. SEMANTIC_TYPE_UNKNOWN for columns, "Reference Data" for unclear domains).
"""

_USER_PROMPT = """\
Analyse the following database schema and produce all enrichment data.

Database: {database_name}
Vendor: {database_vendor}
Version: {database_version}

Tables and columns:
{tables_info}

Foreign-key relationships:
{relationships_info}

Produce all enrichment data (descriptions, roles, domains, semantic types,
entities, entity relationships, use cases, and sample queries).
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_schema(schema: CanonicalSchema) -> tuple[str, str]:
    """Format tables and relationships for the LLM prompt.

    Returns (tables_info, relationships_info).
    """
    # Tables and columns
    table_lines: list[str] = []
    for tbl in schema.tables:
        cols = ", ".join(
            f"{c.column_name} ({c.data_type})"
            f"{' PK' if c.is_primary_key else ''}"
            for c in tbl.columns
        )
        table_lines.append(f"  - {tbl.table_name}: [{cols}]")
    tables_info = "\n".join(table_lines) if table_lines else "(no tables)"

    # Relationships
    rel_lines: list[str] = []
    for rel in schema.relationships:
        rel_lines.append(
            f"  - {rel.from_table}.{rel.from_column} "
            f"\u2192 {rel.to_table}.{rel.to_column}"
        )
    relationships_info = "\n".join(rel_lines) if rel_lines else "(no relationships)"

    return tables_info, relationships_info


def _build_database_context(schema: CanonicalSchema) -> str:
    """Build database context string."""
    db = schema.database_info
    parts = []
    if db:
        if db.name:
            parts.append(f"Schema: {db.name}")
        if db.vendor:
            parts.append(f"Vendor: {db.vendor}")
        if db.version:
            parts.append(f"Version: {db.version}")
    return " | ".join(parts) if parts else "(no database info)"


# ---------------------------------------------------------------------------
# Node function — single enrichment node
# ---------------------------------------------------------------------------


def consolidated_enrichment_node(state: PipelineState) -> PipelineState:
    """Single enrichment node: one LLM call + fast rule-based passes.

    PipelineState fields produced
    -----------------------------
    - ``descriptions`` — from LLM (table + column descriptions)
    - ``business_roles`` — from LLM
    - ``domains`` — from LLM
    - ``semantic_types`` — from LLM + RuleEngine overrides
    - ``entities`` — from LLM
    - ``entity_relationships`` — physical (from schema) + entity-level (from LLM)
    - ``use_cases`` — from LLM
    - ``sample_queries`` — from LLM
    - ``patterns`` — from rule-based pattern_detection (fast)
    - ``validation_report`` — from rule-based validation (fast)
    """
    # --- Early exit when there is no schema ----------------------------------
    if state.canonical_schema is None:
        logger.warning("canonical_schema is None — skipping enrichment")
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
        return state

    schema = state.canonical_schema
    tables_info, relationships_info = _format_schema(schema)

    if not tables_info or tables_info == "(no tables)":
        logger.warning("canonical_schema has no tables — skipping enrichment")
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
        return state

    # Database context
    db = schema.database_info
    db_name = db.name or ""
    db_vendor = db.vendor or ""
    db_version = db.version or ""

    # ==================================================================
    # 1. Single LLM call for all enrichment
    # ==================================================================
    logger.info(
        "[consolidated] ▶  LLM enrichment call "
        "(%d tables, %d columns, %d relationships)",
        len(schema.tables),
        sum(len(t.columns) for t in schema.tables),
        len(schema.relationships),
    )

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(
            ConsolidatedEnrichmentOutput, method="function_calling"
        )

        user_prompt = _USER_PROMPT.format(
            database_name=db_name,
            database_vendor=db_vendor,
            database_version=db_version,
            tables_info=tables_info,
            relationships_info=relationships_info,
        )

        result = cast(
            "ConsolidatedEnrichmentOutput",
            structured_llm.invoke(
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            ),
        )

        if result is None:
            logger.warning("LLM returned None — all enrichment fields will be empty")
            state.descriptions = {"table_descriptions": {}, "column_descriptions": {}}
            state.business_roles = {}
            state.domains = {}
            state.semantic_types = {}
            state.entities = None
            state.entity_relationships = None
            state.use_cases = []
            state.sample_queries = []
            # Still run fast passes for patterns and validation
            _run_fast_passes(state)
            return state

        # --- Map LLM output to PipelineState fields --------------------------

        # descriptions
        state.descriptions = {
            "table_descriptions": result.table_descriptions or {},
            "column_descriptions": result.column_descriptions or {},
        }

        # business_roles
        state.business_roles = result.business_roles or {}

        # domains
        state.domains = result.domains or {}

        # semantic_types — LLM output first, RuleEngine overrides below
        semantic_types: dict[str, str] = dict(result.semantic_types or {})

        # entities
        entities: list[str] = []
        if result.entities:
            seen: set[str] = set()
            for e in result.entities:
                if e not in seen:
                    seen.add(e)
                    entities.append(e)
        state.entities = entities if entities else None

        # entity_relationships
        entity_rels: list[dict[str, str]] = []
        if result.entity_relationships:
            for item in result.entity_relationships:
                entity_rels.append(
                    {
                        "entity": item.entity,
                        "related_entities": item.related_entities,
                        "business_meaning": item.business_meaning,
                    }
                )

        # Physical relationships (extracted directly from canonical schema)
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

        # use_cases (stored as list of dicts)
        state.use_cases = [
            {
                "name": uc.name,
                "description": uc.description,
                "involved_tables": ", ".join(uc.involved_tables)
                if uc.involved_tables
                else "",
            }
            for uc in (result.use_cases or [])
        ]

        # sample_queries
        state.sample_queries = [
            {
                "question": q.question,
                "sql": q.sql,
                "category": q.category,
            }
            for q in (result.sample_queries or [])
        ]

        logger.info(
            "[consolidated] ✓  LLM enrichment complete — "
            "%d tables described, %d columns typed, %d entities, "
            "%d use cases, %d queries",
            len(state.descriptions.get("table_descriptions", {})),
            len(semantic_types),
            len(entities),
            len(state.use_cases),
            len(state.sample_queries),
        )

        # ==================================================================
        # 2. RuleEngine semantic type overrides (PII / pattern-based)
        # ==================================================================
        engine = RuleEngine()
        for table in schema.tables:
            for column in table.columns:
                key = f"{table.table_name}.{column.column_name}"
                rule_result = engine.classify(column.column_name, column.data_type)
                if rule_result.get("classification"):
                    # RuleEngine overrides LLM for PII / known patterns
                    semantic_types[key] = rule_result["classification"]

        state.semantic_types = semantic_types
        logger.info(
            "[consolidated] ✓  RuleEngine applied — %d semantic types total",
            len(semantic_types),
        )

    except Exception:
        logger.exception(
            "[consolidated] ✗  LLM enrichment failed — "
            "falling back to empty enrichment fields"
        )
        state.descriptions = {"table_descriptions": {}, "column_descriptions": {}}
        state.business_roles = {}
        state.domains = {}
        state.semantic_types = {}
        state.entities = None
        state.entity_relationships = None
        state.use_cases = []
        state.sample_queries = []

    # ==================================================================
    # 3. Fast rule-based passes (pattern_detection, validation)
    # ==================================================================
    _run_fast_passes(state)

    return state


def _run_fast_passes(state: PipelineState) -> None:
    """Run fast rule-based passes that don't need LLM calls."""
    # pattern_detection_node is fast (YAML lookup, no LLM)
    pattern_detection_node(state)

    # validation_node is fast (rule-based checks, no LLM)
    validation_node(state)

    logger.info(
        "[consolidated] ✓  Fast passes complete — "
        "%d patterns, validation: %s",
        len(state.patterns or []),
        state.validation_report.get("status", "N/A")
        if isinstance(state.validation_report, dict)
        else "N/A",
    )


__all__ = ["consolidated_enrichment_node"]
