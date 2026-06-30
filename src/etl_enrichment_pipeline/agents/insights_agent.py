"""Insights generator — KPIs, Insights, Opportunities, Art of the Possible.

Builds business intelligence from enriched schema metadata using vector +
graph retrieval and a single LLM call with structured output.

This module is independent of FastAPI — it depends only on ``core.llm``,
``core.vector_store``, ``core.graph_store``, and ``core.embedding_service``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from etl_enrichment_pipeline.core.llm import get_llm

if TYPE_CHECKING:
    from etl_enrichment_pipeline.core.embedding_service import EmbeddingService
    from etl_enrichment_pipeline.core.graph_store import GraphStore
    from etl_enrichment_pipeline.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured-output schemas
# ---------------------------------------------------------------------------


@dataclass
class KPI:
    """A single key performance indicator for aviation / airport operations."""

    name: str = ""
    description: str = ""
    sql_query: str = ""
    category: str = ""
    potential_value: str = ""


@dataclass
class Insight:
    """A data-driven business insight with supporting evidence."""

    finding: str = ""
    supporting_evidence: str = ""
    impact: str = ""
    confidence: float = 0.0


@dataclass
class Opportunity:
    """An identified area for operational improvement or growth."""

    area: str = ""
    description: str = ""
    potential_value: str = ""
    effort: str = ""
    suggested_approach: str = ""


@dataclass
class ArtOfThePossible:
    """A visionary / transformative capability enabled by the data."""

    title: str = ""
    description: str = ""
    technologies_needed: str = ""
    complexity: str = ""
    business_value: str = ""


@dataclass
class InsightsResult:
    """Aggregated output from the insights generator.

    All four categories are produced in a single LLM call.
    """

    kpis: list[KPI] | None = None
    insights: list[Insight] | None = None
    opportunities: list[Opportunity] | None = None
    art_of_the_possible: list[ArtOfThePossible] | None = None


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert business data analyst. Given the schema context
below, generate business intelligence across four categories.

CRITICAL — You MUST obey ALL of these rules:
1. Use ONLY the tables, columns, and relationships from the provided context.
   NEVER invent tables, columns, or domains that are not present.
2. Every SQL query in KPIs MUST reference ONLY tables and columns that exist
   in the schema context above. If a KPI cannot be written with real columns,
   omit it.
3. Every Insight MUST cite specific tables/columns as supporting evidence.
4. Every Opportunity MUST target an area that is clearly supported by the
   actual tables and columns in the context.
5. Do NOT add generic business platitudes — every output item must be
   directly traceable to the provided schema.

SCHEMA CONTEXT:
{schema_context}

{domain_filter}

---

OUTPUT REQUIREMENTS:

### KPIs (3-6 items)
Key Performance Indicators relevant to the schema's domain. Each KPI MUST include
a realistic SQL query that uses ONLY tables and columns from the context.

Category must be one of the domains actually present in the schema (e.g.
the domains listed in the DOMAIN FILTER above).

Potential value describes the business benefit (e.g. "Increases revenue by 15%",
"Saves $200K/year", "Reduces churn by 10%").

### Insights (3-5 items)
Data-driven findings about the business domain that could be surfaced from the
schema. Each insight needs:
- A specific, actionable finding
- Supporting evidence (tables/columns that back it up)
- Business impact description
- Confidence score (0.0-1.0)

### Opportunities (2-4 items)
Areas for operational improvement, cost savings, or new capabilities.
- potential_value: "Low" / "Medium" / "High"
- effort: "S" / "M" / "L"
- suggested_approach: Concrete next steps

### Art of the Possible (2-3 items)
Transformative capabilities that could be built on top of the data.
- complexity: "Low" / "Medium" / "High"
- Describe what technologies would be needed
- Quantify business value where possible

Return valid JSON matching the output schema exactly.
"""

_USER_PROMPT = """Based on the schema context above, generate a complete set of KPIs,
Insights, Opportunities, and Art of the Possible relevant to the business domain
reflected in the tables.

Ensure every SQL query references ONLY tables and columns present in the schema
context. Choose categories that match the actual domain (e.g. Sales, Inventory,
Customer, Operations, Workforce, etc.)."""

# ---------------------------------------------------------------------------
# Field-name constants for serialisation (used by InsightsGenerator)
# ---------------------------------------------------------------------------

