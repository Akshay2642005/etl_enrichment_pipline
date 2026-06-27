"""Insights generator — KPIs, Insights, Opportunities, Art of the Possible.

Builds business intelligence from enriched schema metadata using vector +
graph retrieval and a single LLM call with structured output.

This module is independent of FastAPI — it depends only on ``core.llm``,
``core.vector_store``, ``core.graph_store``, and ``core.embedding_service``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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

    kpis: list[KPI] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    opportunities: list[Opportunity] = field(default_factory=list)
    art_of_the_possible: list[ArtOfThePossible] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert business data analyst. Given the schema context
below, generate business intelligence across four categories. Use ONLY the tables,
columns, and relationships from the provided context — never invent tables or columns.

SCHEMA CONTEXT:
{schema_context}

{domain_filter}

---

OUTPUT REQUIREMENTS:

### KPIs (3-6 items)
Key Performance Indicators relevant to the schema's domain (e.g. Sales, Operations,
Workforce, Customer, Inventory, Financial, Logistics, etc.). Each KPI must include
a realistic SQL query that uses ONLY tables and columns from the context.

Category must be one of the following or another domain-appropriate category:
"Workforce", "Operations", "Equipment", "Inventory", "Sales", "Financial",
"Customer Service", "Logistics", "Compliance", "Marketing", "Product".

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
            f"  {er.get('entity', '')}  ->  "
            f"{er.get('related_entities', '')}{extra}"
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
    """Build a domain/entity filter instruction for the LLM prompt."""
    parts: list[str] = []
    if domain:
        parts.append(f"DOMAIN FILTER: Focus on the '{domain}' domain.")
        # List tables for this domain
        domain_tables = [
            t["table_name"]
            for t in metadata.get("tables", [])
            if t.get("domain", "").lower() == domain.lower()
        ]
        if domain_tables:
            parts.append(
                f"Relevant tables for this domain: {', '.join(domain_tables)}."
            )
    if entity:
        parts.append(f"ENTITY FOCUS: Prioritize insights related to '{entity}'.")
        # Find entity relationships
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

        try:
            structured_llm = self._llm.with_structured_output(
                InsightsResult, method="function_calling"
            )
            result = cast(
                "InsightsResult | None",
                structured_llm.invoke(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": _USER_PROMPT},
                    ]
                ),
            )

            if result is None:
                logger.warning("LLM returned None — returning empty InsightsResult")
                return self._empty_result()

            # Handle dict result (some providers return dict instead of dataclass)
            if isinstance(result, dict):
                result = self._dict_to_insights_result(result)

        except Exception:
            logger.exception(
                "Insights generation failed — returning graceful degradation"
            )
            return self._empty_result()

        # --- 5. Serialise to plain dicts ---
        return {
            "kpis": [
                self._dataclass_to_dict(k, _KPI_FIELDS)
                for k in (result.kpis or [])
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
                        retrieved_entities.append({
                            "entity": meta.get("entity", ""),
                            "related_entities": meta.get("related_entities", ""),
                            "business_meaning": meta.get("business_meaning", ""),
                        })
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
                "Tables retrieved by vector similarity: "
                + ", ".join(retrieved_tables)
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
                        entities.append({
                            "entity": tables[i],
                            "related_entities": tables[i + 1],
                            "business_meaning": "Discovered via FK join path",
                        })
        return entities

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