_KPI_FIELDS = ("name", "description", "sql_query", "category", "potential_value")
_INSIGHT_FIELDS = ("finding", "supporting_evidence", "impact", "confidence")
_OPPORTUNITY_FIELDS = (
    "area",
    "description",
    "potential_value",
    "effort",
    "suggested_approach",
)
_AOTP_FIELDS = (
    "title",
    "description",
    "technologies_needed",
    "complexity",
    "business_value",
)

# ---------------------------------------------------------------------------
# Context formatting helpers
# ---------------------------------------------------------------------------


def _format_tables(tables: list[dict[str, Any]]) -> str:
    """Format table list into a readable schema block."""
    lines: list[str] = []
    for tbl in tables:
        lines.append(f"Table: {tbl['table_name']}")
        if tbl.get("description"):
            lines.append(f"  Description: {tbl['description']}")
        if tbl.get("business_role"):
            lines.append(f"  Role: {tbl['business_role']}")
        if tbl.get("domain"):
            lines.append(f"  Domain: {tbl['domain']}")
        for col in tbl.get("columns", []):
            col_name = col.get("column_name", "")
            data_type = col.get("data_type", "")
            sem_type = col.get("semantic_type", "")
            col_desc = col.get("description", "")
            pk = "PK" if col.get("is_primary_key") else ""
            extras = f"  [{sem_type}]" if sem_type else ""
            extras += f"  {col_desc}" if col_desc else ""
            extras += f"  {pk}" if pk else ""
            lines.append(f"  - {col_name} ({data_type}){extras}")
        lines.append("")
    return "\n".join(lines)


def _format_relationships(relationships: list[dict[str, Any]]) -> str:
    """Format foreign-key relationships into a readable block."""
    if not relationships:
        return ""
    lines: list[str] = ["### Foreign Key Relationships"]
    for rel in relationships:
        lines.append(
            f"  {rel.get('from_table', '')}.{rel.get('from_column', '')}"
            f"  ->  {rel.get('to_table', '')}.{rel.get('to_column', '')}"
        )
    return "\n".join(lines)


def _format_entity_relationships(entity_relationships: list[dict[str, Any]]) -> str:
    """Format entity relationships into a readable block."""
    if not entity_relationships:
        return ""
    lines: list[str] = ["### Entity Relationships"]
    for er in entity_relationships:
        meaning = er.get("business_meaning", "")
        extra = f"  :  {meaning}" if meaning else ""
        lines.append(
            f"  {er.get('entity', '')}  ->  {er.get('related_entities', '')}{extra}"
        )
    return "\n".join(lines)


def _format_business_processes(processes: list[dict[str, Any]]) -> str:
    """Format business processes into a readable block."""
    if not processes:
        return ""
    lines: list[str] = ["### Business Processes"]
    for bp in processes:
        lines.append(f"  {bp.get('domain', '')}:  {bp.get('tables', '')}")
    return "\n".join(lines)


def _format_use_cases(use_cases: list[dict[str, Any]]) -> str:
    """Format use cases into a readable block."""
    if not use_cases:
        return ""
    lines: list[str] = ["### Use Cases"]
    for uc in use_cases:
        lines.append(f"  {uc.get('name', '')}:  {uc.get('description', '')}")
        lines.append(f"    Tables: {uc.get('involved_tables', '')}")
    return "\n".join(lines)


def _format_sample_queries(queries: list[dict[str, Any]]) -> str:
    """Format sample queries into a readable block."""
    if not queries:
        return ""
    lines: list[str] = ["### Sample Queries"]
    for sq in queries:
        lines.append(f"  Question: {sq.get('question', '')}")
        lines.append(f"  SQL: {sq.get('sql', '')}")
    return "\n".join(lines)


def _build_schema_context(metadata: dict[str, Any]) -> str:
    """Build a comprehensive schema context string from enriched metadata.

    Uses only what's available in the metadata dict — no external queries.
    """
    sections: list[str] = []

    tables = metadata.get("tables", [])
    if tables:
        sections.append(_format_tables(tables))

    relationships = metadata.get("relationships", [])
    if relationships:
        sections.append(_format_relationships(relationships))

    entity_relationships = metadata.get("entity_relationships", [])
    if entity_relationships:
        sections.append(_format_entity_relationships(entity_relationships))

    business_processes = metadata.get("business_processes", [])
    if business_processes:
        sections.append(_format_business_processes(business_processes))

    use_cases = metadata.get("use_cases", [])
    if use_cases:
        sections.append(_format_use_cases(use_cases))

    sample_queries = metadata.get("sample_queries", [])
    if sample_queries:
        sections.append(_format_sample_queries(sample_queries))

    return "\n\n".join(sections) if sections else "(no schema context available)"


def _build_domain_filter(
    domain: str | None,
    entity: str | None,
    metadata: dict[str, Any],
) -> str:
    """Build a domain/entity filter instruction for the LLM prompt.

    When *domain* is ``None`` the function discovers all unique domains
    from the enriched metadata tables and lists them so the LLM is
    grounded in what actually exists.
    """
    parts: list[str] = []

    # Discover all table names and domains from the actual schema
    all_tables = metadata.get("tables", [])
    all_table_names = [t["table_name"] for t in all_tables if t.get("table_name")]

    if domain:
        parts.append(f"DOMAIN FILTER: Focus on the '{domain}' domain.")
        domain_tables = [
            t["table_name"]
            for t in all_tables
            if t.get("domain", "").lower() == domain.lower()
        ]
        if domain_tables:
            parts.append(
                f"Relevant tables for this domain: {', '.join(domain_tables)}."
            )
        else:
            parts.append(
                f"No tables are explicitly tagged with the '{domain}' domain. "
                f"Choose the most relevant tables from: {', '.join(all_table_names)}."
            )
    else:
        # Overview — list actual domains and tables found in the schema
        unique_domains = sorted(
            {t["domain"] for t in all_tables if t.get("domain") and t["domain"].strip()}
        )
        if unique_domains:
            parts.append(
                "DOMAIN OVERVIEW — The schema contains these actual domains: "
                + ", ".join(unique_domains)
                + "."
            )
        if all_table_names:
            parts.append(
                "All tables in the schema: " + ", ".join(all_table_names) + "."
            )
            parts.append(
                "Generate insights that span these tables and domains — "
                "do NOT introduce domains or tables that are not listed above."
            )

    if entity:
        parts.append(f"ENTITY FOCUS: Prioritize insights related to '{entity}'.")
        for er in metadata.get("entity_relationships", []):
            if er.get("entity", "").lower() == entity.lower():
                parts.append(
                    f"The '{entity}' entity is related to: "
                    f"{er.get('related_entities', '')} "
                    f"({er.get('business_meaning', '')})."
                )

    if not parts:
        return (
            "No domain or entity filter — cover all aspects of the "
            "business domain reflected in the schema context."
        )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Insights Generator
# ---------------------------------------------------------------------------


class InsightsGenerator:
    """Generates KPIs, Insights, Opportunities, and Art of the Possible from
    enriched schema metadata.

    Uses ``get_llm()`` with structured output to produce all four insight
    categories in a single LLM call.  Optionally queries VectorStore and
    GraphStore for retrieval-augmented context, but falls back to the
    metadata dict alone when those stores are unavailable.

    Usage::

        generator = InsightsGenerator(enriched_metadata)
        result = await generator.generate(domain="Flight Operations")
        print(result["kpis"])
    """

    def __init__(
        self,
        enriched_metadata: dict[str, Any],
        vector_store: VectorStore | None = None,
        graph_store: GraphStore | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize the insights generator.

        Args:
            enriched_metadata: The output of the enrichment pipeline —
                a dict with keys ``tables``, ``relationships``,
                ``entity_relationships``, ``business_processes``,
                ``use_cases``, ``sample_queries``, etc.
            vector_store: Optional ``VectorStore`` for semantic table
                retrieval.  When provided, the generator searches for
                the top-10 tables relevant to the domain/entity filter.
            graph_store: Optional ``GraphStore`` for entity-relationship
                traversal.  When provided, the generator discovers join
                paths between matched tables.
            embedding_service: Optional shared ``EmbeddingService``
                singleton.  When omitted a new instance is created on
                demand (less efficient).
        """
        self._metadata = enriched_metadata
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._embedding_service = embedding_service
        self._llm = get_llm()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        domain: str | None = None,
        entity: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate business intelligence from the enriched schema.

        Args:
            domain: Optional domain filter (e.g. ``"Flight Operations"``,
                ``"Human Resources"``).  When provided, the context is
                scoped to tables belonging to that domain.
            entity: Optional entity focus (e.g. ``"Flight"``,
                ``"Employee"``).  When provided, entity-relationship
                context for that entity is emphasised.

        Returns:
            A dict with four keys, each containing a list of dicts:

            - ``kpis`` — 3-6 KPI entries
            - ``insights`` — 3-5 insight entries
            - ``opportunities`` — 2-4 opportunity entries
            - ``art_of_the_possible`` — 2-3 visionary entries
        """
        # --- 1. Build schema context ---
        schema_context = _build_schema_context(self._metadata)

        # --- 2. Optionally retrieve vector-store context ---
        retrieval_context = await self._retrieve_context(domain, entity)
        if retrieval_context:
            schema_context = (
                f"{schema_context}\n\n"
                f"---\n"
                f"### Vector-Search Context (top matched tables)\n"
                f"{retrieval_context}"
            )

        # --- 3. Build domain/entity filter ---
        domain_filter = _build_domain_filter(domain, entity, self._metadata)

        # --- 4. Call LLM with structured output ---
        system_prompt = _SYSTEM_PROMPT.format(
            schema_context=schema_context,
            domain_filter=domain_filter,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _USER_PROMPT},
        ]

        result: InsightsResult | None = None

        # --- Attempt 1: function_calling (most structured) ---
        # Use include_raw=True so we can inspect the raw message when
        # the model returns None (e.g. malformed tool-call response).
        try:
            raw_output = self._llm.with_structured_output(
                InsightsResult,
                method="function_calling",
                include_raw=True,
            ).invoke(messages)

            if isinstance(raw_output, dict):
                result = cast("InsightsResult | None", raw_output.get("parsed"))
                if result is None:
                    _err = raw_output.get("parsing_error")
                    _raw = raw_output.get("raw")
                    _content_len = len(getattr(_raw, "content", "") or "")
                    logger.warning(
                        "function_calling returned None — "
                        "parsing_error=%s, raw_content_len=%d",
                        _err,
                        _content_len,
                    )
            else:
                result = cast("InsightsResult | None", raw_output)

        except Exception as _exc:
            logger.warning("function_calling attempt failed: %s", _exc)

        # --- Attempt 2: json_mode fallback ---
        # Broader model support — works with Ollama models that don’t
        # reliably implement tool-use (e.g. qwen2.5:3b, llama3 etc.).
        if result is None:
            try:
                result = cast(
                    "InsightsResult | None",
                    self._llm.with_structured_output(
                        InsightsResult, method="json_mode"
                    ).invoke(messages),
                )
                if result is not None:
                    logger.info(
                        "json_mode fallback succeeded for domain=%s",
                        domain or "<all>",
                    )
                else:
                    logger.warning(
                        "json_mode fallback also returned None for domain=%s",
                        domain or "<all>",
                    )
            except Exception as _exc:
                logger.warning("json_mode attempt failed: %s", _exc)

        if result is None:
            logger.warning(
                "All LLM attempts returned None for domain=%s — returning empty result",
                domain or "<all>",
            )
            return self._empty_result()

        # Handle dict result (some providers return dict instead of dataclass)
        if isinstance(result, dict):
            result = self._dict_to_insights_result(result)

        # --- 5. Serialise to plain dicts ---
        raw_output = {
            "kpis": [
                self._dataclass_to_dict(k, _KPI_FIELDS) for k in (result.kpis or [])
            ],
            "insights": [
                self._dataclass_to_dict(i, _INSIGHT_FIELDS)
                for i in (result.insights or [])
            ],
            "opportunities": [
                self._dataclass_to_dict(o, _OPPORTUNITY_FIELDS)
                for o in (result.opportunities or [])
            ],
            "art_of_the_possible": [
                self._dataclass_to_dict(a, _AOTP_FIELDS)
                for a in (result.art_of_the_possible or [])
            ],
        }

        # --- 6. Post-generation grounding validation ---
        # Strip any items referencing tables not in the actual schema.
        # This catches LLM hallucinations even when the model ignores
        # the grounding rules in the system prompt.
        validated = self._validate_grounding(raw_output)
        return validated

    # ------------------------------------------------------------------
    # Internal: retrieval
    # ------------------------------------------------------------------

    async def _retrieve_context(
        self,
        domain: str | None,
        entity: str | None,
    ) -> str:
        """Query VectorStore and GraphStore for retrieval-augmented context.

        Falls back to an empty string when either store is unavailable.
        """
        if self._vector_store is None and self._graph_store is None:
            return ""

        query_parts: list[str] = []
        if domain:
            query_parts.append(f"domain {domain}")
        if entity:
            query_parts.append(f"entity {entity}")
        query = " ".join(query_parts) if query_parts else "business schema"

        retrieved_tables: list[str] = []
        retrieved_entities: list[dict[str, Any]] = []

        # --- Vector search for top-10 tables ---
        if self._vector_store is not None:
            try:
                from etl_enrichment_pipeline.core.embedding_service import (
                    EmbeddingService,
                )

                emb_service = self._embedding_service or EmbeddingService()
                query_emb = emb_service.generate_embeddings([query])[0]
                table_results = await self._vector_store.search_similar(
                    query_emb, object_type="table", top_k=10
                )
                retrieved_tables = [
                    r.metadata.get("table_name", "")
                    for r in table_results
                    if r.metadata.get("table_name")
                ]

                # Also search for entity relationships
                rel_results = await self._vector_store.search_similar(
                    query_emb, object_type="relationship", top_k=5
                )
                for r in rel_results:
                    meta = r.metadata
                    if meta.get("relationship_type") == "entity_relationship":
                        retrieved_entities.append(
                            {
                                "entity": meta.get("entity", ""),
                                "related_entities": meta.get("related_entities", ""),
                                "business_meaning": meta.get("business_meaning", ""),
                            }
                        )
            except Exception:
                logger.warning(
                    "VectorStore query failed — skipping vector context",
                    exc_info=True,
                )

        # --- Graph traversal for join paths ---
        if self._graph_store is not None and retrieved_tables:
            try:
                join_paths = await self._graph_store.find_join_paths(
                    retrieved_tables, max_hops=2
                )
                if join_paths:
                    retrieved_entities.extend(
                        self._join_paths_to_entity_context(join_paths)
                    )
            except Exception:
                logger.warning(
                    "GraphStore query failed — skipping graph context",
                    exc_info=True,
                )

        # --- Format retrieval context ---
        context_parts: list[str] = []
        if retrieved_tables:
            context_parts.append(
                "Tables retrieved by vector similarity: " + ", ".join(retrieved_tables)
            )
        if retrieved_entities:
            er_lines = ["Entity relationships from retrieval:"]
            for er in retrieved_entities:
                meaning = er.get("business_meaning", "")
                er_lines.append(
                    f"  {er.get('entity', '')} -> "
                    f"{er.get('related_entities', '')}"
                    f"{'  :  ' + meaning if meaning else ''}"
                )
            context_parts.append("\n".join(er_lines))

        return "\n\n".join(context_parts) if context_parts else ""

    @staticmethod
    def _join_paths_to_entity_context(
        join_paths: list[Any],
    ) -> list[dict[str, Any]]:
        """Convert GraphStore ``JoinPath`` results to entity-relationship dicts."""
        entities: list[dict[str, Any]] = []
        seen_pairs: set[str] = set()
        for jp in join_paths:
            if isinstance(jp, dict):
                tables = jp.get("tables", [])
            else:
                tables = getattr(jp, "tables", [])
            if len(tables) >= 2:
                for i in range(len(tables) - 1):
                    pair_key = f"{tables[i]}->{tables[i + 1]}"
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        entities.append(
                            {
                                "entity": tables[i],
                                "related_entities": tables[i + 1],
                                "business_meaning": "Discovered via FK join path",
                            }
                        )
        return entities

    # ------------------------------------------------------------------
    # Internal: post-generation grounding validation
    # ------------------------------------------------------------------

    def _get_real_table_names(self) -> set[str]:
        """Return the set of actual table names from the enriched schema.

        These are the ONLY tables the LLM is allowed to reference in SQL.
        """
        return {
            t["table_name"].lower()
            for t in (self._metadata.get("tables") or [])
            if t.get("table_name")
        }

    def _get_valid_identifiers(self) -> set[str]:
        """Return all valid identifiers: table names AND column names.

        Used for text-field grounding validation so that the LLM is not
        penalised for correctly referencing column names in descriptions,
        supporting evidence, or suggested approaches.  SQL-query validation
        still uses the stricter :meth:`_get_real_table_names` set.
        """
        valid: set[str] = set()
        for t in self._metadata.get("tables") or []:
            if t.get("table_name"):
                valid.add(t["table_name"].lower())
            for col in t.get("columns", []):
                if col.get("column_name"):
                    valid.add(col["column_name"].lower())
        return valid

    @staticmethod
    def _extract_sql_tables(sql: str) -> set[str]:
        """Extract table names from a SQL query.

        Looks for identifiers immediately after ``FROM``, ``JOIN``,
        ``UPDATE``, ``INTO``, and ``TABLE`` keywords — these are
        unambiguously table references in SQL.
        """
        if not sql:
            return set()

        import re

        table_refs: set[str] = set()
        patterns = [
            r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bJOIN\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bUPDATE\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bINTO\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\bTABLE\s+([A-Za-z_][A-Za-z0-9_]*)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, sql, re.IGNORECASE):
                name = match.group(1).lower()
                if name in (
                    "select",
                    "where",
                    "set",
                    "values",
                    "key",
                    "index",
                    "constraint",
                    "primary",
                    "foreign",
                    "unique",
                    "check",
                    "default",
                    "null",
                    "true",
                    "false",
                    "on",
                    "as",
                    "and",
                    "or",
                    "not",
                    "in",
                    "is",
                    "like",
                    "between",
                    "exists",
                ):
                    continue
                table_refs.add(name)

        return table_refs

    @staticmethod
    def _extract_identifier_tokens(text: str) -> set[str]:
        """Extract tokens that LOOK like database identifiers from free text.

        Picks out snake_case, PascalCase, and UPPER_CASE sequences
        that are at least 3 characters — these are likely to be table
        or column references rather than plain English words.
        """
        if not text:
            return set()

        import re

        candidates: set[str] = set()
        for match in re.finditer(
            r"\b[a-z]+_[a-z][a-z0-9_]*(?:_[a-z][a-z0-9_]*)*\b", text
        ):
            candidates.add(match.group(0))
        for match in re.finditer(r"\b[A-Z][A-Z]+(?:_[A-Z][A-Z]+)+\b", text):
            candidates.add(match.group(0).lower())
        for match in re.finditer(r"\b[A-Z][a-z]+[A-Z][a-zA-Z]*\b", text):
            candidates.add(match.group(0).lower())

        return candidates

    def _validate_item_tables(
        self,
        item: dict[str, Any],
        real_tables: set[str],
        sql_field: str | None,
        text_fields: list[str],
        item_type: str,
        valid_identifiers: set[str] | None = None,
    ) -> bool:
        """Return True if the item's SQL query references only real tables.

        Two validation passes are applied:

        1. **SQL validation (strict)** — if *sql_field* is provided, every
           table name in the query is checked against *real_tables*.  Items
           whose SQL references non-existent tables are rejected.

        2. **Text validation (informational)** — identifier-like tokens in
           *text_fields* are checked against *valid_identifiers* (table names
           **plus** column names).  Mismatches are logged as DEBUG messages
           only; items are **never rejected** solely because of text tokens.
           This prevents false positives when the LLM correctly cites column
           names (e.g. ``crew_id``, ``departure_time``) in descriptions.
        """
        real_lower = {t.lower() for t in real_tables}
        # Broader set for text validation: tables + columns.
        # Falls back to real_tables if caller doesn't provide it.
        valid_id_lower = (
            valid_identifiers if valid_identifiers is not None else real_lower
        )

        # ── SQL validation — strict, reject on bad table references ──────
        if sql_field:
            sql_text = str(item.get(sql_field, "") or "")
            sql_tables = self._extract_sql_tables(sql_text)
            bad_sql = sql_tables - real_lower
            if bad_sql:
                logger.warning(
                    "[grounding] %s SQL references non-existent tables %s — "
                    "schema has: %s",
                    item_type,
                    sorted(bad_sql),
                    sorted(real_lower),
                )
                return False

        # ── Text validation — informational only, never rejects ───────────
        all_text = " ".join(str(item.get(f, "") or "") for f in text_fields)
        identifier_tokens = self._extract_identifier_tokens(all_text)
        bad_tokens = identifier_tokens - valid_id_lower
        if bad_tokens:
            logger.debug(
                "[grounding] %s text has unrecognized identifiers %s "
                "(informational — not filtering item)",
                item_type,
                sorted(bad_tokens),
            )

        return True

    def _validate_grounding(
        self,
        result: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Post-generation validation pass.

        **Only SQL queries are validated strictly** — KPIs whose ``sql_query``
        field references tables that do NOT exist in the actual enriched schema
        are removed.  Text-field tokens (insights, opportunities, etc.) are
        checked against the broader valid-identifiers set (table names + column
        names) and produce DEBUG-level log entries only; no items are removed
        solely because of text mismatches.

        This design prevents false positives when the LLM correctly cites
        column names (e.g. ``crew_id``, ``departure_time``) or business terms
        in free-text descriptions.
        """
        real_tables = self._get_real_table_names()
        if not real_tables:
            logger.warning(
                "[grounding] No real tables found in metadata — "
                "skipping grounding validation"
            )
            return result

        # Build the broader valid-identifier set (tables + all column names).
        valid_identifiers = self._get_valid_identifiers()

        validated: dict[str, list[dict[str, Any]]] = {}

        # KPIs: SQL is validated strictly; text fields are informational.
        validated["kpis"] = [
            item
            for item in (result.get("kpis") or [])
            if self._validate_item_tables(
                item,
                real_tables,
                sql_field="sql_query",
                text_fields=["name", "description"],
                item_type="KPI",
                valid_identifiers=valid_identifiers,
            )
        ]

        # Insights/Opportunities/ArtOfThePossible: no SQL field → never rejected.
        validated["insights"] = [
            item
            for item in (result.get("insights") or [])
            if self._validate_item_tables(
                item,
                real_tables,
                sql_field=None,
                text_fields=["finding", "supporting_evidence", "impact"],
                item_type="Insight",
                valid_identifiers=valid_identifiers,
            )
        ]

        validated["opportunities"] = [
            item
            for item in (result.get("opportunities") or [])
            if self._validate_item_tables(
                item,
                real_tables,
                sql_field=None,
                text_fields=["area", "description", "suggested_approach"],
                item_type="Opportunity",
                valid_identifiers=valid_identifiers,
            )
        ]

        validated["art_of_the_possible"] = [
            item
            for item in (result.get("art_of_the_possible") or [])
            if self._validate_item_tables(
                item,
                real_tables,
                sql_field=None,
                text_fields=["title", "description", "technologies_needed"],
                item_type="ArtOfThePossible",
                valid_identifiers=valid_identifiers,
            )
        ]

        for key in ("kpis", "insights", "opportunities", "art_of_the_possible"):
            before = len(result.get(key, []))
            after = len(validated.get(key, []))
            if before != after:
                logger.info(
                    "[grounding] %s: %d → %d KPIs removed (bad SQL table refs)",
                    key,
                    before,
                    after,
                )

        return validated

    # ------------------------------------------------------------------
    # Internal: serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> dict[str, list[dict[str, Any]]]:
        """Return an empty result dict with the correct shape."""
        return {
            "kpis": [],
            "insights": [],
            "opportunities": [],
            "art_of_the_possible": [],
        }

    @staticmethod
    def _dataclass_to_dict(obj: Any, fields_seq: tuple[str, ...]) -> dict[str, Any]:
        """Serialize a dataclass instance to a dict with the given field order."""
        return {f: getattr(obj, f) for f in fields_seq}

    @staticmethod
    def _dict_to_insights_result(data: dict[str, Any]) -> InsightsResult:
        """Convert a raw dict to InsightsResult (provider fallback)."""
        return InsightsResult(
            kpis=[
                KPI(**{f: (it.get(f) or "") for f in _KPI_FIELDS})
                for it in (data.get("kpis") or [])
            ],
            insights=[
                Insight(
                    finding=it.get("finding") or "",
                    supporting_evidence=it.get("supporting_evidence") or "",
                    impact=it.get("impact") or "",
                    confidence=float(it.get("confidence") or 0.0),
                )
                for it in (data.get("insights") or [])
            ],
            opportunities=[
                Opportunity(**{f: (it.get(f) or "") for f in _OPPORTUNITY_FIELDS})
                for it in (data.get("opportunities") or [])
            ],
            art_of_the_possible=[
                ArtOfThePossible(**{f: (it.get(f) or "") for f in _AOTP_FIELDS})
                for it in (data.get("art_of_the_possible") or [])
            ],
        )


__all__ = [
    "InsightsGenerator",
    "InsightsResult",
    "KPI",
    "Insight",
    "Opportunity",
    "ArtOfThePossible",
]
